import importlib.util
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import setup_env  # noqa: F401
from django.core.exceptions import ValidationError
from package.parser.baseParser import LoadPropertyPageException
from package.utils.error_page_replayer import ErrorPageReplayer
from package.utils.failure_reporter import FailureReporter, html_meta_key
from package.utils.storage import ObjectStorageManager

CLI_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "debug_tools", "fetch_run_failures.py",
)

OG_HTML = b'<html><head><meta property="og:url" content="https://www.livable.co.jp/tochi/C48259L92/"></head><body>x</body></html>'
URL = "https://www.livable.co.jp/tochi/C48259L92/"


class FakeItem:
    def __init__(self, error=None, **values):
        self._error = error
        self.full_clean_kwargs = None
        for k, v in values.items():
            setattr(self, k, v)

    def full_clean(self, **kwargs):
        self.full_clean_kwargs = kwargs
        if self._error:
            raise self._error


class FakeParser:
    def __init__(self, item=None, exc=None):
        self.item = item
        self.exc = exc
        self.received_content = None
        self.received_url = None

    def save_error_html(self, *_args, **_kwargs):
        raise AssertionError("save_error_html must be disabled during replay")

    async def parsePropertyDetailPage(self, session, url):
        self.received_url = url
        self.received_content = await self._getContent(session, url)
        self.save_error_html(url, self.received_content, reason="x")
        if self.exc:
            raise self.exc
        return self.item


class TestExtractPageUrl:
    def test_og_url(self):
        assert ErrorPageReplayer.extract_page_url(OG_HTML) == URL

    def test_canonical_fallback(self):
        html = b'<html><head><link rel="canonical" href="https://www.nomu.com/land/id/QD770295/"></head></html>'
        assert ErrorPageReplayer.extract_page_url(html) == "https://www.nomu.com/land/id/QD770295/"

    def test_og_url_preferred_over_canonical(self):
        html = (
            b'<html><head><link rel="canonical" href="https://a.example/c"/>'
            b'<meta property="og:url" content="https://a.example/og"/></head></html>'
        )
        assert ErrorPageReplayer.extract_page_url(html) == "https://a.example/og"

    def test_relative_or_missing_returns_none(self):
        assert ErrorPageReplayer.extract_page_url(b'<html><head><link rel="canonical" href="/rel"></head></html>') is None
        assert ErrorPageReplayer.extract_page_url(b"<html><body>none</body></html>") is None

    def test_shift_jis_page(self):
        html = (
            '<!DOCTYPE html><html><head><meta http-equiv="Content-Type" content="text/html; charset=shift_jis" />'
            '<title>ステップ物件詳細</title><link rel="canonical" href="https://www.stepon.co.jp/mansion/detail_168P3020/" />'
            '</head><body>' + "物件" * 200 + '</body></html>'
        ).encode("cp932")
        assert ErrorPageReplayer.extract_page_url(html) == "https://www.stepon.co.jp/mansion/detail_168P3020/"

    def test_strips_whitespace(self):
        html = b'<html><head><meta property="og:url" content="  https://a.example/x  "></head></html>'
        assert ErrorPageReplayer.extract_page_url(html) == "https://a.example/x"


class TestReplayHtml:
    def test_no_url(self):
        res = ErrorPageReplayer.replay_html(b"<html></html>", "tokyu_tochi")
        assert res == {"url": None, "status": "no_url", "invalid_fields": {}, "error": ""}

    def test_explicit_url_overrides_html(self):
        explicit = "https://smtrc.jp/detail/CompareDetails?propertyCode=Bkd260280&pageId=D010"
        with patch("package.utils.error_page_replayer.UrlRouter.create_parser", return_value=None) as cp:
            res = ErrorPageReplayer.replay_html(b"<html></html>", "smtrc_tochi", url=explicit)
        cp.assert_called_once_with(explicit, property_type="tochi")
        assert res["status"] == "no_parser"
        assert res["url"] == explicit

    def test_no_parser(self):
        with patch("package.utils.error_page_replayer.UrlRouter.create_parser", return_value=None):
            res = ErrorPageReplayer.replay_html(OG_HTML, "tokyu_tochi")
        assert res == {"url": URL, "status": "no_parser", "invalid_fields": {}, "error": ""}

    def test_ok_uses_saved_html_and_skips_unique_validation(self):
        item = FakeItem()
        parser = FakeParser(item=item)
        with patch("package.utils.error_page_replayer.UrlRouter.create_parser", return_value=parser):
            res = ErrorPageReplayer.replay_html(OG_HTML, "tokyu_tochi")
        assert res == {"url": URL, "status": "ok", "invalid_fields": {}, "error": ""}
        assert parser.received_content == OG_HTML
        assert parser.received_url == URL
        assert item.full_clean_kwargs == {"validate_unique": False}

    def test_invalid_reports_fields_values_and_errors(self):
        err = ValidationError({"price": ["must be positive"], "kenpei": ["bad", "worse"]})
        item = FakeItem(error=err, price=-1, kenpei="x" * 100)
        with patch("package.utils.error_page_replayer.UrlRouter.create_parser", return_value=FakeParser(item=item)):
            res = ErrorPageReplayer.replay_html(OG_HTML, "tokyu_tochi")
        assert res["status"] == "invalid"
        assert res["url"] == URL
        assert res["error"] == ""
        assert res["invalid_fields"] == {
            "price": {"value": "-1", "errors": ["must be positive"]},
            "kenpei": {"value": "x" * 80, "errors": ["bad", "worse"]},
        }

    def test_parse_error(self):
        parser = FakeParser(exc=LoadPropertyPageException("StrictExtractionFailed: address is empty"))
        with patch("package.utils.error_page_replayer.UrlRouter.create_parser", return_value=parser):
            res = ErrorPageReplayer.replay_html(OG_HTML, "tokyu_tochi")
        assert res["status"] == "parse_error"
        assert res["error"] == "LoadPropertyPageException: StrictExtractionFailed: address is empty"
        assert res["invalid_fields"] == {}

    def test_parse_error_message_truncated(self):
        parser = FakeParser(exc=RuntimeError("e" * 1000))
        with patch("package.utils.error_page_replayer.UrlRouter.create_parser", return_value=parser):
            res = ErrorPageReplayer.replay_html(OG_HTML, "tokyu_tochi")
        assert len(res["error"]) == 500
        assert res["error"].startswith("RuntimeError: eee")

    def test_validation_error_with_no_item_returns_parse_error(self):
        parser = FakeParser(exc=ValidationError("Failed inside parser"))
        with patch("package.utils.error_page_replayer.UrlRouter.create_parser", return_value=parser):
            res = ErrorPageReplayer.replay_html(OG_HTML, "tokyu_tochi")
        assert res["status"] == "parse_error"
        assert "ValidationError: ['Failed inside parser']" in res["error"]
        assert res["invalid_fields"] == {}

    def test_validation_error_without_message_dict_returns_parse_error(self):
        item = FakeItem(error=ValidationError("List style validation error"))
        with patch("package.utils.error_page_replayer.UrlRouter.create_parser", return_value=FakeParser(item=item)):
            res = ErrorPageReplayer.replay_html(OG_HTML, "tokyu_tochi")
        assert res["status"] == "parse_error"
        assert "ValidationError: ['List style validation error']" in res["error"]
        assert res["invalid_fields"] == {}

    @pytest.mark.parametrize("job_key,expected", [
        ("sumifu_investment_apartment", "apartment"),
        ("homes_invest_apartment", "apartment"),
        ("tokyu_tochi", "tochi"),
        ("nomura_mansion", "mansion"),
        ("heim_kodate", "kodate"),
        ("sumifu_invest_kodate", None),
    ])
    def test_router_property_type_mapping(self, job_key, expected):
        with patch("package.utils.error_page_replayer.UrlRouter.create_parser", return_value=None) as cp:
            ErrorPageReplayer.replay_html(OG_HTML, job_key)
        cp.assert_called_once_with(URL, property_type=expected)


def _result(status, fields=None, url=URL):
    return {"url": url, "status": status, "invalid_fields": fields or {}, "error": ""}


class TestReplayDate:
    @pytest.fixture(autouse=True)
    def _isolate_fallback_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_LOCAL_FALLBACK_DIR", str(tmp_path))
        self.tmp_path = tmp_path

    def _storage(self, keys):
        sm = MagicMock()
        sm.list_files.return_value = keys
        sm.read_bytes.side_effect = lambda k: k.encode("utf-8")
        return sm

    def test_aggregates_per_job(self):
        keys = [
            "runs/20260928/error_pages/tokyu_tochi/a.html",
            "runs/20260928/error_pages/tokyu_tochi/b.html",
            "runs/20260928/error_pages/tokyu_tochi/c.html",
            "runs/20260928/error_pages/nomura_tochi/d.html",
        ]
        results = {
            "a": _result("invalid", {"kenpei": {"value": "1", "errors": ["e"]}, "youseki": {"value": "", "errors": ["e"]}}),
            "b": _result("invalid", {"kenpei": {"value": "2", "errors": ["e"]}}),
            "c": _result("ok"),
            "d": _result("parse_error"),
        }

        def fake_replay(html, job_key, url=None):
            name = html.decode().rsplit("/", 1)[1].split(".")[0]
            assert job_key == ("tokyu_tochi" if name in "abc" else "nomura_tochi")
            assert url is None
            return results[name]

        sm = self._storage(keys)
        with patch("package.utils.error_page_replayer.get_storage_manager", return_value=sm), \
                patch.object(ErrorPageReplayer, "replay_html", side_effect=fake_replay):
            summary = ErrorPageReplayer.replay_date("20260928")

        sm.list_files.assert_called_once_with(prefix="runs/20260928/error_pages/")
        assert summary["total"] == 4
        assert summary["unresolved"] == 3
        tokyu = summary["jobs"]["tokyu_tochi"]
        assert tokyu["total"] == 3
        assert tokyu["status_counts"] == {"invalid": 2, "ok": 1}
        assert tokyu["field_counts"] == {"kenpei": 2, "youseki": 1}
        assert [s["html_key"] for s in tokyu["samples"]] == [keys[0], keys[1]]
        assert tokyu["samples"][0]["status"] == "invalid"
        nomura = summary["jobs"]["nomura_tochi"]
        assert nomura["status_counts"] == {"parse_error": 1}
        assert nomura["field_counts"] == {}

    def test_sidecar_meta_url_is_used(self):
        keys = [
            "runs/20260928/error_pages/smtrc_tochi/a.html",
            "runs/20260928/error_pages/smtrc_tochi/a_meta.json",
            "runs/20260928/error_pages/smtrc_tochi/b.html",
        ]
        sm = self._storage(keys)
        meta = json.dumps({"target_url": "https://smtrc.jp/detail/X"}).encode()
        sm.read_bytes.side_effect = lambda k: meta if k.endswith("_meta.json") else b"<html></html>"
        with patch("package.utils.error_page_replayer.get_storage_manager", return_value=sm), \
                patch.object(ErrorPageReplayer, "replay_html", return_value=_result("ok")) as rh:
            summary = ErrorPageReplayer.replay_date("20260928")
        assert summary["total"] == 2
        assert rh.call_args_list[0].kwargs == {"url": "https://smtrc.jp/detail/X"}
        assert rh.call_args_list[0].args == (b"<html></html>", "smtrc_tochi")
        assert rh.call_args_list[1].kwargs == {"url": None}

    def test_broken_meta_falls_back_to_html(self):
        keys = [
            "runs/20260928/error_pages/smtrc_tochi/a.html",
            "runs/20260928/error_pages/smtrc_tochi/a_meta.json",
        ]
        sm = self._storage(keys)
        sm.read_bytes.side_effect = lambda k: b"{broken" if k.endswith("_meta.json") else b"<html></html>"
        with patch("package.utils.error_page_replayer.get_storage_manager", return_value=sm), \
                patch.object(ErrorPageReplayer, "replay_html", return_value=_result("ok")) as rh:
            ErrorPageReplayer.replay_date("20260928")
        assert rh.call_args.kwargs == {"url": None}

    def test_job_filter(self):
        keys = [
            "runs/20260928/error_pages/tokyu_tochi/a.html",
            "runs/20260928/error_pages/nomura_tochi/d.html",
        ]
        with patch("package.utils.error_page_replayer.get_storage_manager", return_value=self._storage(keys)), \
                patch.object(ErrorPageReplayer, "replay_html", return_value=_result("ok")) as rh:
            summary = ErrorPageReplayer.replay_date("20260928", job_key="nomura_tochi")
        assert list(summary["jobs"]) == ["nomura_tochi"]
        assert rh.call_count == 1
        assert summary["unresolved"] == 0

    def test_samples_capped_at_five(self):
        keys = [f"runs/20260928/error_pages/tokyu_tochi/{i}.html" for i in range(8)]
        with patch("package.utils.error_page_replayer.get_storage_manager", return_value=self._storage(keys)), \
                patch.object(ErrorPageReplayer, "replay_html", return_value=_result("parse_error")):
            summary = ErrorPageReplayer.replay_date("20260928")
        assert len(summary["jobs"]["tokyu_tochi"]["samples"]) == 5
        assert summary["unresolved"] == 8

    def test_local_fallback_included_and_deduplicated(self):
        local_dir = self.tmp_path / "runs" / "20260928" / "error_pages" / "tokyu_tochi"
        local_dir.mkdir(parents=True)
        (local_dir / "a.html").write_bytes(b"local-a")
        (local_dir / "z.html").write_bytes(b"local-z")
        keys = ["runs/20260928/error_pages/tokyu_tochi/a.html"]
        seen = []

        def fake_replay(html, _job_key, url=None):
            seen.append(html)
            return _result("ok")

        with patch("package.utils.error_page_replayer.get_storage_manager", return_value=self._storage(keys)), \
                patch.object(ErrorPageReplayer, "replay_html", side_effect=fake_replay):
            summary = ErrorPageReplayer.replay_date("20260928")
        assert summary["total"] == 2
        assert sorted(seen) == [b"local-z", keys[0].encode()]

    def test_storage_failure_falls_back_to_local(self):
        local_dir = self.tmp_path / "runs" / "20260928" / "error_pages" / "heim_kodate"
        local_dir.mkdir(parents=True)
        (local_dir / "h.html").write_bytes(b"h")
        with patch("package.utils.error_page_replayer.get_storage_manager", side_effect=RuntimeError("no creds")), \
                patch.object(ErrorPageReplayer, "replay_html", return_value=_result("ok")):
            summary = ErrorPageReplayer.replay_date("20260928")
        assert summary["total"] == 1
        assert summary["storage_error"] == "no creds"

    def test_unreadable_blob_is_skipped(self):
        keys = [
            "runs/20260928/error_pages/tokyu_tochi/a.html",
            "runs/20260928/error_pages/tokyu_tochi/b.html",
        ]
        sm = self._storage(keys)
        sm.read_bytes.side_effect = [RuntimeError("boom"), b"ok"]
        with patch("package.utils.error_page_replayer.get_storage_manager", return_value=sm), \
                patch.object(ErrorPageReplayer, "replay_html", return_value=_result("ok")):
            summary = ErrorPageReplayer.replay_date("20260928")
        assert summary["total"] == 1


CLI_MANIFEST = {"date": "20260928", "total_failures": 1, "total_log_errors": 0, "storage_error": None,
                "failures": [], "log_errors": []}
CLI_REPLAY = {"total": 3, "unresolved": 2, "storage_error": None, "jobs": {
    "tokyu_tochi": {"total": 3, "status_counts": {"ok": 1, "invalid": 2}, "field_counts": {"kenpei": 2},
                    "samples": [{"html_key": "k", "url": URL, "status": "invalid",
                                 "invalid_fields": {"kenpei": {"value": "1", "errors": ["e"]}}, "error": ""}]}}}


class TestFetchRunFailuresCli:
    MANIFEST = CLI_MANIFEST
    REPLAY = CLI_REPLAY

    @pytest.fixture
    def cli(self):
        spec = importlib.util.spec_from_file_location("fetch_run_failures_561", CLI_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_replay_json(self, cli, capsys):
        with patch.object(cli.FailureReporter, "fetch_daily_failures", return_value=dict(self.MANIFEST)), \
                patch.object(cli.ErrorPageReplayer, "replay_date", return_value=self.REPLAY) as rd, \
                patch("sys.argv", ["fetch_run_failures.py", "--date", "20260928", "--replay", "--job", "tokyu_tochi"]):
            cli.main()
        rd.assert_called_once_with("20260928", job_key="tokyu_tochi")
        out = json.loads(capsys.readouterr().out)
        assert out["replay"] == self.REPLAY

    def test_logs_routed_to_stderr(self, cli):
        with patch.object(cli.FailureReporter, "fetch_daily_failures", return_value=dict(self.MANIFEST)), \
                patch.object(cli, "configure_logging") as cl, \
                patch("sys.argv", ["fetch_run_failures.py", "--date", "20260928"]):
            cli.main()
        cl.assert_called_once_with(force_reconfigure=True, output_stream=sys.stderr)

    def test_no_replay_by_default(self, cli, capsys):
        with patch.object(cli.FailureReporter, "fetch_daily_failures", return_value=dict(self.MANIFEST)), \
                patch.object(cli.ErrorPageReplayer, "replay_date") as rd, \
                patch("sys.argv", ["fetch_run_failures.py", "--date", "20260928"]):
            cli.main()
        rd.assert_not_called()
        assert "replay" not in json.loads(capsys.readouterr().out)

    def test_replay_summary(self, cli, capsys):
        with patch.object(cli.FailureReporter, "fetch_daily_failures", return_value=dict(self.MANIFEST)), \
                patch.object(cli.ErrorPageReplayer, "replay_date", return_value=self.REPLAY), \
                patch("sys.argv", ["fetch_run_failures.py", "--date", "20260928", "--replay", "--summary"]):
            cli.main()
        out = capsys.readouterr().out
        assert "=== Replay (current parsers) ===" in out
        assert "Unresolved: 2 / 3" in out
        assert "tokyu_tochi: unresolved 2 / 3 {'ok': 1, 'invalid': 2}" in out
        assert "fields: {'kenpei': 2}" in out
        assert "kenpei" in out and URL in out

    def test_replay_storage_error_exits_nonzero(self, cli, capsys):
        replay_err = {"total": 0, "unresolved": 0, "storage_error": "Connection error", "jobs": {}}
        with patch.object(cli.FailureReporter, "fetch_daily_failures", return_value=dict(self.MANIFEST)), \
                patch.object(cli.ErrorPageReplayer, "replay_date", return_value=replay_err), \
                patch("sys.argv", ["fetch_run_failures.py", "--date", "20260928", "--replay"]), \
                pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "ERROR: Failed to retrieve error pages from storage" in err
        assert "Connection error" in err


class TestErrorPageSidecarMeta:
    @pytest.fixture(autouse=True)
    def _isolate_fallback_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_LOCAL_FALLBACK_DIR", str(tmp_path))
        self.tmp_path = tmp_path

    def test_html_meta_key(self):
        assert html_meta_key("runs/d/error_pages/j/abc.html") == "runs/d/error_pages/j/abc_meta.json"

    def test_storage_upload_includes_meta(self):
        sm = MagicMock()
        sm.upload_bytes.return_value = "gs://b/k"
        with patch("package.utils.failure_reporter.get_storage_manager", return_value=sm):
            rec = FailureReporter.record_job_failure(
                company="smtrc", property_type="tochi", error_type="FetchOrParseError",
                error_message="Property Name: x", target_url="https://smtrc.jp/detail/X",
                raw_html=b"<html></html>", date_str="20260928",
            )
        meta_calls = [c for c in sm.upload_bytes.call_args_list if c.args[1].endswith("_meta.json")]
        assert len(meta_calls) == 1
        html_key = next(c.args[1] for c in sm.upload_bytes.call_args_list if c.args[1].endswith(".html"))
        assert meta_calls[0].args[1] == html_meta_key(html_key)
        assert meta_calls[0].kwargs == {"content_type": "application/json"}
        meta = json.loads(meta_calls[0].args[0])
        assert meta == {
            "target_url": "https://smtrc.jp/detail/X",
            "error_type": "FetchOrParseError",
            "error_message": "Property Name: x",
            "timestamp": rec["timestamp"],
        }

    def test_sidecar_upload_failure_does_not_abort_primary_telemetry(self):
        sm = MagicMock()
        sm.upload_bytes.side_effect = lambda _data, key, **_: "gs://b/h" if key.endswith(".html") else (
            (_ for _ in ()).throw(RuntimeError("sidecar fail")) if key.endswith("_meta.json") else "gs://b/m"
        )
        with patch("package.utils.failure_reporter.get_storage_manager", return_value=sm):
            rec = FailureReporter.record_job_failure(
                company="smtrc", property_type="tochi", error_type="FetchOrParseError",
                error_message="Property Name: x", target_url="https://smtrc.jp/detail/X",
                raw_html=b"<html></html>", date_str="20260928",
            )
        assert rec["metadata_key"] == "runs/20260928/failures/smtrc_tochi.json"
        assert sm.upload_bytes.call_count == 3
        # Primary metadata upload still succeeded
        meta_call = [c for c in sm.upload_bytes.call_args_list if c.args[1].endswith("smtrc_tochi.json")]
        assert len(meta_call) == 1

    def test_no_meta_without_html(self):
        sm = MagicMock()
        with patch("package.utils.failure_reporter.get_storage_manager", return_value=sm):
            FailureReporter.record_job_failure(
                company="sumifu", property_type="invest_kodate", error_type="ZeroCountFailure",
                error_message="0 items", date_str="20260928",
            )
        assert all(not c.args[1].endswith("_meta.json") for c in sm.upload_bytes.call_args_list)

    def test_local_fallback_writes_meta(self):
        with patch("package.utils.failure_reporter.get_storage_manager", side_effect=RuntimeError("down")):
            FailureReporter.record_job_failure(
                company="smtrc", property_type="tochi", error_type="FetchOrParseError",
                error_message="m", target_url="https://smtrc.jp/detail/Y",
                raw_html=b"<html></html>", date_str="20260928",
            )
        metas = list((self.tmp_path / "runs" / "20260928" / "error_pages" / "smtrc_tochi").glob("*_meta.json"))
        assert len(metas) == 1
        assert json.loads(metas[0].read_text(encoding="utf-8"))["target_url"] == "https://smtrc.jp/detail/Y"


class TestStorageReadBytes:
    def test_gcs_read_bytes(self):
        sm = ObjectStorageManager.__new__(ObjectStorageManager)
        sm.is_gcs = True
        sm.gcs_bucket = MagicMock()
        sm.gcs_bucket.blob.return_value.download_as_bytes.return_value = b"\x82\xa0"
        assert sm.read_bytes("k") == b"\x82\xa0"
        sm.gcs_bucket.blob.assert_called_once_with("k")

    def test_s3_read_bytes_and_read_text(self):
        sm = ObjectStorageManager.__new__(ObjectStorageManager)
        sm.is_gcs = False
        sm.bucket_name = "b"
        sm.s3_client = MagicMock()
        sm.s3_client.get_object.side_effect = lambda **_: {"Body": MagicMock(read=MagicMock(return_value="あ".encode()))}
        assert sm.read_bytes("k") == "あ".encode()
        assert sm.read_text("k") == "あ"
        sm.s3_client.get_object.assert_called_with(Bucket="b", Key="k")

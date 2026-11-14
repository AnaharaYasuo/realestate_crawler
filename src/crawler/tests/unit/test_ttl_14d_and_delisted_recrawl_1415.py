"""Unit tests for Issue #1415: 14-day TTL shortening & daily TTL-expired direct-URL recrawl / delisted flagging."""

from __future__ import annotations

import datetime
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from django.db import OperationalError
from django.utils import timezone
import pytest

import setup_env  # noqa: F401
from package.api import api as api_module
from package.api import differential as diff_module
from package.api.differential import ListItem, _should_fetch_item
from package.parser.baseParser import (
    AccessBlockedException,
    ListingEndedException,
    SiteMaintenanceException,
)
from scripts.ops import run_ttl_expired_recrawl as ttl_recrawl


class TestDifferentialTtl14Days:
    def test_default_ttl_is_14_days_in_api_and_differential(self):
        code = inspect.getsource(api_module.ParseMiddlePageAsyncBase._callApi)
        assert '"14"' in code
        sig = inspect.signature(diff_module.filter_differential_items)
        assert sig.parameters["ttl_days"].default == 14

    def test_should_fetch_item_refetches_at_15_days_and_skips_at_13_days(self):
        now = datetime.datetime(2026, 11, 14, 12, 0, tzinfo=datetime.UTC)
        item = ListItem("https://www.rehouse.co.jp/buy/mansion/bkdetail/F001/", price=50000000)

        fresh_rec = {
            "price": 50000000,
            "last_detail_fetched_at": now - datetime.timedelta(days=13, hours=23),
            "updateDateTime": now,
        }
        assert _should_fetch_item(item, fresh_rec, now, ttl_days=14) is False

        expired_rec = {
            "price": 50000000,
            "last_detail_fetched_at": now - datetime.timedelta(days=14, seconds=10),
            # Even if list-skip updated updateDateTime today, 14-day detail TTL must fire!
            "updateDateTime": now,
        }
        assert _should_fetch_item(item, expired_rec, now, ttl_days=14) is True


class TestCollectTtlExpiredTargets:
    def test_collects_expired_published_evals_legacy_null_evals_and_unevaluated_models(self):
        now = datetime.datetime(2026, 11, 14, 12, 0, tzinfo=datetime.UTC)

        # 1) Expired published PropertyEvaluation (last_detail_fetched_at 15d ago) -> INCLUDE
        ev_expired = {
            "id": 10,
            "property_url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/EXP1/",
            "company": "mitsui",
            "property_type": "mansion",
            "property_id": 101,
            "is_published": True,
            "last_detail_fetched_at": now - datetime.timedelta(days=15),
        }
        # 2) Fresh published PropertyEvaluation (last_detail_fetched_at 5d ago) -> EXCLUDE
        ev_fresh = {
            "id": 11,
            "property_url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/FRESH1/",
            "company": "mitsui",
            "property_type": "mansion",
            "property_id": 102,
            "is_published": True,
            "last_detail_fetched_at": now - datetime.timedelta(days=5),
        }
        # 3) Legacy published PropertyEvaluation with last_detail_fetched_at=None, model inputDateTime 20d ago -> INCLUDE
        ev_null_old = {
            "id": 12,
            "property_url": "https://www.livable.co.jp/mansion/C001/",
            "company": "tokyu",
            "property_type": "mansion",
            "property_id": 201,
            "is_published": True,
            "last_detail_fetched_at": None,
        }
        # 4) Legacy published PropertyEvaluation with last_detail_fetched_at=None, model inputDateTime 3d ago -> EXCLUDE
        ev_null_recent = {
            "id": 13,
            "property_url": "https://www.livable.co.jp/mansion/C002/",
            "company": "tokyu",
            "property_type": "mansion",
            "property_id": 202,
            "is_published": True,
            "last_detail_fetched_at": None,
        }
        # 5) Already delisted PropertyEvaluation -> EXCLUDE even if model row still exists in property table
        ev_delisted = {
            "id": 14,
            "property_url": "https://www.nomu.com/mansion/id/DEL1/",
            "company": "nomura",
            "property_type": "mansion",
            "property_id": 301,
            "is_published": False,
            "last_detail_fetched_at": now - datetime.timedelta(days=40),
        }

        all_evals = [ev_expired, ev_fresh, ev_null_old, ev_null_recent, ev_delisted]

        model_rows_by_comp = {
            "mitsui": [
                {
                    "id": 101,
                    "pageUrl": "https://www.rehouse.co.jp/buy/mansion/bkdetail/EXP1/",
                    "inputDateTime": now - datetime.timedelta(days=30),
                    "updateDateTime": now - datetime.timedelta(days=1),
                },
                {
                    "id": 102,
                    "pageUrl": "https://www.rehouse.co.jp/buy/mansion/bkdetail/FRESH1/",
                    "inputDateTime": now - datetime.timedelta(days=5),
                    "updateDateTime": now - datetime.timedelta(days=1),
                },
            ],
            "tokyu": [
                {
                    "id": 201,
                    "pageUrl": "https://www.livable.co.jp/mansion/C001/",
                    "inputDateTime": now - datetime.timedelta(days=20),
                    "updateDateTime": now - datetime.timedelta(days=1),
                },
                {
                    "id": 202,
                    "pageUrl": "https://www.livable.co.jp/mansion/C002/",
                    "inputDateTime": now - datetime.timedelta(days=3),
                    "updateDateTime": now - datetime.timedelta(days=1),
                },
            ],
            "nomura": [
                # Delisted in PropertyEvaluation -> must NOT be re-queued!
                {
                    "id": 301,
                    "pageUrl": "https://www.nomu.com/mansion/id/DEL1/",
                    "inputDateTime": now - datetime.timedelta(days=40),
                    "updateDateTime": now - datetime.timedelta(days=40),
                },
                # Unevaluated property row older than 14d -> MUST be included!
                {
                    "id": 302,
                    "pageUrl": "https://www.nomu.com/mansion/id/UNEV1/",
                    "inputDateTime": now - datetime.timedelta(days=18),
                    "updateDateTime": now - datetime.timedelta(days=2),
                },
            ],
        }

        targets = ttl_recrawl.build_ttl_expired_targets_from_snapshots(
            eval_rows=all_evals,
            model_rows_by_entry=[
                ("mitsui", "mansion", model_rows_by_comp["mitsui"]),
                ("tokyu", "mansion", model_rows_by_comp["tokyu"]),
                ("nomura", "mansion", model_rows_by_comp["nomura"]),
            ],
            now=now,
            ttl_days=14,
        )

        urls = [t.property_url for t in targets]
        assert set(urls) == {
            "https://www.rehouse.co.jp/buy/mansion/bkdetail/EXP1/",
            "https://www.livable.co.jp/mansion/C001/",
            "https://www.nomu.com/mansion/id/UNEV1/",
        }
        assert len(urls) == 3

    def test_interleave_targets_by_company_prevents_single_domain_burst(self):
        raw = [
            ttl_recrawl.TtlTarget(property_url=f"https://a.example/{i}", company="mitsui", property_type="mansion")
            for i in range(3)
        ] + [
            ttl_recrawl.TtlTarget(property_url=f"https://b.example/{i}", company="tokyu", property_type="mansion")
            for i in range(2)
        ]
        ordered = ttl_recrawl.interleave_targets_by_company(raw)
        companies = [t.company for t in ordered]
        assert companies[:4] == ["mitsui", "tokyu", "mitsui", "tokyu"]
        assert len(ordered) == 5


class TestDirectCrawlOutcomes:
    @pytest.mark.asyncio
    async def test_delisted_url_marks_is_published_false_and_sets_delisted_at(self):
        target = ttl_recrawl.TtlTarget(
            property_url="https://www.rehouse.co.jp/buy/mansion/bkdetail/ENDED99/",
            company="mitsui",
            property_type="mansion",
            property_id=55,
        )
        fake_parser = MagicMock()
        fake_parser.property_type = "mansion"
        fake_parser.parsePropertyDetailPage = AsyncMock(
            side_effect=ListingEndedException("掲載終了")
        )

        persisted_delisted = MagicMock()
        with (
            patch("package.utils.url_router.UrlRouter.create_parser", return_value=fake_parser),
            patch.object(
                api_module.ParseDetailPageAsyncBase,
                "_sync_persist_delisted",
                persisted_delisted,
            ),
            patch.object(
                ttl_recrawl,
                "_inspect_post_crawl_outcome_sync",
                return_value="delisted",
            ),
        ):
            outcome = await ttl_recrawl.crawl_single_ttl_target(target, timeout_sec=15)

        assert outcome == "delisted"
        persisted_delisted.assert_called_once()

    @pytest.mark.asyncio
    async def test_active_url_saves_property_normally_and_refreshes_ttl(self):
        target = ttl_recrawl.TtlTarget(
            property_url="https://www.rehouse.co.jp/buy/mansion/bkdetail/ACTIVE1/",
            company="mitsui",
            property_type="mansion",
            property_id=56,
        )
        fake_item = SimpleNamespace(
            pageUrl=target.property_url,
            propertyName="テストマンション",
            price=64800000,
        )
        fake_parser = MagicMock()
        fake_parser.property_type = "mansion"
        fake_parser.parsePropertyDetailPage = AsyncMock(return_value=fake_item)

        handle_saved = AsyncMock()
        with (
            patch("package.utils.url_router.UrlRouter.create_parser", return_value=fake_parser),
            patch.object(
                api_module.ParseDetailPageAsyncBase,
                "_handle_saved_property",
                handle_saved,
            ),
            patch.object(
                ttl_recrawl,
                "_inspect_post_crawl_outcome_sync",
                return_value="refreshed",
            ),
        ):
            outcome = await ttl_recrawl.crawl_single_ttl_target(target, timeout_sec=15)

        assert outcome == "refreshed"
        handle_saved.assert_awaited_once_with(fake_item)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "transient_exc",
        [
            SiteMaintenanceException("メンテナンス中"),
            AccessBlockedException("403 WAF Blocked"),
        ],
    )
    async def test_maintenance_or_blocked_never_marks_delisted(self, transient_exc):
        target = ttl_recrawl.TtlTarget(
            property_url="https://www.mizuho-re.co.jp/buyers/mansion/detail/123/",
            company="mizuho",
            property_type="mansion",
            property_id=77,
        )
        fake_parser = MagicMock()
        fake_parser.property_type = "mansion"
        fake_parser.createEntity.return_value = SimpleNamespace()
        fake_parser.parsePropertyDetailPage = AsyncMock(side_effect=transient_exc)

        persisted_delisted = MagicMock()
        with (
            patch("package.utils.url_router.UrlRouter.create_parser", return_value=fake_parser),
            patch.object(
                api_module.ParseDetailPageAsyncBase,
                "_sync_persist_delisted",
                persisted_delisted,
            ),
            patch.object(
                ttl_recrawl,
                "_inspect_post_crawl_outcome_sync",
                return_value="transient_skipped",
            ),
        ):
            outcome = await ttl_recrawl.crawl_single_ttl_target(target, timeout_sec=15)

        assert outcome == "transient_skipped"
        persisted_delisted.assert_not_called()

    def test_overwrite_protection_still_refreshes_last_detail_fetched_at_via_integrity_tag(self):
        """Even if overwrite protection preserves old property fields, tag_property_integrity updates last_detail_fetched_at."""
        from package.utils.data_validator import apply_integrity_transition

        eval_rec = SimpleNamespace(
            last_detail_fetched_at=None,
            needs_parser_fix=False,
            needs_recrawl=False,
            heal_status="healthy",
            is_published=True,
            delisted_at=None,
            data_quality_issue="",
            failed_git_sha="",
            recrawl_attempts=0,
            first_stage_predicted_price=5000,
            second_stage_predicted_price=None,
            dcf_theoretical_price=4800,
            is_first_stage_passed=True,
        )
        ts = timezone.now()
        apply_integrity_transition(eval_rec, is_valid=True, reasons=[], now=ts)
        assert eval_rec.last_detail_fetched_at == ts
        assert eval_rec.is_published is True


class TestLocalProdInfraContext:
    def test_starts_proxysql_and_iap_tunnel_verifies_select1_and_cleans_up(self):
        fake_tunnel_proc = MagicMock()
        fake_tunnel_proc.poll.return_value = None

        port_checks = iter([False, False, True])
        status_checks = iter(["TERMINATED", "RUNNING"])

        run_calls: list[list[str]] = []

        def fake_run_cmd(cmd: list[str], **kwargs):
            run_calls.append(cmd)
            if "describe" in cmd:
                return SimpleNamespace(returncode=0, stdout=next(status_checks), stderr="")
            return SimpleNamespace(returncode=0, stdout="UPDATED", stderr="")

        with (
            patch.object(ttl_recrawl, "_run_headless_cmd", side_effect=fake_run_cmd),
            patch.object(ttl_recrawl, "_is_tcp_port_open", side_effect=lambda *a, **kw: next(port_checks)),
            patch.object(ttl_recrawl, "_spawn_iap_tunnel_process", return_value=fake_tunnel_proc) as spawn_mock,
            patch.object(ttl_recrawl, "verify_db_select_one", return_value=True) as db_verify_mock,
            patch.object(ttl_recrawl, "_run_safe_proxysql_stop_check") as safe_stop_mock,
            patch("time.sleep"),
        ):
            with ttl_recrawl.LocalProdInfraContext(
                gcloud_bin="gcloud.cmd",
                project_id="sumifu",
                zone="asia-northeast1-a",
                instance_name="proxysql-instance-prod",
                local_host="127.0.0.1",
                local_port=6033,
                stop_if_idle_on_exit=True,
            ) as ctx:
                assert ctx.started_proxysql is True
                assert ctx.started_tunnel is True

        assert any("start" in c for c in run_calls)
        spawn_mock.assert_called_once()
        db_verify_mock.assert_called_once()
        fake_tunnel_proc.terminate.assert_called_once()
        safe_stop_mock.assert_called_once()

    def test_fail_fast_when_db_select_one_fails(self):
        with (
            patch.object(
                ttl_recrawl,
                "_run_headless_cmd",
                return_value=SimpleNamespace(returncode=0, stdout="RUNNING", stderr=""),
            ),
            patch.object(ttl_recrawl, "_is_tcp_port_open", return_value=True),
            patch.object(
                ttl_recrawl,
                "verify_db_select_one",
                side_effect=OperationalError("(2002, \"Can't connect to MySQL server\")"),
            ),
        ):
            with pytest.raises(OperationalError):
                with ttl_recrawl.LocalProdInfraContext(
                    gcloud_bin="gcloud.cmd",
                    stop_if_idle_on_exit=False,
                ):
                    pass

    def test_reuses_existing_running_proxysql_and_open_tunnel_without_killing_foreign_tunnel(self):
        with (
            patch.object(
                ttl_recrawl,
                "_run_headless_cmd",
                return_value=SimpleNamespace(returncode=0, stdout="RUNNING", stderr=""),
            ),
            patch.object(ttl_recrawl, "_is_tcp_port_open", return_value=True),
            patch.object(ttl_recrawl, "_spawn_iap_tunnel_process") as spawn_mock,
            patch.object(ttl_recrawl, "verify_db_select_one", return_value=True),
            patch.object(ttl_recrawl, "_run_safe_proxysql_stop_check") as safe_stop_mock,
        ):
            with ttl_recrawl.LocalProdInfraContext(
                gcloud_bin="gcloud.cmd",
                stop_if_idle_on_exit=True,
            ) as ctx:
                assert ctx.started_proxysql is False
                assert ctx.started_tunnel is False

        spawn_mock.assert_not_called()
        # Did not start ProxySQL itself -> should not force stop check unless requested
        safe_stop_mock.assert_not_called()


class TestBatchConcurrencyAndCliMain:
    @pytest.mark.asyncio
    async def test_crawl_ttl_expired_targets_async_aggregates_stats_and_trips_circuit_breaker(self):
        targets = [
            ttl_recrawl.TtlTarget(property_url=f"https://example.com/{i}", company="mitsui", property_type="mansion")
            for i in range(5)
        ]
        outcomes = iter(["refreshed", "delisted", "error", "error", "refreshed"])

        async def fake_single(target, timeout_sec=60):
            val = next(outcomes)
            if val == "error":
                raise RuntimeError("hard boom")
            return val

        with (
            patch.object(ttl_recrawl, "crawl_single_ttl_target", side_effect=fake_single),
            patch.object(ttl_recrawl, "close_old_connections"),
        ):
            stats = await ttl_recrawl.crawl_ttl_expired_targets_async(
                targets=targets,
                concurrency=1,
                domain_concurrency=1,
                max_consecutive_failures=2,
            )

        assert stats["refreshed"] == 1
        assert stats["delisted"] == 1
        assert stats["error"] == 2
        assert stats["skipped_by_circuit_breaker"] == 1

    def test_main_dry_run_with_local_prod_infra_prints_json_summary(self, capsys):
        sample_targets = [
            ttl_recrawl.TtlTarget(property_url="https://example.com/1", company="mitsui", property_type="mansion"),
            ttl_recrawl.TtlTarget(property_url="https://example.com/2", company="tokyu", property_type="kodate"),
        ]
        with (
            patch.object(
                ttl_recrawl,
                "_run_headless_cmd",
                return_value=SimpleNamespace(returncode=0, stdout="RUNNING", stderr=""),
            ),
            patch.object(ttl_recrawl, "_is_tcp_port_open", return_value=True),
            patch.object(ttl_recrawl, "verify_db_select_one", return_value=True),
            patch.object(ttl_recrawl, "collect_ttl_expired_targets", return_value=sample_targets),
        ):
            rc = ttl_recrawl.main(["--ensure-local-prod-infra", "--dry-run", "--ttl-days", "14"])

        assert rc == 0
        out = capsys.readouterr().out.strip().splitlines()[-1]
        import json

        data = json.loads(out)
        assert data["ttl_days"] == 14
        assert data["target_count"] == 2
        assert data["dry_run"] is True
        assert data["by_company"] == {"mitsui": 1, "tokyu": 1}

    def test_main_live_run_invokes_async_crawler(self, capsys):
        sample_targets = [
            ttl_recrawl.TtlTarget(property_url="https://example.com/1", company="mitsui", property_type="mansion"),
        ]
        with (
            patch.object(ttl_recrawl, "verify_db_select_one", return_value=True),
            patch.object(ttl_recrawl, "collect_ttl_expired_targets", return_value=sample_targets),
            patch.object(
                ttl_recrawl,
                "crawl_ttl_expired_targets_async",
                new=AsyncMock(return_value={"delisted": 1}),
            ),
        ):
            rc = ttl_recrawl.main(["--ttl-days", "14", "--limit", "1"])

        assert rc == 0
        out = capsys.readouterr().out.strip().splitlines()[-1]
        import json

        data = json.loads(out)
        assert data["stats"] == {"delisted": 1}

    def test_collect_ttl_expired_targets_queries_orm_and_respects_limit(self):
        now = datetime.datetime(2026, 11, 14, 12, 0, tzinfo=datetime.UTC)
        fake_eval_qs = MagicMock()
        fake_eval_qs.filter.return_value = fake_eval_qs
        fake_eval_qs.values.return_value.iterator.return_value = [
            {
                "id": 1,
                "property_url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/E1/",
                "company": "mitsui",
                "property_type": "mansion",
                "property_id": 10,
                "is_published": True,
                "last_detail_fetched_at": now - datetime.timedelta(days=20),
            },
            {
                "id": 2,
                "property_url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/E2/",
                "company": "mitsui",
                "property_type": "mansion",
                "property_id": 11,
                "is_published": True,
                "last_detail_fetched_at": now - datetime.timedelta(days=21),
            },
        ]
        fake_model_cls = MagicMock()
        fake_model_cls.objects.values.return_value.iterator.return_value = [
            {
                "id": 10,
                "pageUrl": "https://www.rehouse.co.jp/buy/mansion/bkdetail/E1/",
                "inputDateTime": now - datetime.timedelta(days=20),
                "updateDateTime": now - datetime.timedelta(days=1),
            }
        ]

        with (
            patch("django.utils.timezone.now", return_value=now),
            patch.object(ttl_recrawl.PropertyEvaluation.objects, "all", return_value=fake_eval_qs),
            patch.object(
                ttl_recrawl.SiteRegistry,
                "get_all_property_model_entries",
                return_value=[(fake_model_cls, "mitsui", "mansion")],
            ),
        ):
            res = ttl_recrawl.collect_ttl_expired_targets(ttl_days=14, company="mitsui", limit=1)

        assert len(res) == 1
        assert res[0].company == "mitsui"

    def test_inspect_post_crawl_outcome_sync_covers_all_branches(self):
        url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/BRANCH1/"

        def _run_with_eval(eval_obj, item_obj):
            qs = MagicMock()
            qs.first.return_value = eval_obj
            with patch.object(ttl_recrawl.PropertyEvaluation.objects, "filter", return_value=qs):
                return ttl_recrawl._inspect_post_crawl_outcome_sync(url, item_obj)

        assert _run_with_eval(SimpleNamespace(is_published=False), None) == "delisted"
        assert (
            _run_with_eval(
                SimpleNamespace(is_published=True, needs_parser_fix=True, needs_recrawl=False),
                SimpleNamespace(),
            )
            == "invalid_saved"
        )
        assert (
            _run_with_eval(
                SimpleNamespace(is_published=True, needs_parser_fix=False, needs_recrawl=False),
                SimpleNamespace(),
            )
            == "refreshed"
        )
        assert (
            _run_with_eval(
                SimpleNamespace(is_published=True, needs_parser_fix=True, needs_recrawl=False),
                None,
            )
            == "parser_failed"
        )
        assert (
            _run_with_eval(
                SimpleNamespace(is_published=True, needs_parser_fix=False, needs_recrawl=False),
                None,
            )
            == "transient_skipped"
        )

    @pytest.mark.asyncio
    async def test_crawl_single_ttl_target_returns_unresolved_url_when_no_parser(self):
        target = ttl_recrawl.TtlTarget(
            property_url="https://unknown.invalid/item/1",
            company="unknown",
            property_type="unknown",
        )
        with patch("package.utils.url_router.UrlRouter.create_parser", return_value=None):
            res = await ttl_recrawl.crawl_single_ttl_target(target)
        assert res == "unresolved_url"

    def test_low_level_infra_helpers(self):
        assert isinstance(ttl_recrawl._resolve_gcloud_binary("gcloud.cmd"), str)
        assert ttl_recrawl._resolve_gcloud_binary("gcloud.cmd") == "gcloud.cmd"

        with patch("socket.socket") as sock_cls:
            sock_inst = MagicMock()
            sock_inst.connect_ex.return_value = 0
            sock_cls.return_value = sock_inst
            assert ttl_recrawl._is_tcp_port_open("127.0.0.1", 6033) is True
            sock_inst.close.assert_called_once()

        with patch("subprocess.Popen") as popen_mock:
            ttl_recrawl._spawn_iap_tunnel_process(
                "gcloud.cmd", "sumifu", "asia-northeast1-a", "proxysql-instance-prod", "127.0.0.1", 6033
            )
            popen_mock.assert_called_once()

        with (
            patch.object(ttl_recrawl, "close_old_connections"),
            patch.object(ttl_recrawl, "connection") as conn_mock,
        ):
            cur = MagicMock()
            cur.fetchone.return_value = (1,)
            conn_mock.cursor.return_value.__enter__.return_value = cur
            assert ttl_recrawl.verify_db_select_one() is True



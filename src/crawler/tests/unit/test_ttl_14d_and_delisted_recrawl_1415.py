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
        assert ctx._tunnel_err_fp is None
        assert ctx._tunnel_err_path is None
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
            popen_kwargs = popen_mock.call_args.kwargs
            assert popen_kwargs.get("stderr") is not ttl_recrawl.subprocess.PIPE

        with (
            patch.object(ttl_recrawl, "close_old_connections"),
            patch.object(ttl_recrawl, "connection") as conn_mock,
        ):
            cur = MagicMock()
            cur.fetchone.return_value = (1,)
            conn_mock.cursor.return_value.__enter__.return_value = cur
            assert ttl_recrawl.verify_db_select_one() is True


class TestIssue1421ColdBootAndWorkerPool:
    def test_collect_ttl_expired_targets_retries_on_transient_lost_connection_2013(self):
        now = datetime.datetime(2026, 11, 14, 12, 0, tzinfo=datetime.UTC)
        attempts = {"count": 0}

        def flaky_eval_iterator(*args, **kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise OperationalError(2013, "Lost connection to server during query")
            return iter(
                [
                    {
                        "id": 10,
                        "property_url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/RETRY2013/",
                        "company": "mitsui",
                        "property_type": "mansion",
                        "property_id": 99,
                        "is_published": True,
                        "last_detail_fetched_at": now - datetime.timedelta(days=20),
                    }
                ]
            )

        fake_eval_qs = MagicMock()
        fake_eval_qs.filter.return_value = fake_eval_qs
        fake_eval_qs.values.return_value.iterator.side_effect = flaky_eval_iterator

        fake_model_cls = MagicMock()
        fake_model_cls.objects.values.return_value.iterator.return_value = iter([])

        with (
            patch("django.utils.timezone.now", return_value=now),
            patch.object(ttl_recrawl.PropertyEvaluation.objects, "all", return_value=fake_eval_qs),
            patch.object(
                ttl_recrawl.SiteRegistry,
                "get_all_property_model_entries",
                return_value=[(fake_model_cls, "mitsui", "mansion")],
            ),
            patch.object(ttl_recrawl, "connection") as conn_mock,
            patch("time.sleep") as sleep_mock,
        ):
            targets = ttl_recrawl.collect_ttl_expired_targets(ttl_days=14, company="mitsui")

        assert attempts["count"] == 2
        conn_mock.close.assert_called()
        sleep_mock.assert_called_once()
        assert len(targets) == 1
        assert targets[0].property_url == "https://www.rehouse.co.jp/buy/mansion/bkdetail/RETRY2013/"

    def test_local_prod_infra_restarts_dropped_iap_tunnel_and_sets_gcs_defaults(self, monkeypatch):
        monkeypatch.delenv("STORAGE_BACKEND", raising=False)
        monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)

        first_proc = MagicMock()
        # Alive during startup, then exited (rc=1) when watchdog checks
        first_proc.poll.side_effect = [None, 1, 1]
        first_proc.returncode = 1

        second_proc = MagicMock()
        second_proc.poll.return_value = None

        port_checks = iter([False, True, False, True])

        with (
            patch.object(
                ttl_recrawl,
                "_run_headless_cmd",
                return_value=SimpleNamespace(returncode=0, stdout="RUNNING", stderr=""),
            ),
            patch.object(ttl_recrawl, "_is_tcp_port_open", side_effect=lambda *a, **kw: next(port_checks)),
            patch.object(
                ttl_recrawl,
                "_spawn_iap_tunnel_process",
                side_effect=[first_proc, second_proc],
            ) as spawn_mock,
            patch.object(ttl_recrawl, "verify_db_select_one", return_value=True),
            patch("time.sleep"),
        ):
            with ttl_recrawl.LocalProdInfraContext(
                gcloud_bin="gcloud.cmd",
                stop_if_idle_on_exit=False,
                enable_tunnel_watchdog=False,
            ) as ctx:
                import os

                assert os.environ.get("STORAGE_BACKEND") == "gcs"
                assert os.environ.get("GCS_BUCKET_NAME") == "realestate-images-sumifu-prod"
                restarted = ctx.ensure_tunnel_alive()
                assert restarted is True

        assert spawn_mock.call_count == 2
        second_proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_ttl_expired_targets_async_uses_bounded_worker_pool_and_shared_session(self):
        import asyncio

        targets = [
            ttl_recrawl.TtlTarget(
                property_url=f"https://example.com/{i}",
                company=f"comp_{i % 5}",
                property_type="mansion",
            )
            for i in range(40)
        ]
        active_workers = 0
        peak_active_workers = 0
        received_sessions: list[object] = []

        async def fake_single(target, timeout_sec=60, session=None):
            nonlocal active_workers, peak_active_workers
            active_workers += 1
            peak_active_workers = max(peak_active_workers, active_workers)
            received_sessions.append(session)
            await asyncio.sleep(0.002)
            active_workers -= 1
            return "refreshed"

        with (
            patch.object(ttl_recrawl, "crawl_single_ttl_target", side_effect=fake_single),
            patch.object(ttl_recrawl, "close_old_connections"),
        ):
            stats = await ttl_recrawl.crawl_ttl_expired_targets_async(
                targets=targets,
                concurrency=4,
                domain_concurrency=2,
            )

        assert stats == {"refreshed": 40}
        assert 1 <= peak_active_workers <= 4
        assert all(s is not None for s in received_sessions)
        assert len({id(s) for s in received_sessions}) == 1


class TestIssue1424SplitPoolsAndParallelDb:
    @pytest.mark.asyncio
    async def test_split_targets_isolates_playwright_and_static_pools_without_head_of_line_blocking(self):
        import asyncio
        import time

        # Put slow Playwright targets FIRST so a shared single pool of size 4 would stall behind athome!
        pw_targets = [
            ttl_recrawl.TtlTarget(
                property_url=f"https://www.athome.co.jp/mansion/{i}",
                company="athome",
                property_type="mansion",
            )
            for i in range(6)
        ]
        static_targets = [
            ttl_recrawl.TtlTarget(
                property_url=f"https://www.rehouse.co.jp/buy/mansion/{i}",
                company=f"static_{i % 6}",
                property_type="mansion",
            )
            for i in range(24)
        ]
        all_targets = pw_targets + static_targets

        static_done_mono: float = 0.0
        static_completed = 0
        pw_in_flight = 0
        peak_pw_in_flight = 0
        started = time.monotonic()

        async def fake_single(target, timeout_sec=60, session=None, db_runner=None, domain_concurrency=3):
            nonlocal static_done_mono, static_completed, pw_in_flight, peak_pw_in_flight
            if target.company in ttl_recrawl.PLAYWRIGHT_HEAVY_COMPANIES:
                pw_in_flight += 1
                peak_pw_in_flight = max(peak_pw_in_flight, pw_in_flight)
                await asyncio.sleep(0.06)
                pw_in_flight -= 1
                return "delisted"

            await asyncio.sleep(0.003)
            static_completed += 1
            if static_completed == len(static_targets):
                static_done_mono = time.monotonic() - started
            return "refreshed"

        with (
            patch.object(ttl_recrawl, "crawl_single_ttl_target", side_effect=fake_single),
            patch.object(ttl_recrawl, "close_old_connections"),
        ):
            stats = await ttl_recrawl.crawl_ttl_expired_targets_async(
                targets=all_targets,
                concurrency=8,
                domain_concurrency=2,
                playwright_concurrency=1,
                db_concurrency=4,
            )

        assert stats == {"refreshed": 24, "delisted": 6}
        assert peak_pw_in_flight == 1
        # 6 athome targets at 0.06s with playwright_concurrency=1 take >=0.36s total,
        # whereas all 24 static targets finish well under 0.15s because pools are isolated!
        assert 0.0 < static_done_mono < 0.18

    @pytest.mark.asyncio
    async def test_bounded_db_executor_runs_concurrently_off_main_thread_and_closes_connections(self):
        import asyncio
        import threading
        import time

        main_tid = threading.get_ident()
        lock = threading.Lock()
        in_flight = 0
        peak_in_flight = 0
        worker_tids: set[int] = set()
        closed_tids: set[int] = set()

        def slow_db_op(idx: int) -> int:
            nonlocal in_flight, peak_in_flight
            tid = threading.get_ident()
            with lock:
                worker_tids.add(tid)
                in_flight += 1
                peak_in_flight = max(peak_in_flight, in_flight)
            time.sleep(0.04)
            with lock:
                in_flight -= 1
            return idx * 2

        def fake_conn_close_all() -> None:
            with lock:
                closed_tids.add(threading.get_ident())

        with patch.object(ttl_recrawl.connections, "close_all", side_effect=fake_conn_close_all):
            db_runner = ttl_recrawl._BoundedDbExecutor(max_workers=4)
            results = await asyncio.gather(*(db_runner.run(slow_db_op, i) for i in range(8)))
            await db_runner.aclose()

        assert results == [i * 2 for i in range(8)]
        assert main_tid not in worker_tids
        assert peak_in_flight >= 2
        assert peak_in_flight <= 4
        # Every DB worker thread that touched Django ORM had connections.close_all() invoked on shutdown
        assert worker_tids.issubset(closed_tids)

    @pytest.mark.asyncio
    async def test_ttl_direct_detail_proc_persists_active_item_via_db_runner_with_price_revision(self):
        class _FakePropertyModel:
            objects = MagicMock()

            def __init__(self, page_url: str) -> None:
                self.id = None
                self.pageUrl = page_url
                self.propertyName = "DB並列マンション"
                self.price = 62000000
                self.inputDate = None
                self.inputDateTime = None
                self.updateDateTime = None
                self._state = SimpleNamespace(adding=True)

        target = ttl_recrawl.TtlTarget(
            property_url="https://www.rehouse.co.jp/buy/mansion/bkdetail/DB1/",
            company="mitsui",
            property_type="mansion",
            property_id=101,
        )
        fake_item = _FakePropertyModel(target.property_url)
        existing_rec = SimpleNamespace(
            id=101,
            price=65000000,
            inputDate=datetime.date(2026, 10, 1),
            inputDateTime=datetime.datetime(2026, 10, 1, 9, 0),
        )
        db_runner = ttl_recrawl._BoundedDbExecutor(max_workers=2)
        proc = ttl_recrawl.TtlDirectDetailProc(
            target=target,
            resolved_parser=MagicMock(),
            timeout_sec=15,
            db_runner=db_runner,
            domain_concurrency=3,
        )
        saved_mock = MagicMock()
        tagged_mock = MagicMock()
        price_rev_mock = MagicMock()

        try:
            with (
                patch.object(ttl_recrawl.UrlMatcher, "find_match_in_queryset", return_value=existing_rec),
                patch.object(proc, "_should_preserve_existing_valid_record", return_value=(False, [])),
                patch.object(proc, "_save_item_record_with_duplicate_fallback", saved_mock),
                patch.object(proc, "_tag_integrity_sync", tagged_mock),
                patch.object(ttl_recrawl.PropertyPriceHistory.objects, "create", price_rev_mock),
                patch.object(ttl_recrawl.connections, "close_all"),
            ):
                await proc._save_property_and_price_history(fake_item)
        finally:
            await db_runner.aclose()

        assert fake_item.id == 101
        price_rev_mock.assert_called_once()
        saved_mock.assert_called_once()
        tagged_mock.assert_called_once_with(fake_item)

    @pytest.mark.asyncio
    async def test_ttl_db_batch_buffer_flushes_at_100_items_and_flushes_remainder(self):
        import asyncio
        import time

        flushed_sizes: list[int] = []

        def fake_flush(chunk, batch_size=100):
            flushed_sizes.append(len(chunk))
            return ["delisted" if e.kind == "delisted" else "refreshed" for e in chunk]

        stats_lock = asyncio.Lock()
        state = ttl_recrawl._BatchRunState(
            total=235,
            max_consecutive_failures=25,
            started_mono=time.monotonic(),
            stats={},
        )
        db_runner = ttl_recrawl._BoundedDbExecutor(max_workers=2)
        buf = ttl_recrawl._TtlDbBatchBuffer(
            db_runner=db_runner,
            stats_lock=stats_lock,
            state=state,
            batch_size=100,
        )

        try:
            with (
                patch.object(ttl_recrawl, "_flush_fetched_batch_with_retry", side_effect=fake_flush),
                patch.object(ttl_recrawl.connections, "close_all"),
            ):
                for idx in range(235):
                    t = ttl_recrawl.TtlTarget(
                        property_url=f"https://example.com/item/{idx}",
                        company="mitsui",
                        property_type="mansion",
                    )
                    kind = "delisted" if idx % 5 == 0 else "active"
                    await buf.add(ttl_recrawl._FetchedOutcomeItem(target=t, kind=kind))
                await buf.flush_remaining()
        finally:
            await db_runner.aclose()

        assert flushed_sizes == [100, 100, 35]
        assert state.completed == 235
        assert state.stats["delisted"] == 47
        assert state.stats["refreshed"] == 188

    def test_flush_fetched_batch_sync_once_bulk_updates_delisted_and_active_records(self):
        class _DummyModel:
            objects = MagicMock()
            _meta = SimpleNamespace(
                concrete_fields=[
                    SimpleNamespace(name="id", primary_key=True),
                    SimpleNamespace(name="pageUrl", primary_key=False),
                    SimpleNamespace(name="price", primary_key=False),
                ]
            )

        existing_prop = _DummyModel()
        existing_prop.id = 10
        existing_prop.pk = 10
        existing_prop.pageUrl = "https://www.rehouse.co.jp/buy/mansion/bkdetail/ACT1/"
        existing_prop.price = 55000000
        existing_prop.inputDate = datetime.date(2026, 9, 1)
        existing_prop.inputDateTime = datetime.datetime(2026, 9, 1, 9, 0)
        _DummyModel.objects.filter.return_value = [existing_prop]

        new_prop = _DummyModel()
        new_prop.id = None
        new_prop.pageUrl = existing_prop.pageUrl
        new_prop.propertyName = "一括更新マンション"
        new_prop.price = 52000000
        new_prop.address = "東京都港区六本木1-1-1"
        new_prop.traffic = "東京メトロ日比谷線 六本木駅 徒歩4分"
        new_prop.senyuMenseki = 65.0
        new_prop.kaisuStr = "5階"
        new_prop.madori = "2LDK"
        new_prop.chikunengetsuStr = "2015年3月"
        new_prop._state = SimpleNamespace(adding=True)

        eval_active = SimpleNamespace(
            pk=501,
            property_url=existing_prop.pageUrl,
            company="mitsui",
            property_type="mansion",
            property_id=10,
            is_published=True,
            delisted_at=None,
            needs_parser_fix=False,
            needs_recrawl=False,
            data_quality_issue="",
            heal_status="healthy",
            failed_git_sha="",
            recrawl_attempts=0,
            last_detail_fetched_at=None,
            first_stage_predicted_price=5400,
            second_stage_predicted_price=None,
            dcf_theoretical_price=5300,
            is_first_stage_passed=True,
        )
        eval_delisted = SimpleNamespace(
            pk=502,
            property_url="https://www.rehouse.co.jp/buy/mansion/bkdetail/DEL1/",
            company="mitsui",
            property_type="mansion",
            property_id=11,
            is_published=True,
            delisted_at=None,
            needs_parser_fix=False,
            needs_recrawl=True,
            data_quality_issue="",
            heal_status="healthy",
            failed_git_sha="",
            recrawl_attempts=0,
            last_detail_fetched_at=None,
            first_stage_predicted_price=None,
            second_stage_predicted_price=None,
            dcf_theoretical_price=None,
            is_first_stage_passed=False,
        )

        batch = [
            ttl_recrawl._FetchedOutcomeItem(
                target=ttl_recrawl.TtlTarget(
                    property_url=existing_prop.pageUrl,
                    company="mitsui",
                    property_type="mansion",
                    property_id=10,
                ),
                kind="active",
                item=new_prop,
            ),
            ttl_recrawl._FetchedOutcomeItem(
                target=ttl_recrawl.TtlTarget(
                    property_url=eval_delisted.property_url,
                    company="mitsui",
                    property_type="mansion",
                    property_id=11,
                ),
                kind="delisted",
            ),
        ]

        with (
            patch.object(
                ttl_recrawl.PropertyEvaluation.objects,
                "filter",
                return_value=[eval_active, eval_delisted],
            ),
            patch.object(ttl_recrawl.PropertyEvaluation.objects, "bulk_update") as eval_bulk_upd,
            patch.object(ttl_recrawl.PropertyEvaluation.objects, "bulk_create"),
            patch.object(ttl_recrawl.PropertyPriceHistory.objects, "bulk_create") as hist_bulk_create,
            patch.object(ttl_recrawl.ParseDetailPageAsyncBase, "_detect_company_name", return_value="mitsui"),
            patch.object(ttl_recrawl.PropertyTypeDetector, "detect_from_object", return_value="mansion"),
        ):
            outcomes = ttl_recrawl._flush_fetched_batch_sync_once(batch, batch_size=100)

        assert outcomes == ["refreshed", "delisted"]
        _DummyModel.objects.bulk_update.assert_called_once()
        hist_bulk_create.assert_called_once()
        eval_bulk_upd.assert_called_once()
        assert eval_delisted.is_published is False
        assert eval_delisted.delisted_at is not None
        assert eval_active.last_detail_fetched_at is not None


class TestIssue1427ConcurrencyDefaultsAndStopAtJst:
    def test_tuned_concurrency_defaults(self):
        parser = ttl_recrawl.build_arg_parser()
        args = parser.parse_args([])
        assert args.concurrency == 40
        assert args.domain_concurrency == 3
        assert args.playwright_concurrency == 2
        assert args.db_concurrency == 8
        assert args.db_batch_size == 100
        assert args.stop_at_jst is None
        assert args.stop_proxysql_on_exit is False

    def test_compute_next_jst_deadline_rolls_to_next_day_when_past(self):
        # 2026-11-14 21:30 JST -> next 00:50 JST is 2026-11-15 00:50 JST
        now_jst = datetime.datetime(2026, 11, 14, 21, 30, 0, tzinfo=ttl_recrawl.JST)
        deadline_evening = ttl_recrawl.compute_next_jst_deadline("00:50", now_utc=now_jst.astimezone(datetime.UTC))
        assert deadline_evening.astimezone(ttl_recrawl.JST) == datetime.datetime(
            2026, 11, 15, 0, 50, 0, tzinfo=ttl_recrawl.JST
        )

        # 2026-11-15 00:10 JST -> next 00:50 JST is same day 2026-11-15 00:50 JST
        now_early = datetime.datetime(2026, 11, 15, 0, 10, 0, tzinfo=ttl_recrawl.JST)
        deadline_early = ttl_recrawl.compute_next_jst_deadline("00:50", now_utc=now_early.astimezone(datetime.UTC))
        assert deadline_early.astimezone(ttl_recrawl.JST) == datetime.datetime(
            2026, 11, 15, 0, 50, 0, tzinfo=ttl_recrawl.JST
        )

        with pytest.raises(ValueError, match="HH:MM"):
            ttl_recrawl.compute_next_jst_deadline("25:99")

    @pytest.mark.asyncio
    async def test_deadline_reached_stops_popping_new_targets_and_flushes_buffered_items(self):
        targets = [
            ttl_recrawl.TtlTarget(
                property_url=f"https://www.rehouse.co.jp/buy/mansion/bkdetail/DL{i}/",
                company="mitsui",
                property_type="mansion",
            )
            for i in range(6)
        ]
        fetched_urls: list[str] = []
        past_deadline = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=5)

        async def _fake_crawl_single(target, timeout_sec=60):
            fetched_urls.append(target.property_url)
            return "refreshed"

        with patch.object(ttl_recrawl, "crawl_single_ttl_target", side_effect=_fake_crawl_single):
            stats = await ttl_recrawl.crawl_ttl_expired_targets_async(
                targets=targets,
                concurrency=2,
                domain_concurrency=2,
                db_batch_size=1,
                deadline_utc=past_deadline,
            )

        assert fetched_urls == []
        assert stats.get("deadline_skipped") == 6

    def test_stop_proxysql_on_exit_runs_stop_check_with_skip_traffic_even_when_already_running(self):
        with (
            patch.object(ttl_recrawl.LocalProdInfraContext, "_get_proxysql_status", return_value="RUNNING"),
            patch.object(ttl_recrawl, "_is_tcp_port_open", return_value=True),
            patch.object(ttl_recrawl, "verify_db_select_one", return_value=True),
            patch.object(ttl_recrawl, "_run_safe_proxysql_stop_check") as stop_mock,
        ):
            with ttl_recrawl.LocalProdInfraContext(
                gcloud_bin="gcloud.cmd",
                stop_if_idle_on_exit=True,
                force_stop_proxysql_on_exit=True,
            ):
                pass

        stop_mock.assert_called_once_with(skip_traffic_check=True)

    def test_ensure_resources_stopped_skip_traffic_check_stops_instance_despite_recent_local_traffic(self):
        from scripts import ensure_resources_stopped as ers

        with (
            patch.object(ers, "_get_instance_info", return_value=("RUNNING", "", 1800.0)),
            patch.object(ers, "_get_active_cloud_run_executions", return_value=([], "")),
            patch.object(ers, "_get_instance_network_received_bytes") as traffic_mock,
            patch.object(ers, "_stop_instance", return_value="") as stop_inst_mock,
            patch.object(ers, "send_slack_alert"),
        ):
            res = ers.check_and_stop_proxysql_instance(
                project_id="sumifu",
                zone="asia-northeast1-a",
                instance_name="proxysql-instance-prod",
                grace_period_sec=0.0,
                skip_traffic_check=True,
            )

        assert res.forced_stop is True
        traffic_mock.assert_not_called()
        stop_inst_mock.assert_called_once_with("sumifu", "asia-northeast1-a", "proxysql-instance-prod")


class TestIssue1430SiteSpecificConcurrencyLimits:
    def test_weak_domain_concurrency_default_and_resolution(self):
        parser = ttl_recrawl.build_arg_parser()
        args = parser.parse_args([])
        assert args.weak_domain_concurrency == 2

        # High-capacity portal / top-4 major brokers -> 3
        for strong in ("homes", "mitsui", "sumifu", "tokyu", "nomura"):
            assert (
                ttl_recrawl.resolve_company_domain_concurrency(
                    strong,
                    domain_concurrency=3,
                    weak_domain_concurrency=2,
                    playwright_concurrency=2,
                )
                == 3
            )

        # Weak / slower servers -> 2
        for weak in ("sotetsu", "odakyu", "sumai1", "sumirin", "misawa", "reguide", "daiwa", "toho"):
            assert (
                ttl_recrawl.resolve_company_domain_concurrency(
                    weak,
                    domain_concurrency=3,
                    weak_domain_concurrency=2,
                    playwright_concurrency=2,
                )
                == 2
            )

        # Single-concurrency fragile servers (Issue #1435: ietan) -> 1
        assert (
            ttl_recrawl.resolve_company_domain_concurrency(
                "ietan",
                domain_concurrency=3,
                weak_domain_concurrency=2,
                playwright_concurrency=2,
            )
            == 1
        )

        # Playwright sites -> capped by playwright_concurrency (2)
        for pw in ("athome", "mizuho", "sekisui", "smtrc", "kenbiya"):
            assert (
                ttl_recrawl.resolve_company_domain_concurrency(
                    pw,
                    domain_concurrency=3,
                    weak_domain_concurrency=2,
                    playwright_concurrency=2,
                )
                == 2
            )

    @pytest.mark.asyncio
    async def test_crawl_caps_weak_server_at_2_while_allowing_strong_server_at_3(self):
        import asyncio

        targets = [
            *(
                ttl_recrawl.TtlTarget(
                    property_url=f"https://www.rehouse.co.jp/buy/mansion/bkdetail/M{i}/",
                    company="mitsui",
                    property_type="mansion",
                )
                for i in range(6)
            ),
            *(
                ttl_recrawl.TtlTarget(
                    property_url=f"https://www.sotetsu-re.co.jp/buy/detail/S{i}/",
                    company="sotetsu",
                    property_type="mansion",
                )
                for i in range(6)
            ),
        ]
        in_flight: dict[str, int] = {"mitsui": 0, "sotetsu": 0}
        peak: dict[str, int] = {"mitsui": 0, "sotetsu": 0}
        seen_proc_limits: dict[str, set[int]] = {"mitsui": set(), "sotetsu": set()}

        async def _fake_crawl_single(
            target,
            timeout_sec=60,
            session=None,
            db_runner=None,
            domain_concurrency=3,
        ):
            comp = target.company
            seen_proc_limits[comp].add(domain_concurrency)
            in_flight[comp] += 1
            peak[comp] = max(peak[comp], in_flight[comp])
            await asyncio.sleep(0.05)
            in_flight[comp] -= 1
            return "refreshed"

        with patch.object(ttl_recrawl, "crawl_single_ttl_target", side_effect=_fake_crawl_single):
            stats = await ttl_recrawl.crawl_ttl_expired_targets_async(
                targets=targets,
                concurrency=12,
                domain_concurrency=3,
                weak_domain_concurrency=2,
                playwright_concurrency=2,
                db_batch_size=1,
            )

        assert stats["refreshed"] == 12
        assert peak["mitsui"] == 3
        assert peak["sotetsu"] <= 2
        assert peak["sotetsu"] == 2
        assert seen_proc_limits["mitsui"] == {3}
        assert seen_proc_limits["sotetsu"] == {2}

    def test_exclude_company_filters_evaluations_and_unevaluated_models(self):
        now = datetime.datetime(2026, 11, 14, 12, 0, tzinfo=datetime.UTC)
        old_dt = now - datetime.timedelta(days=20)
        eval_rows = [
            {
                "id": 1,
                "property_url": "https://www.ietan.jp/mansion/detail/IE1",
                "company": "ietan",
                "property_type": "mansion",
                "property_id": 10,
                "is_published": True,
                "last_detail_fetched_at": old_dt,
            },
            {
                "id": 2,
                "property_url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/M1/",
                "company": "mitsui",
                "property_type": "mansion",
                "property_id": 20,
                "is_published": True,
                "last_detail_fetched_at": old_dt,
            },
        ]
        model_rows = [
            (
                "ietan",
                "mansion",
                [{"id": 11, "pageUrl": "https://www.ietan.jp/mansion/detail/IE2", "inputDateTime": old_dt, "updateDateTime": old_dt}],
            ),
            (
                "sumifu",
                "mansion",
                [{"id": 21, "pageUrl": "https://www.stepon.co.jp/mansion/detail_S1/", "inputDateTime": old_dt, "updateDateTime": old_dt}],
            ),
        ]
        targets = ttl_recrawl.build_ttl_expired_targets_from_snapshots(
            eval_rows=eval_rows,
            model_rows_by_entry=model_rows,
            now=now,
            ttl_days=14,
            exclude_companies={"ietan"},
        )
        companies = [t.company for t in targets]
        assert "ietan" not in companies
        assert set(companies) == {"mitsui", "sumifu"}

        parser = ttl_recrawl.build_arg_parser()
        args = parser.parse_args(["--exclude-company", "ietan"])
        assert args.exclude_company == "ietan"

    def test_shared_session_default_headers_match_http_client_optimized_headers(self):
        from package.utils.http_client import DEFAULT_HEADERS

        assert ttl_recrawl.DEFAULT_HTTP_HEADERS == DEFAULT_HEADERS
        assert "Accept" in ttl_recrawl.DEFAULT_HTTP_HEADERS
        assert "Accept-Language" in ttl_recrawl.DEFAULT_HTTP_HEADERS
        assert "Chrome/124.0.0.0" in ttl_recrawl.DEFAULT_HTTP_HEADERS["User-Agent"]











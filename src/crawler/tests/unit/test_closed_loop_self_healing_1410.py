# -*- coding: utf-8 -*-
"""
Unit tests for Issue #1410: Closed-Loop Self-Healing Architecture.

Covers:
1. PropertyEvaluation self-healing state machine fields & Migration 0073 idempotency.
2. SiteRegistry 100% dynamic model resolution across all 30+ companies & invest_kodate aliases.
3. Integrity transitions (preserving is_slack_notified, invalidating predictions on anomaly,
   creating PropertyEvaluation when missing in validate_data, recrawled_pending_ml -> healthy ML re-eval).
4. differential.py true 30-day detail TTL (immune to updateDateTime skip resets) & SHA-aware anomaly refetch.
5. recrawl_anomalies.py PK modulo distribution for property_id=0, --skip-same-sha, source_data_invalid escalation,
   and cross-table orphan cleanup on property-type switch.
6. auto_heal_parsers.py property_id=0 extraction & GCS instruction sync/pull, monitor_error_pages.py pathlib+GCS,
   run_ml_pipeline.py automated recrawl + resilient auto-heal invocation, and deploy-production.yml wiring.
"""
from __future__ import annotations

import asyncio
import datetime
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

import setup_env  # noqa: F401
from package.api.differential import ListItem, _should_fetch_item
from package.ml.evaluation.record_builder import build_or_update_eval_record
from package.ml.evaluation.targets import _should_skip_item
from package.models.evaluation import PropertyEvaluation
from package.site_registry import SiteRegistry
from package.utils.data_validator import apply_integrity_transition
from scripts.debug_tools import auto_heal_parsers
from scripts.maintenance import recrawl_anomalies, validate_data
from scripts.ops import monitor_error_pages, run_ml_pipeline

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_property_evaluation_has_self_healing_fields_and_migration_0073():
    """AC2: PropertyEvaluation defines self-healing lifecycle fields and migration 0073 exists."""
    field_names = {f.name for f in PropertyEvaluation._meta.get_fields()}
    expected = {
        "heal_status",
        "failed_git_sha",
        "recrawl_attempts",
        "last_recrawled_at",
        "last_detail_fetched_at",
    }
    assert expected.issubset(field_names), f"Missing fields: {expected - field_names}"

    inst = PropertyEvaluation(
        company="mitsui",
        property_type="mansion",
        property_id=1,
        property_url="https://www.rehouse.co.jp/buy/mansion/bkdetail/TEST1/",
    )
    assert inst.heal_status == "healthy"
    assert inst.failed_git_sha == ""
    assert inst.recrawl_attempts == 0

    mig_path = REPO_ROOT / "src" / "crawler" / "package" / "migrations" / "0073_add_self_healing_lifecycle_fields.py"
    assert mig_path.exists(), f"Migration file missing: {mig_path}"


def test_site_registry_resolves_all_companies_and_invest_kodate_aliases():
    """AC3: SiteRegistry resolves all 30+ companies without 7-company/9-company hardcoding."""
    entries = SiteRegistry.get_all_property_model_entries()
    companies = {comp for _, comp, _ in entries}
    assert len(companies) >= 28
    for must_have in ("mitsui", "smtrc", "sumai1", "mizuho", "sekisui", "haseko", "ietan", "adcast", "toho", "reguide", "kenbiya"):
        assert must_have in companies, f"{must_have} missing from get_all_property_model_entries()"

    # Every registered crawl job must resolve to a concrete Django model class
    unresolved = []
    for comp, ptype in SiteRegistry.get_all_jobs():
        if SiteRegistry.resolve_model_class(comp, ptype) is None:
            unresolved.append((comp, ptype))
    assert unresolved == [], f"Unresolved crawl jobs in SiteRegistry: {unresolved}"

    # Alias resolution for invest_kodate / investment_kodate / apartment
    m_inv_k = SiteRegistry.resolve_model_class("mitsui", "invest_kodate")
    assert m_inv_k is not None and m_inv_k.__name__ == "MitsuiInvestmentKodate"
    assert SiteRegistry.resolve_model_class("mitsui", "investment_kodate") is m_inv_k
    assert SiteRegistry.resolve_model_class("smtrc", "apartment") is not None

    # Company detection from mid-broker / portal model instances
    haseko_cls = SiteRegistry.resolve_model_class("haseko", "mansion")
    assert haseko_cls is not None
    assert SiteRegistry.detect_company_from_model(haseko_cls) == "haseko"


@pytest.mark.asyncio
async def test_integrity_transition_preserves_slack_notified_and_recovers_to_ml():
    """AC4: Anomaly detection never pollutes is_slack_notified, creates missing eval_rec in validate_data,
    invalidates stale predictions, and transitions healed records through recrawled_pending_ml -> healthy."""
    eval_rec = PropertyEvaluation(
        pk=101,
        company="mitsui",
        property_type="mansion",
        property_id=55,
        property_url="https://www.rehouse.co.jp/buy/mansion/bkdetail/F101/",
        first_stage_predicted_price=Decimal(5500),
        second_stage_predicted_price=Decimal(5600),
        dcf_theoretical_price=5400,
        is_first_stage_passed=True,
        is_slack_notified=False,
        heal_status="healthy",
    )
    now = timezone.now()

    # 1. Anomaly detected -> isolate without touching is_slack_notified, clear stale predictions
    apply_integrity_transition(
        eval_rec,
        is_valid=False,
        reasons=["専有面積欠損"],
        git_sha="sha_broken_1",
        now=now,
    )
    assert eval_rec.heal_status == "detected"
    assert eval_rec.needs_parser_fix is True
    assert eval_rec.needs_recrawl is True
    assert eval_rec.failed_git_sha == "sha_broken_1"
    assert eval_rec.is_slack_notified is False
    assert eval_rec.first_stage_predicted_price is None
    assert eval_rec.second_stage_predicted_price is None
    assert eval_rec.dcf_theoretical_price is None
    assert eval_rec.is_first_stage_passed is False
    assert eval_rec.last_detail_fetched_at == now

    # While needs_recrawl=True, bulk ML skips it
    assert _should_skip_item(eval_rec, force=False) is True

    # 2. Parser fixed & recrawled -> valid! Transitions to recrawled_pending_ml
    apply_integrity_transition(
        eval_rec,
        is_valid=True,
        reasons=[],
        git_sha="sha_fixed_2",
        now=now + datetime.timedelta(hours=2),
    )
    assert eval_rec.heal_status == "recrawled_pending_ml"
    assert eval_rec.needs_parser_fix is False
    assert eval_rec.needs_recrawl is False
    assert eval_rec.failed_git_sha == ""
    assert eval_rec.recrawl_attempts == 0
    assert eval_rec.is_slack_notified is False

    # Even if an old prediction were somehow present, recrawled_pending_ml forces re-evaluation!
    eval_rec.first_stage_predicted_price = Decimal(5000)
    eval_rec.dcf_theoretical_price = 4900
    assert _should_skip_item(eval_rec, force=False) is False

    # 3. Bulk ML evaluation runs -> transitions recrawled_pending_ml to healthy!
    dummy_prop = SimpleNamespace(
        id=55,
        pageUrl=eval_rec.property_url,
        price=45000000,
        propertyName="テストマンション",
        address="東京都港区赤坂1-1-1",
        traffic="東京メトロ千代田線「赤坂」駅 徒歩3分",
        senyuMenseki=Decimal("60.0"),
        chikunengetsuStr="2015年3月",
        kaisuStr="5階/10階建",
        chidai=None,
        chidaiStr="",
    )
    with patch("package.ml.evaluation.record_builder.evaluate_dcf_and_yields") as mock_dcf:
        mock_dcf.return_value = SimpleNamespace(
            expected_gross_yield=4.8,
            expected_net_yield=3.9,
            estimated_annual_rent=2160000,
            dcf_theoretical_price=5200,
        )
        updated_rec, is_new = build_or_update_eval_record(
            item=dummy_prop,
            price_stage1=5500.0,
            existing=eval_rec,
            company="mitsui",
            property_type="mansion",
            skip_duplicate_check=True,
            p10_stage1=5000.0,
        )
    assert is_new is False
    assert updated_rec.heal_status == "healthy"
    assert updated_rec.is_slack_notified is False

    # 4. validate_data.process_property_validation creates PropertyEvaluation when eval_rec is None!
    broken_item = SimpleNamespace(
        id=777,
        pageUrl="https://www.sumai1.com/buy/mansion/detail/777/",
        propertyName="",  # Missing name -> invalid
        address="東京都新宿区西新宿1-1-1",
        traffic="JR山手線「新宿」駅 徒歩5分",
        price=50000000,
        senyuMenseki=Decimal("55.0"),
    )
    res, created_eval = await validate_data._validate_single_property(
        sem=asyncio.Semaphore(2),
        item=broken_item,
        ptype="mansion",
        company="sumai1",
        eval_rec=None,
        skip_url_check=True,
    )
    assert res["status"] == "invalid"
    assert created_eval is not None
    assert created_eval.company == "sumai1"
    assert created_eval.needs_parser_fix is True
    assert created_eval.needs_recrawl is True
    assert created_eval.is_slack_notified is False
    assert created_eval.heal_status == "detected"


def test_differential_true_ttl_expiry_and_sha_aware_anomaly_refetch():
    """AC5: differential.py expires 30-day TTL even when updateDateTime is reset daily,
    and refetches anomalous records only when git_sha changed (or sha is empty)."""
    now = timezone.now()
    thirty_one_days_ago = now - datetime.timedelta(days=31)
    yesterday = now - datetime.timedelta(days=1)

    item = ListItem(url="https://example.com/p1", price=40000000)

    # Case 1: updateDateTime was overwritten to `now` by daily skip, but inputDateTime / last_detail_fetched_at is 31d old -> MUST FETCH!
    rec_stale_detail = {
        "pageUrl": item.url,
        "price": 40000000,
        "updateDateTime": now,
        "inputDateTime": thirty_one_days_ago,
        "last_detail_fetched_at": thirty_one_days_ago,
    }
    assert _should_fetch_item(item, rec_stale_detail, now, ttl_days=30) is True

    # Case 2: Detail fetched yesterday, price unchanged, healthy -> SKIP
    rec_fresh_healthy = {
        "pageUrl": item.url,
        "price": 40000000,
        "updateDateTime": now,
        "inputDateTime": thirty_one_days_ago,
        "last_detail_fetched_at": yesterday,
        "needs_recrawl": False,
        "needs_parser_fix": False,
        "heal_status": "healthy",
    }
    assert _should_fetch_item(item, rec_fresh_healthy, now, ttl_days=30) is False

    # Case 3: Anomalous record on SAME git_sha ("sha_v1") -> SKIP (do not hammer unfixed parser)
    rec_anom_same_sha = {
        **rec_fresh_healthy,
        "needs_recrawl": True,
        "needs_parser_fix": True,
        "heal_status": "detected",
        "failed_git_sha": "sha_v1",
    }
    with patch("package.api.differential.get_current_git_sha", return_value="sha_v1"):
        assert _should_fetch_item(item, rec_anom_same_sha, now, ttl_days=30) is False

    # Case 4: Anomalous record after NEW git_sha ("sha_v2") deployed -> FETCH IMMEDIATELY!
    with patch("package.api.differential.get_current_git_sha", return_value="sha_v2"):
        assert _should_fetch_item(item, rec_anom_same_sha, now, ttl_days=30) is True

    # Case 5: source_data_invalid with fresh TTL -> SKIP until TTL expires
    rec_source_invalid = {
        **rec_fresh_healthy,
        "needs_recrawl": False,
        "needs_parser_fix": False,
        "heal_status": "source_data_invalid",
        "failed_git_sha": "sha_v1",
    }
    with patch("package.api.differential.get_current_git_sha", return_value="sha_v2"):
        assert _should_fetch_item(item, rec_source_invalid, now, ttl_days=30) is False


def test_recrawl_anomalies_pk_sharding_source_invalid_and_orphan_cleanup():
    """AC6: recrawl_anomalies distributes property_id=0 evenly via PK id, escalates source_data_invalid
    after 3 distinct SHAs, and cleans up orphaned wrong-type records when parser switches property_type."""
    # 1. 8 first-time parser failures all have property_id=0, but distinct PK id=1..8
    zero_prop_records = [
        SimpleNamespace(id=idx, property_id=0, property_url=f"https://example.com/{idx}")
        for idx in range(1, 9)
    ]
    assigned_counts = [
        len(recrawl_anomalies.filter_targets_by_task(zero_prop_records, task_index=t, task_count=8))
        for t in range(8)
    ]
    assert assigned_counts == [1, 1, 1, 1, 1, 1, 1, 1]

    # 2. Repeated unresolved validation across 3 distinct SHAs -> escalates to source_data_invalid
    ev = PropertyEvaluation(
        pk=202,
        company="mitsui",
        property_type="tochi",
        property_id=999,
        property_url="https://www.rehouse.co.jp/buy/tochi/bkdetail/F202/",
        needs_parser_fix=True,
        needs_recrawl=True,
        heal_status="detected",
        failed_git_sha="sha_1",
        recrawl_attempts=2,
    )
    recrawl_anomalies.apply_unresolved_recrawl_escalation(ev, current_sha="sha_3", item_parsed=True)
    assert ev.recrawl_attempts == 3
    assert ev.heal_status == "source_data_invalid"
    assert ev.needs_parser_fix is False
    assert ev.needs_recrawl is False

    # 3. Orphan cleanup when property_type switched (e.g. kodate -> mansion)
    mock_old_model = MagicMock()
    mock_new_model = MagicMock()
    with patch.object(
        SiteRegistry,
        "resolve_model_class",
        side_effect=lambda comp, ptype: mock_old_model if ptype == "kodate" else mock_new_model,
    ):
        deleted = recrawl_anomalies.cleanup_orphaned_old_type_record(
            old_company="mitsui",
            old_property_type="kodate",
            old_property_id=42,
            new_company="mitsui",
            new_property_type="mansion",
            property_url="https://www.rehouse.co.jp/buy/mansion/bkdetail/F42/",
        )
    assert deleted is True
    mock_old_model.objects.filter.assert_called_once()


def test_auto_heal_gcs_bridge_zero_prop_id_and_pipeline_wiring(tmp_path, monkeypatch):
    """AC7: auto_heal_parsers handles property_id=0 & GCS sync/pull, monitor_error_pages works via pathlib,
    and run_ml_pipeline runs recrawl_anomalies + invokes auto_heal even when validate_data fails."""
    # 1. GCS pull writes Temp/auto_heal_instruction.json
    sample_inst = {"generated_at": "2026-11-14 09:00:00", "total_anomalies_detected": 2, "targets": [{"company": "haseko"}]}
    fake_sm = MagicMock()
    fake_sm.read_text.return_value = json.dumps(sample_inst, ensure_ascii=False)
    out_file = tmp_path / "auto_heal_instruction.json"
    with patch("scripts.debug_tools.auto_heal_parsers.get_storage_manager", return_value=fake_sm):
        pulled = auto_heal_parsers.pull_latest_instruction_from_gcs(dest_path=str(out_file))
    assert pulled is True
    assert json.loads(out_file.read_text(encoding="utf-8"))["total_anomalies_detected"] == 2

    # 2. monitor_error_pages scans error HTML via pathlib without Linux `find`
    err_dir = tmp_path / "error_pages" / "haseko_mansion"
    err_dir.mkdir(parents=True)
    html_file = err_dir / "err1.html"
    html_file.write_text("<html>error</html>", encoding="utf-8")
    (err_dir / "err1_meta.txt").write_text("URL: https://www.haseko-chukai.com/x\nReason: Missing price\n", encoding="utf-8")

    summary = monitor_error_pages.collect_error_page_summary(
        error_dirs=[str(tmp_path / "error_pages")],
        include_gcs=False,
    )
    assert summary["total_errors"] == 1
    assert summary["recent_errors_24h"] == 1
    assert summary["by_company_type"]["haseko_mansion"]["recent_24h"] == 1

    # 3. run_ml_pipeline runs recrawl_anomalies and still runs auto_heal_parsers with --failed-steps if validate_data fails
    executed_cmds: list[list[str]] = []

    def fake_run_command(cmd: list[str], desc: str):
        executed_cmds.append(cmd)
        if any("validate_data.py" in c for c in cmd):
            raise RuntimeError("validate_data failed")

    with (
        patch.object(run_ml_pipeline, "start_on_demand_resources"),
        patch.object(run_ml_pipeline, "verify_barrier_completion", return_value=(True, [])),
        patch.object(run_ml_pipeline, "send_aggregated_crawl_report"),
        patch.object(run_ml_pipeline, "_can_stop_shared_proxysql", return_value=False),
        patch.object(run_ml_pipeline, "run_command", side_effect=fake_run_command),
    ):
        with pytest.raises(RuntimeError, match="validate_data failed"):
            run_ml_pipeline.main(["--dry-run", "--skip-train", "--skip-potentials-sync"])

    joined = [" ".join(c) for c in executed_cmds]
    assert any("recrawl_anomalies.py" in s and "--skip-same-sha" in s for s in joined), f"recrawl_anomalies not called: {joined}"
    assert any("auto_heal_parsers.py" in s and "--failed-steps" in s for s in joined), f"auto_heal fallback not called: {joined}"

    # 4. deploy-production.yml injects APP_GIT_SHA and triggers recrawl workflow on parser changes
    deploy_yml = (REPO_ROOT / ".github" / "workflows" / "deploy-production.yml").read_text(encoding="utf-8")
    assert "APP_GIT_SHA" in deploy_yml
    assert "realestate-recrawl-anomalies-pipeline-prod" in deploy_yml

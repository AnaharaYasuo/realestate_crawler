"""Unit tests for periodic sync and TTL freshness via ExternalDataSyncAudit (Issue #1538)."""
import datetime
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone
from package.models.building_master import BuildingMaster
from package.models.evaluation import (
    HazardMapPotential,
    LandPricePointPotential,
    MunicipalFuturePotential,
    MunicipalPotential,
    MunicipalYearlyPotential,
    StationPotential,
    UrbanInductionZoneMaster,
    UrbanPlanningZonePotential,
)
from package.models.external_data_sync_audit import ExternalDataSyncAudit
from scripts.sync_all_potentials import (
    _is_dataset_fresh_by_audit,
    _record_sync_audit,
    _resolve_effective_skip_flags,
)


@pytest.mark.django_db
class TestExternalDataSyncAuditTTL:
    def test_audit_record_creation_and_update(self):
        """_record_sync_audit で同期実行メタデータが正常に記録・更新されること"""
        _record_sync_audit("estat", "SUCCESS", 1741, duration_sec=12)
        audit = ExternalDataSyncAudit.objects.get(dataset_key="estat")
        assert audit.status == "SUCCESS"
        assert audit.record_count == 1741
        assert audit.duration_seconds == 12

        # 再度記録した際に上書き更新されること
        _record_sync_audit("estat", "SUCCESS", 1742, duration_sec=15)
        audit.refresh_from_db()
        assert audit.record_count == 1742
        assert audit.duration_seconds == 15

    def test_is_dataset_fresh_by_audit_with_fresh_and_stale(self):
        """TTL 期限内なら True、期限切れ（stale）なら False を返すこと"""
        now = timezone.now()
        # 10日前に同期成功 -> 30日TTLなら fresh
        ExternalDataSyncAudit.objects.update_or_create(
            dataset_key="stations",
            defaults={
                "dataset_name": "stations",
                "last_synced_at": now - datetime.timedelta(days=10),
                "record_count": 10000,
                "status": "SUCCESS",
            },
        )
        assert _is_dataset_fresh_by_audit("stations", max_age_days=30) is True

        # 35日前に同期成功 -> 30日TTLなら stale
        ExternalDataSyncAudit.objects.update_or_create(
            dataset_key="stations",
            defaults={
                "dataset_name": "stations",
                "last_synced_at": now - datetime.timedelta(days=35),
                "record_count": 10000,
                "status": "SUCCESS",
            },
        )
        assert _is_dataset_fresh_by_audit("stations", max_age_days=30) is False

    def test_is_dataset_fresh_by_audit_initializes_existing_data(self):
        """監査レコード未作成でも既存テーブルに十分なデータがあれば初回自動補完して初回スキップすること"""
        ExternalDataSyncAudit.objects.filter(dataset_key="hazard_map").delete()
        mock_model = MagicMock()
        mock_model.objects.count.return_value = 1600

        # 初回判定: 1600件あるので自動補完されて True になる
        fresh = _is_dataset_fresh_by_audit("hazard_map", max_age_days=30, model_cls=mock_model, min_rows=1500)
        assert fresh is True

        # 監査レコードが作成されていること
        audit = ExternalDataSyncAudit.objects.filter(dataset_key="hazard_map").first()
        assert audit is not None
        assert audit.record_count == 1600

    def test_resolve_effective_skip_flags_respects_ttl_and_force(self):
        """_resolve_effective_skip_flags が TTL 判定および force フラグに正しく従うこと"""
        raw_flags = {
            "estat": False,
            "stations": False,
            "urban_zones": False,
            "land_prices": False,
            "hazard_map": False,
            "future_pop": False,
            "induction_zones": False,
            "historical": False,
            "building_master": False,
            "rent_cap_rates": False,
            "macro": False,
            "open_geo_tx": False,
        }

        # 全て fresh な状態をモック
        with patch("scripts.sync_all_potentials._is_dataset_fresh_by_audit", return_value=True), \
             patch("scripts.sync_all_potentials._is_updated_within_days", return_value=True), \
             patch("scripts.sync_all_potentials._is_macro_fresh", return_value=True):

            # respect_ttl=True の場合、すべてスキップ (True) に解決される
            eff = _resolve_effective_skip_flags(raw_flags, respect_ttl=True, force=False)
            assert eff["estat"] is True
            assert eff["stations"] is True
            assert eff["hazard_map"] is True
            assert eff["future_pop"] is True

            # force=True の場合、TTL 判定に関わらずすべて再同期 (False) に解決される
            eff_forced = _resolve_effective_skip_flags(raw_flags, respect_ttl=True, force=True)
            assert eff_forced["estat"] is False
            assert eff_forced["stations"] is False
            assert eff_forced["hazard_map"] is False
            assert eff_forced["future_pop"] is False

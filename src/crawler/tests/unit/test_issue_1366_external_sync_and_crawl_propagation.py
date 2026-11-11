"""Issue #1366: 外部データ全14種定期更新・GCS永続化・新規クロール物件への特徴量完全伝播の単体テスト"""

from __future__ import annotations

import datetime
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from asgiref.sync import sync_to_async
import pytest

from package.ml.features.builder import build_features
from package.ml.inference.api_client import serialize_property
from package.models.evaluation import (
    LandPricePointPotential,
    MacroEconomicIndex,
    MunicipalPotential,
    StationPotential,
)
from package.parser.mitsuiParser import MitsuiKodateParser, MitsuiTochiParser
from package.parser.sumifuParser import SumifuTochiParser
from package.utils.gsi_dem_terrain import lookup_cached_dem_features, reset_dem_cache
from package.utils.gsi_geocoder import lookup_cached_coordinates, reset_geocode_cache

pytestmark = pytest.mark.django_db


def _seed_test_potentials() -> None:
    MunicipalPotential.objects.update_or_create(
        prefecture="東京都",
        city="世田谷区",
        defaults={
            "total_population": 920000,
            "population_growth_rate": Decimal("1.8"),
            "average_income": 5600,
            "population_density": Decimal("15800.0"),
        },
    )
    StationPotential.objects.update_or_create(
        station_name="経堂",
        railway_line="小田急小田原線",
        defaults={"passenger_volume": 82000},
    )
    LandPricePointPotential.objects.update_or_create(
        point_code="L01-SETAGAYA-1366",
        defaults={
            "survey_type": "L01",
            "prefecture": "東京都",
            "city": "世田谷区",
            "chome_key": "東京都世田谷区桜丘1",
            "latitude": 35.6470,
            "longitude": 139.6350,
            "land_price": 780000,
            "growth_rate": Decimal("4.2"),
            "land_use": "residential",
            "zone_name": "第一種低層住居専用地域",
            "road_width": 5.0,
            "station_name": "経堂",
            "station_distance_m": 650,
            "has_gas": True,
            "has_water": True,
            "has_sewer": True,
        },
    )
    from package.ml.features.reference_data import reset_reference_caches

    reset_reference_caches()


def test_serialize_property_preserves_all_land_building_and_alias_fields():
    """新規クロールのインライン査定・URL査定用シリアライザが会社別カラム・土地属性を完全保持し特徴量が一致すること"""
    _seed_test_potentials()
    model_like = SimpleNamespace(
        propertyName="三井のリハウス 世田谷桜丘戸建",
        price=79800000,
        address="東京都世田谷区桜丘1丁目2-3",
        address1="東京都",
        address2="世田谷区桜丘1丁目",
        station1="経堂",
        railwayWalkMinute1=9,
        busUse1=0,
        busRideMinute1=0,
        busWalkMinute1=0,
        traffic="小田急線「経堂」駅 徒歩9分",
        tochiMenseki=Decimal("118.40"),
        tatemonoMenseki=Decimal("96.20"),
        chikunengetsu=datetime.date(2016, 6, 1),
        kouzou="木造2階建",
        kaisu="2",
        kaisuStr="地上2階建",
        madori="4LDK",
        youseki=Decimal(150),
        kenpei=Decimal(60),
        youtoChiiki="第一種低層住居専用地域",
        kuiki="市街化区域",
        chimoku="宅地",
        chisei="ひな段",
        setsudou="南側 接面8.5m 公道 幅員4.2m",
        douroHaba=Decimal("4.2"),
        setsumen=Decimal("8.5"),
        douroMuki="南",
        douroKubun="公道",
        setsubi="都市ガス・公営水道・浄化槽",
        biko="道路面より1.8m高い・間知石擁壁あり・確定測量済",
        boukaChiiki="準防火地域",
        privateRoadBurden="",
        tochikenri="所有権",
        chidai=0,
    )

    serialized = serialize_property(model_like, "kodate")
    assert serialized["propertyType"] == "kodate"
    assert serialized["setsumen"] == pytest.approx(8.5)
    assert serialized["douroHaba"] == pytest.approx(4.2)
    assert serialized["chisei"] == "ひな段"
    assert "浄化槽" in serialized["setsubi"]

    direct_feats = build_features(model_like, "kodate")
    serial_feats = build_features(serialized, "kodate")

    for key in (
        "is_maguchi_missing",
        "is_road_width_missing",
        "frontage_penalty_factor",
        "road_condition_factor",
        "estimated_infra_cost_man",
        "retaining_wall_cost_man",
        "estimated_fixed_cost_man",
        "is_measured_boundary",
        "net_land_component_man",
        "anchor_log_unit_price",
    ):
        assert serial_feats[key] == pytest.approx(direct_feats[key], rel=1e-5), f"Mismatch on {key}"
    assert serial_feats["is_maguchi_missing"] == 0.0
    assert serial_feats["is_road_width_missing"] == 0.0
    assert serial_feats["estimated_fixed_cost_man"] > 0.0


def test_mitsui_and_sumifu_parsers_do_not_swap_maguchi_and_road_width():
    """サイト固有パーサーが『接面8.5m 公道 幅員4.0m』で間口と道路幅員を取り違えないこと"""
    tochi_parser = MitsuiTochiParser()
    res_tochi = tochi_parser._parseSetudouDetails("南側 接面8.5m 公道 幅員4.0m")
    assert float(res_tochi["douroHaba"]) == pytest.approx(4.0)
    assert float(res_tochi["setsumen"]) == pytest.approx(8.5)

    kodate_parser = MitsuiKodateParser()
    with patch.object(kodate_parser, "_parseSetsudou", return_value="北東 接面9.2ｍ 私道 幅員4.5ｍ"):
        res_kodate = kodate_parser._parseSetudouDetails(MagicMock())
    assert float(res_kodate["douroHaba"]) == pytest.approx(4.5)
    assert float(res_kodate["setsumen"]) == pytest.approx(9.2)

    sumifu_parser = SumifuTochiParser(None)
    res_sumifu = sumifu_parser._parseDouroText("南側 接面8.5m(公道) 幅員4.0m")
    assert float(res_sumifu["douroHaba"]) == pytest.approx(4.0)
    assert float(res_sumifu["setsumen"]) == pytest.approx(8.5)


def test_open_data_cache_gcs_roundtrip_and_ondemand_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """GCSストレージからの自動プル・プッシュおよび未見町丁目のオンデマンド解決が動作すること"""
    from package.utils.open_data_cache_sync import (
        ensure_local_cache_from_storage,
        upload_cache_to_storage,
    )

    fake_storage = MagicMock()

    def _fake_download(remote_key: str, dest: str) -> None:
        assert remote_key == "ml_reference_data/gsi_geocode_cache.json"
        Path(dest).write_text(json.dumps({"東京都渋谷区恵比寿1": [35.6467, 139.7101]}), encoding="utf-8")

    fake_storage.download_file.side_effect = _fake_download
    monkeypatch.setenv("OPEN_DATA_STORAGE_SYNC_FORCE", "1")
    local_geo = tmp_path / "gsi_geocode_cache.json"
    pulled = ensure_local_cache_from_storage(
        local_geo, "gsi_geocode_cache.json", storage_getter=lambda: fake_storage
    )
    assert pulled is True
    assert local_geo.exists()

    pushed = upload_cache_to_storage(
        local_geo, "gsi_geocode_cache.json", storage_getter=lambda: fake_storage
    )
    assert pushed is True
    fake_storage.upload_file.assert_called_once()

    reset_geocode_cache()
    reset_dem_cache()
    monkeypatch.setenv("ALLOW_ONDEMAND_OPEN_GEO", "1")
    with patch("package.utils.gsi_geocoder._fetch_gsi_coordinates", return_value=(35.6800, 139.7600)) as mock_geo:
        coords = lookup_cached_coordinates("東京都千代田区丸の内99", cache_path=local_geo)
        assert coords == (35.6800, 139.7600)
        assert mock_geo.call_count == 1

    local_dem = tmp_path / "gsi_dem_terrain_cache.json"
    with patch("package.utils.gsi_dem_terrain._fetch_tile_array", return_value=None) as mock_tile:
        dem_feat = lookup_cached_dem_features(35.6800, 139.7600, cache_path=local_dem)
        assert dem_feat.dem_elevation_m == 0.0
        assert mock_tile.call_count >= 1


def test_sync_macro_economic_indices_parses_mof_jgb_csv_and_covers_future_month():
    """財務省国債金利CSVの和暦/西暦パースおよび将来年月を含むマクロ経済指標自動同期が機能すること"""
    from scripts.data_import.sync_macro_economic_indices import (
        parse_mof_jgb_csv_10y_monthly,
        sync_macro_economic_indices,
    )

    sample_csv = (
        "財務省 国債金利情報\n"
        "基準日,1年,2年,5年,10年,20年\n"
        "R8.10.30,0.45,0.58,0.82,1.34,2.05\n"
        "R8.11.10,0.46,0.60,0.85,1.38,2.09\n"
        "2027/3/15,0.50,0.65,0.92,1.46,2.15\n"
    )
    monthly = parse_mof_jgb_csv_10y_monthly(sample_csv)
    assert monthly["2026-10"] == pytest.approx(1.34)
    assert monthly["2026-11"] == pytest.approx(1.38)
    assert monthly["2027-03"] == pytest.approx(1.46)

    with patch(
        "scripts.data_import.sync_macro_economic_indices._fetch_mof_jgb_monthly_yields",
        return_value=monthly,
    ):
        synced = sync_macro_economic_indices(target_date=datetime.date(2027, 3, 20))
    assert synced > 0
    rec_2027 = MacroEconomicIndex.objects.filter(year_month="2027-03").first()
    assert rec_2027 is not None
    assert rec_2027.jgb_10y_yield == pytest.approx(1.46)
    assert rec_2027.repi_tochi > 100.0


def test_sync_all_potentials_respect_ttl_and_weekly_retrain_schedule():
    """鮮度TTL判定および日曜週次自動再学習スケジュール判定が正しく動作すること"""
    from scripts.ops.run_ml_pipeline import should_run_ml_training
    from scripts.sync_all_potentials import _is_macro_fresh

    MacroEconomicIndex.objects.update_or_create(
        year_month="2026-11",
        defaults={
            "repi_mansion": 218.5,
            "repi_kodate": 122.0,
            "repi_tochi": 113.5,
            "jgb_10y_yield": 1.25,
            "mortgage_fixed_rate": 2.05,
            "nikkei_225": 43200.0,
            "tse_reit_index": 1820.0,
            "construction_cost_index": 144.0,
            "cpi_core": 113.2,
        },
    )
    assert _is_macro_fresh(datetime.date(2026, 11, 11)) is True
    assert _is_macro_fresh(datetime.date(2026, 12, 1)) is False

    # 平日 + SKIP_TRAIN=true -> スキップ
    assert should_run_ml_training(
        cli_skip_train=False,
        env_skip_train=True,
        now_dt=datetime.datetime(2026, 11, 11, 5, 10),  # Wednesday
    ) is False
    # 日曜 + SKIP_TRAIN=true -> 週次自動再学習を実行
    assert should_run_ml_training(
        cli_skip_train=False,
        env_skip_train=True,
        now_dt=datetime.datetime(2026, 11, 15, 5, 10),  # Sunday
    ) is True
    # 明示的 CLI --skip-train -> 曜日に関わらずスキップ
    assert should_run_ml_training(
        cli_skip_train=True,
        env_skip_train=False,
        now_dt=datetime.datetime(2026, 11, 15, 5, 10),
    ) is False


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_inline_stage1_eval_persists_dcf_and_yield_fields():
    """新規クロール物件のインラインStage1評価でDCF理論価格・期待利回りが即時保存されること"""
    await sync_to_async(_seed_test_potentials)()
    from package.api.api import ParseDetailPageAsyncBase
    from package.models.evaluation import PropertyEvaluation

    class _DummyDetailRunner(ParseDetailPageAsyncBase):
        def _generateParser(self):
            return MagicMock()

        def _getLocalPararellLimit(self):
            return 1

        def _getCloudPararellLimit(self):
            return 1

        def _getTimeOutSecond(self):
            return 10

        def _getApiKey(self):
            return ""

    runner = _DummyDetailRunner()
    item = SimpleNamespace(
        id=9901,
        propertyName="桜丘売地テスト",
        pageUrl="https://example.com/tochi/9901",
        price=65000000,
        address="東京都世田谷区桜丘1丁目1-1",
        address1="東京都",
        address2="世田谷区桜丘1丁目",
        station1="経堂",
        railwayWalkMinute1=8,
        tochiMenseki=Decimal("110.0"),
        youseki=Decimal(150),
        kenpei=Decimal(60),
        chidai=None,
        chidaiStr="",
    )

    eval_rec, pred1, passed = await runner._run_stage1_eval(
        item,
        company="mitsui",
        property_type="tochi",
        asking_price=6500.0,
        property_eval_cls=PropertyEvaluation,
        predict_first_stage=lambda _x: 7200,
    )
    assert pred1 == 7200
    assert passed is True
    assert eval_rec.dcf_theoretical_price is not None
    assert eval_rec.expected_gross_yield is not None
    assert eval_rec.expected_net_yield is not None
    assert eval_rec.estimated_annual_rent is not None

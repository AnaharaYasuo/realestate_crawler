# -*- coding: utf-8 -*-
"""
全国全自治体・全駅の時系列推移および2050年将来予測・立地適正化計画データの全量網羅統合テスト (Issue #1210)
"""
import pytest
import datetime
from decimal import Decimal

pytestmark = pytest.mark.django_db

from package.models.evaluation import (
    MunicipalPotential, StationPotential,
    MunicipalFuturePotential, MunicipalYearlyPotential,
    StationYearlyPotential, UrbanInductionZoneMaster
)
from package.ml.features import (
    build_features, FEATURE_SETS, _init_global_caches,
    query_future_population_features,
    query_urban_induction_zone_features,
    query_historical_momentum_features,
)
from package.ml.danchou_rag import format_comprehensive_future_and_historical_context
from package.ml.report_generator import _build_rag_prompt
from scripts.data_import.import_ipss_future_population import sync_ipss_future_population
from scripts.data_import.import_urban_induction_zones import sync_urban_induction_zones
from scripts.data_import.sync_yearly_historical_potentials import (
    sync_municipal_yearly_potentials, sync_station_yearly_potentials
)


@pytest.fixture(autouse=True)
def setup_comprehensive_masters():
    """テスト用マスタデータの初期化"""
    MunicipalPotential.objects.update_or_create(
        prefecture="東京都", city="中央区",
        defaults={
            "population_growth_rate": Decimal("0.85"),
            "average_income": 6500,
            "total_population": 175000,
            "income_growth_rate": Decimal("2.10"),
            "population_density": Decimal("16500.0"),
        }
    )
    StationPotential.objects.update_or_create(
        station_name="勝どき", railway_line="都営大江戸線",
        defaults={"passenger_volume": 115000}
    )

    sync_ipss_future_population()
    sync_urban_induction_zones()
    sync_municipal_yearly_potentials()
    sync_station_yearly_potentials()
    _init_global_caches(force_refresh=True)


def test_municipal_future_potential_records():
    """社人研将来推計人口の全量・全時点レコード検証"""
    count = MunicipalFuturePotential.objects.filter(prefecture="東京都", city="中央区").count()
    assert count == 6  # 2025, 2030, 2035, 2040, 2045, 2050

    rec_2035 = MunicipalFuturePotential.objects.get(prefecture="東京都", city="中央区", target_year=2035)
    assert rec_2035.projected_population > 0
    assert rec_2035.working_age_ratio > 0
    assert rec_2035.elderly_ratio > 0


def test_urban_induction_zone_master():
    """立地適正化計画区域マスタの判定検証"""
    uiz = UrbanInductionZoneMaster.objects.filter(prefecture="東京都", city="中央区").first()
    assert uiz is not None
    assert uiz.is_residential_induction_zone is True


def test_yearly_potentials_history():
    """過去10年実績推移マスタの検証"""
    muni_history = MunicipalYearlyPotential.objects.filter(prefecture="東京都", city="中央区")
    assert muni_history.count() == 10

    station_history = StationYearlyPotential.objects.filter(station_name="勝どき")
    assert station_history.count() == 10
    latest_st = station_history.get(year=2024)
    assert latest_st.passenger_volume > 0


def test_future_and_momentum_feature_extraction():
    """build_features での将来予測・時系列モメンタム特徴量抽出検証"""
    prop = {
        "propertyName": "パークタワー勝どき",
        "pageUrl": "https://example.com/kachidoki_tower",
        "inputDate": datetime.date(2024, 6, 1),
        "price": 120000000,
        "senyuMenseki": 75.0,
        "madori": "3LDK",
        "chikunengetsu": datetime.date(2023, 1, 1),
        "address": "東京都中央区勝どき",
        "railwayWalkMinute1": 3,
        "traffic": "都営大江戸線 勝どき駅 徒歩3分",
    }

    feats = build_features(prop, property_type="mansion", base_date=datetime.date(2026, 9, 1))

    assert "future_pop_change_2035" in feats
    assert "future_working_age_ratio_2035" in feats
    assert "future_elderly_ratio_2035" in feats
    assert "future_single_household_ratio_2035" in feats
    assert "is_in_urban_induction_zone" in feats
    assert "is_in_residential_induction_zone" in feats
    assert "station_volume_3y_cagr" in feats
    assert "municipal_income_3y_cagr" in feats
    assert "municipal_pop_momentum" in feats

    assert feats["is_in_residential_induction_zone"] == 1.0


def test_feature_sets_include_future_and_momentum_fields():
    """全物件種別の FEATURE_SETS に新設特徴量が含まれていることの検証"""
    new_keys = [
        "future_pop_change_2035", "future_working_age_ratio_2035",
        "future_elderly_ratio_2035", "future_single_household_ratio_2035",
        "is_in_urban_induction_zone", "is_in_residential_induction_zone",
        "station_volume_3y_cagr", "municipal_income_3y_cagr", "municipal_pop_momentum"
    ]
    for ptype in ["mansion", "kodate", "apartment", "tochi"]:
        for stage in ["first", "second"]:
            feats = FEATURE_SETS[ptype][stage]
            for k in new_keys:
                assert k in feats, f"Key {k} missing in FEATURE_SETS['{ptype}']['{stage}']"


def test_danchou_rag_prompt_injects_future_and_historical_context():
    """定性評価プロンプトに将来予測・立地適正化・過去推移が反映されていることの検証"""
    class MockProperty:
        address1 = "東京都"
        address2 = "中央区"
        station1 = "勝どき"
        company = "mitsui"
        price = 120000000
        propertyName = "パークタワー勝どき"
        pageUrl = "https://example.com/kachidoki_tower"
        property_type = "mansion"

    prop = MockProperty()
    context_text = format_comprehensive_future_and_historical_context(prop)
    assert "【自治体将来推計人口・世帯動態（社人研推計）】" in context_text
    assert "【国土交通省 立地適正化計画判定】" in context_text
    assert "【過去10年実績推移モメンタム】" in context_text
    assert "2035年推計人口変化率" in context_text
    assert "誘導区域内" in context_text

    # プロンプト全体への反映検証
    class MockEvalRec:
        estimated_sekisan_price = 10000
        cash_flow = 200
        dscr = 1.35
    eval_rec = MockEvalRec()
    prompt = _build_rag_prompt(
        eval_rec=eval_rec,
        prop=prop,
        ptype_jp="区分マンション",
        asking_price_man=12000,
        address="東京都中央区",
        access="勝どき駅 徒歩3分",
        matched_kb=[],
        far_slack=10.0,
    )
    assert "【自治体将来推計人口・世帯動態（社人研推計）】" in prompt
    assert "【国土交通省 立地適正化計画判定】" in prompt
    assert "【過去10年実績推移モメンタム】" in prompt


def test_missing_data_raises_clear_error():
    """マスター未登録の未知エリアに対してサイレントフォールバックせず例外が発生することの検証"""
    with pytest.raises(ValueError) as excinfo:
        query_future_population_features("未知県", "架空市")
    assert "CRITICAL: Future population data missing" in str(excinfo.value)

# -*- coding: utf-8 -*-
"""
経済的価値創出力評価・外れ値除去仕様の単体テスト
"""
import pytest
import datetime
from decimal import Decimal
from package.ml.features import build_features, FEATURE_SETS
from package.ml.predict import _detect_property_type

class MockProperty:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_landless_investment_rerouted_to_mansion():
    """土地面積0のRC区分所有（オーナーチェンジ）が戸建てテーブルにあってもマンションとして判定されることを検証"""
    class MockSumifuInvestmentKodate:
        def __init__(self):
            self.tochiMenseki = Decimal('0.00')
            self.senyuMenseki = Decimal('22.50')
            self.tatemonoMenseki = Decimal('22.50')
            self.structure = "鉄筋コンクリート造"
            self.price = Decimal('5800000')

    prop = MockSumifuInvestmentKodate()
    detected_type = _detect_property_type(prop)
    assert detected_type == "mansion", f"Expected mansion, got {detected_type}"

def test_area_anomaly_sanitized():
    """価格値（6490万など）が専有面積に混入したパース異常物件が安全にキャップされることを検証"""
    prop = MockProperty(
        senyuMenseki=6490.0,
        address="東京都板橋区前野町",
        chikunengetsu="2010-05",
        structure="RC"
    )
    feats = build_features(prop, "mansion")
    assert feats["area"] <= 500.0, f"Area should be capped under 500m², got {feats['area']}"

def test_huge_land_scale_discount():
    """2.5ヘクタール等の巨大原野・山林において、平米単価が非線形に減退することを検証"""
    prop = MockProperty(
        tochiMenseki=25000.0,
        address="北海道沙流郡日高町",
        structure=""
    )
    feats = build_features(prop, "tochi")
    assert "scale_discount" in feats
    assert feats["scale_discount"] < 0.45, f"Scale discount for 25,000m² should be < 0.45, got {feats['scale_discount']}"

def test_far_extraction_from_combined_string():
    """'建ぺい率・容積率：80% / 600%' から容積率600%が正しく抽出され、潜在延床面積に反映されることを検証"""
    prop = MockProperty(
        tochiMenseki=100.0,
        kenpeiYousekiStr="80% / 600%",
        address="東京都港区六本木"
    )
    feats = build_features(prop, "tochi")
    assert feats["max_youseki"] == 600.0, f"Expected FAR 600.0, got {feats['max_youseki']}"
    assert feats["potential_floor_area"] == 600.0, f"Expected potential floor area 600m², got {feats['potential_floor_area']}"

def test_imputed_age_for_missing_built_year():
    """築年数が完全に欠損している木造家屋に対し、新築（0年）ではなく適正な老朽化年数が補正されることを検証"""
    prop = MockProperty(
        tatemonoMenseki=60.0,
        tochiMenseki=50.0,
        structure="木造",
        address="東京都足立区加賀"
    )
    feats = build_features(prop, "kodate")
    assert feats["chikunen"] >= 30.0, f"Missing age for wooden house should be >= 30 years, got {feats['chikunen']}"

@pytest.mark.django_db
def test_imputed_economic_value_anchor():
    """想定純賃料還元価値（income_approach_value）が正当に算出されることを検証"""
    from package.models.evaluation import LandPricePotential, MunicipalPotential
    import package.ml.features as feat_mod

    LandPricePotential.objects.get_or_create(
        prefecture="東京都",
        city="港区",
        land_use="residential",
        defaults={"average_land_price": 2100000}
    )
    MunicipalPotential.objects.get_or_create(
        prefecture="東京都",
        city="港区",
        defaults={
            "population_growth_rate": Decimal('1.5'),
            "average_income": 11000,
            "population_density": Decimal('12000.0')
        }
    )
    feat_mod._lp_cache.clear()
    feat_mod._muni_cache.clear()

    prop = MockProperty(
        senyuMenseki=70.0,
        address="東京都港区南青山",
        chikunengetsu="2015-01",
        structure="RC",
        railwayWalkMinute1=5
    )
    feats = build_features(prop, "mansion")
    assert feats["income_approach_value"] > 0
    # 都心70㎡新耐震マンションの経済還元価値は数千万円以上
    assert feats["income_approach_value"] >= 3000.0

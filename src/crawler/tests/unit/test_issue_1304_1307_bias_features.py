import pytest
import numpy as np
from package.ml.features.builder import build_features
from package.ml.features.feature_sets import FEATURE_SETS
from package.ml.training.sample_weights import calculate_time_decay_weights


class DummyProp:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_kodate_depreciation_and_demolition_features():
    """Issue #1304: 戸建ての耐用年数超減価と解体控除特徴量"""
    # 築40年の古い木造戸建て
    old_kodate = DummyProp(
        tochiMenseki=120.0,
        tatemonoMenseki=90.0,
        chikunengetsuStr="1985年4月",
        kouzou="木造2階建",
        price=15000000,
        address1="東京都",
        address2="八王子市",
        railwayWalkMinute1=15,
        genkyo="古家あり",
    )
    feats = build_features(old_kodate, "kodate")
    assert "building_depreciation_ratio" in feats
    assert "demolition_cost_discount" in feats
    # 築40年木造は法定耐用年数22年を大幅に超過しているため減価率が低水準（0.10〜0.15付近）
    assert 0.05 <= feats["building_depreciation_ratio"] <= 0.20
    # 解体費用控除が発生していること
    assert feats["demolition_cost_discount"] > 0.0


def test_mansion_vintage_floor_and_scale_interaction():
    """Issue #1305: マンション築古ヴィンテージ床および規模交差項"""
    vintage_mansion = DummyProp(
        senyuMenseki=70.0,
        chikunengetsuStr="1980年3月",
        kouzou="RC造8階建",
        soukosu=150,
        railwayWalkMinute1=18,
        price=35000000,
        address1="東京都",
        address2="世田谷区",
    )
    feats = build_features(vintage_mansion, "mansion")
    assert "mansion_vintage_floor" in feats
    assert "scale_vintage_interaction" in feats
    # 築46年でもヴィンテージ底打ちが機能しゼロにならない
    assert feats["mansion_vintage_floor"] > 0.0
    # 総戸数150戸のスケール交差項が算出されている
    assert feats["scale_vintage_interaction"] > 0.0


def test_tochi_low_demand_discount():
    """Issue #1306: 土地の低路線価・低需要エリア減価特徴量"""
    rural_tochi = DummyProp(
        tochiMenseki=350.0,
        price=8000000,
        address1="茨城県",
        address2="常総市",
        railwayWalkMinute1=25,
        kuiki="市街化調整区域",
    )
    feats = build_features(rural_tochi, "tochi")
    assert "low_demand_land_discount" in feats
    # 低需要・調整区域で割引が効いていること (< 1.0)
    assert 0.0 < feats["low_demand_land_discount"] < 1.0


def test_heteroskedasticity_sample_weights():
    """Issue #1307: 低価格帯の不均一分散を考慮したサンプル重み"""
    dates = ["2026-10-01", "2026-10-01", "2026-10-01"]
    # 300万円（超低価格）、3,000万円（標準）、1億円（高価格）
    prices_man = [300.0, 3000.0, 10000.0]
    weights = calculate_time_decay_weights(dates, prices_man=prices_man)
    assert len(weights) == 3
    # 低価格帯（300万）のMAPEペナルティを高めるため重みが相対的に高いこと
    assert weights[0] > weights[1] > weights[2]


def test_feature_sets_include_new_features():
    """全モデルの特徴量セット（FEATURE_SETS）に整合して含まれていること"""
    assert "building_depreciation_ratio" in FEATURE_SETS["kodate"]["first"]
    assert "demolition_cost_discount" in FEATURE_SETS["kodate"]["first"]
    assert "mansion_vintage_floor" in FEATURE_SETS["mansion"]["first"]
    assert "scale_vintage_interaction" in FEATURE_SETS["mansion"]["first"]
    assert "low_demand_land_discount" in FEATURE_SETS["tochi"]["first"]

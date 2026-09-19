# -*- coding: utf-8 -*-
import datetime
import pytest
from package.models.evaluation import MacroEconomicIndex
from package.ml.features import build_features, FEATURE_SETS, _init_global_caches


@pytest.fixture(autouse=True)
def setup_macro_data():
    """マクロ経済指標のテストデータをセットアップ"""
    MacroEconomicIndex.objects.update_or_create(
        year_month="2021-05",
        defaults={
            "repi_mansion": 165.2,
            "repi_kodate": 105.4,
            "repi_tochi": 100.1,
            "jgb_10y_yield": 0.08,
            "mortgage_fixed_rate": 1.30,
            "nikkei_225": 28860.0,
            "tse_reit_index": 2040.0,
            "construction_cost_index": 115.0,
            "cpi_core": 99.5,
        }
    )
    MacroEconomicIndex.objects.update_or_create(
        year_month="2026-09",
        defaults={
            "repi_mansion": 215.8,
            "repi_kodate": 120.3,
            "repi_tochi": 112.5,
            "jgb_10y_yield": 1.15,
            "mortgage_fixed_rate": 1.95,
            "nikkei_225": 42500.0,
            "tse_reit_index": 1850.0,
            "construction_cost_index": 138.5,
            "cpi_core": 108.2,
        }
    )
    _init_global_caches()


def test_macro_economic_index_model():
    """MacroEconomicIndex モデルの作成・クエリ検証"""
    item = MacroEconomicIndex.objects.get(year_month="2026-09")
    assert item.repi_mansion == 215.8
    assert item.jgb_10y_yield == 1.15
    assert item.nikkei_225 == 42500.0


def test_macro_features_extraction_legacy_vs_current():
    """2021年物件と2026年物件でマクロ特徴量と時間概念が正しく結合されるか検証"""
    # 2021年旧物件
    legacy_prop = {
        "propertyName": "旧ダイアパレス",
        "pageUrl": "https://example.com/legacy1",
        "inputDate": datetime.date(2021, 5, 15),
        "price": 35000000,
        "senyuMenseki": 65.0,
        "madori": "3LDK",
        "chikunengetsu": datetime.date(2005, 3, 1),
        "address": "東京都世田谷区",
        "railwayWalkMinute1": 7,
        "kaisu": "",  # 旧データの欠損（空文字）
        "traffic": None,  # 旧データの欠損（None）
    }

    feats_legacy = build_features(legacy_prop, property_type="mansion", base_date=datetime.date(2026, 9, 1))

    assert feats_legacy["is_legacy_data"] == 1.0
    assert feats_legacy["time_diff_months"] > 50.0
    assert abs(feats_legacy["macro_repi"] - 165.2) < 0.1
    assert abs(feats_legacy["macro_jgb_10y"] - 0.08) < 0.01
    assert abs(feats_legacy["macro_nikkei"] - 28860.0) < 1.0

    # 2026年最新物件
    current_prop = {
        "propertyName": "新築タワーレジデンス",
        "pageUrl": "https://example.com/current1",
        "inputDate": datetime.date(2026, 9, 10),
        "price": 85000000,
        "senyuMenseki": 72.0,
        "madori": "2LDK",
        "chikunengetsu": datetime.date(2024, 1, 1),
        "address": "東京都港区",
        "railwayWalkMinute1": 3,
        "kaisu": 15,
        "traffic": "JR山手線 田町駅 徒歩3分",
    }

    feats_current = build_features(current_prop, property_type="mansion", base_date=datetime.date(2026, 9, 1))

    assert feats_current["is_legacy_data"] == 0.0
    assert feats_current["time_diff_months"] < 2.0
    assert abs(feats_current["macro_repi"] - 215.8) < 0.1
    assert abs(feats_current["macro_jgb_10y"] - 1.15) < 0.01
    assert abs(feats_current["macro_nikkei"] - 42500.0) < 1.0


def test_features_in_feature_sets():
    """FEATURE_SETS にマクロ特徴量が含まれていることを検証"""
    for ptype in ["mansion", "kodate", "apartment", "tochi"]:
        first_feats = FEATURE_SETS[ptype]["first"]
        assert "time_diff_months" in first_feats
        assert "macro_repi" in first_feats
        assert "macro_jgb_10y" in first_feats
        assert "macro_nikkei" in first_feats
        assert "is_legacy_data" in first_feats


def test_time_decay_sample_weights():
    """train.py における時間減衰重み計算の検証"""
    from package.ml.train import calculate_time_decay_weights
    
    dates = [
        datetime.date(2026, 9, 1),   # 最新
        datetime.date(2024, 9, 1),   # 2年前
        datetime.date(2021, 5, 1),   # 約5年前
    ]
    weights = calculate_time_decay_weights(dates, base_date=datetime.date(2026, 9, 1))
    
    assert len(weights) == 3
    assert abs(weights[0] - 1.0) < 0.05
    assert weights[0] > weights[1] > weights[2]
    assert weights[2] >= 0.20  # 下限クリップ

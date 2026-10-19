import pytest

from package.ml.features.builder import build_features
from package.ml.features.feature_sets import FEATURE_SETS
from package.ml.inference.predictor import prepare_df_features


def test_regional_sensitivity_features_calculated():
    """都市部・地方の感応度差を変調する4特徴量が正しく算出されることを検証"""
    prop = {
        "pageUrl": "https://example.com/test_prop_1",
        "address": "東京都千代田区神田1丁目",
        "price": 80000000,
        "priceStr": "8,000万円",
        "area": 70.0,
        "senyuMenseki": 70.0,
        "chikunen": 10.0,
        "chikunengetsuStr": "2016年01月",
        "walk_min": 5,
        "station1": "東京",
        "railway1": "山手線",
        "kouzou": "RC",
    }

    feats = build_features(prop, "mansion")

    assert "walk_min_elasticity" in feats
    assert "effective_station_distance" in feats
    assert "chikunen_depreciation_resistance" in feats
    assert "area_value_intensity" in feats

    assert feats["walk_min_elasticity"] >= 0.0
    assert feats["effective_station_distance"] > 0.0
    assert feats["chikunen_depreciation_resistance"] >= 0.0
    assert feats["area_value_intensity"] > 0.0


def test_regional_sensitivity_features_contrast_urban_vs_rural():
    """都市部と地方で感応度変調特徴量が明確に異なる水準を示すことを検証"""
    urban_prop = {
        "pageUrl": "https://example.com/urban",
        "address": "東京都中央区銀座1丁目",
        "price": 100000000,
        "area": 60.0,
        "senyuMenseki": 60.0,
        "chikunen": 30.0,
        "walk_min": 10,
        "station1": "銀座",
        "kouzou": "RC",
    }

    rural_prop = {
        "pageUrl": "https://example.com/rural",
        "address": "鳥取県日野郡江府町",
        "price": 10000000,
        "area": 60.0,
        "senyuMenseki": 60.0,
        "chikunen": 30.0,
        "walk_min": 10,
        "station1": "江尾",
        "kouzou": "W",
    }

    urban_feats = build_features(urban_prop, "mansion")
    rural_feats = build_features(rural_prop, "mansion")

    # 1. 人口密度・立地密度に基づく駅徒歩弾力性（都市部の方が徒歩ペナルティが急峻）
    assert urban_feats["walk_min_elasticity"] > rural_feats["walk_min_elasticity"]

    # 2. 地価水準に基づく面積価値強度（都市部の方が面積の重みが大きい）
    assert urban_feats["area_value_intensity"] > rural_feats["area_value_intensity"]


def test_feature_sets_include_new_features():
    """FEATURE_SETS の全種別に新特徴量が含まれていること"""
    new_cols = [
        "walk_min_elasticity",
        "effective_station_distance",
        "chikunen_depreciation_resistance",
        "area_value_intensity",
    ]
    for ptype in ["mansion", "kodate", "apartment"]:
        for stage in ["first", "second"]:
            cols = FEATURE_SETS[ptype][stage]
            for nc in new_cols:
                assert nc in cols, f"{nc} not found in FEATURE_SETS[{ptype}][{stage}]"


def test_prepare_df_features_with_new_cols():
    """prepare_df_features が新特徴量を正しく float32 DataFrame に整形すること"""
    dummy_feat = {
        "walk_min_elasticity": 25.5,
        "effective_station_distance": 1.2,
        "chikunen_depreciation_resistance": 5.0,
        "area_value_intensity": 800.0,
    }
    cols = FEATURE_SETS["mansion"]["first"]
    df = prepare_df_features([dummy_feat], cols)
    assert df.shape == (1, len(cols))
    assert df["walk_min_elasticity"].iloc[0] == pytest.approx(25.5, rel=1e-3)

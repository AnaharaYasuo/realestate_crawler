"""
都市部・地方の駅アクセス感応度・地価フォールバック・広大地規模減退の包括的適正化テスト (Issue #1008)
"""
from unittest.mock import MagicMock

from package.ml.features.reference_data import (
    calculate_effective_walk_min,
    calculate_regional_sensitivity_features,
    _get_land_price_stats,
    LandPriceRecord,
)
from package.ml.features.appraisal import calculate_tochi_appraisal_factors


def test_effective_walk_min_no_arbitrary_compression_in_rural():
    """地方・郊外の低人口密度エリアでも、駅徒歩時間が0.4倍などに圧縮されないことを検証"""
    # 従来: pop_density=500 -> 0.475倍に圧縮され、徒歩20分が9.5分扱いになっていた
    walk_20 = calculate_effective_walk_min(
        walk_min=20, bus_use=0, bus_min=0.0, bus_walk=0.0, pop_density=500.0
    )
    assert walk_20 >= 20.0, f"Expected at least 20.0 walk_min, got {walk_20}"

    # バス利用時は所定のバス乗車換算が加算されること
    walk_bus = calculate_effective_walk_min(
        walk_min=20, bus_use=1, bus_min=10.0, bus_walk=5.0, pop_density=500.0
    )
    assert walk_bus >= 20.0


def test_rural_town_village_land_price_no_fallback_to_expensive_pref_average():
    """郡部・町・村において、県都を含む高額な県平均地価にフォールバックしないことを検証"""
    pref_res_cache = {
        "神奈川県": [
            LandPriceRecord("神奈川県", "横浜市西区", 1500000, 1200000, 1050000, 0.05, "residential"),
            LandPriceRecord("神奈川県", "川崎市中原区", 800000, 640000, 560000, 0.03, "residential"),
        ]
    }
    # 湯河原町など未登録町村の場合、県平均（115万円）ではなくNone（もしくは全国町村基準へのフォールバック誘導）を返すこと
    price, _rosenka, _fixed, _growth = _get_land_price_stats(
        "神奈川県", "足柄下郡湯河原町", "residential", pref_res_cache
    )
    # 町村部判定により、都市部中心の県平均地価をそのまま返さない
    assert price is None or price < 150000, f"Expected rural town to not inherit city average price, got {price}"

    # 町田市、蒲郡市、大和郡山市などの市部は県平均へ正しくフォールバックすること
    price_machida, _, _, _ = _get_land_price_stats(
        "神奈川県", "町田市", "residential", pref_res_cache
    )
    assert price_machida == 1150000.0

    price_yamato, _, _, _ = _get_land_price_stats(
        "神奈川県", "大和郡山市小泉町", "residential", pref_res_cache
    )
    assert price_yamato == 1150000.0

    # 町村名＋小字（湯河原町宮上など）も町村部として判定され県平均へのフォールバックが防止されること
    price_yugawara, _, _, _ = _get_land_price_stats(
        "神奈川県", "湯河原町宮上", "residential", pref_res_cache
    )
    assert price_yugawara is None or price_yugawara < 150000


def test_residual_land_value_applies_scale_discount():
    """広大な土地（1000㎡等）において、residual_land_valueに規模減退率（scale_discount）が適用されることを検証"""
    prop_mock = MagicMock()
    prop_mock.maguchi = 20.0
    prop_mock.road_width = 6.0
    prop_mock.road_direction = "南"
    prop_mock.road_type = "公道"
    prop_mock.road_structure = "舗装"
    prop_mock.chimoku = "宅地"
    prop_mock.youtoChiiki = "第一種低層住居専用地域"

    factors_small = calculate_tochi_appraisal_factors(
        property_obj=prop_mock,
        property_type="kodate",
        tochi_area=100.0,
        max_youseki=100.0,
        average_land_price=200000,
        setback_ratio_temp=0.0,
    )
    
    factors_large = calculate_tochi_appraisal_factors(
        property_obj=prop_mock,
        property_type="kodate",
        tochi_area=1000.0,
        max_youseki=100.0,
        average_land_price=200000,
        setback_ratio_temp=0.0,
    )

    # 1000㎡の土地は単純な10倍ではなく、規模減退（scale_discount < 1.0）により10倍未満に抑えられること
    ratio = factors_large.residual_land_value / factors_small.residual_land_value
    assert ratio < 10.0, f"Expected scale discount to suppress value under 10x, but got {ratio}"


def test_regional_sensitivity_features_gradient():
    """地方と都市部の駅力・徒歩感応度交互作用特徴量が正常に勾配を反映すること"""
    # 都市部駅近（徒歩3分、乗降客数10万人、人口密度10000）
    w_tokyo, dist_tokyo, _r_tokyo, inten_tokyo = calculate_regional_sensitivity_features(
        property_type="mansion",
        walk_min=3.0,
        pop_density=10000.0,
        passenger_volume=100000.0,
        average_land_price=1000000.0,
        area=70.0,
        tatemono_area=70.0,
        tochi_area=0.0,
        chikunen=10.0,
        scale_discount=1.0,
    )

    # 地方駅遠（徒歩20分、乗降客数500人、人口密度300）
    w_rural, dist_rural, _r_rural, inten_rural = calculate_regional_sensitivity_features(
        property_type="kodate",
        walk_min=20.0,
        pop_density=300.0,
        passenger_volume=500.0,
        average_land_price=40000.0,
        area=120.0,
        tatemono_area=120.0,
        tochi_area=300.0,
        chikunen=30.0,
        scale_discount=0.85,
    )

    assert w_tokyo > 0 and w_rural > 0
    assert dist_rural > dist_tokyo
    assert inten_tokyo > inten_rural

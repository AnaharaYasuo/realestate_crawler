import pytest
from package.ml.features import (
    build_features_batch,
    _get_nationwide_base_land_price,
)

class MockProperty:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_nationwide_base_land_price():
    # 新潟県新発田市: 住宅地 2万〜4万円/㎡
    res, comm = _get_nationwide_base_land_price("新潟県", "新発田市")
    assert 20000 <= res <= 50000, f"Expected Niigata res price around 30k, got {res}"
    assert 50000 <= comm <= 120000, f"Expected Niigata comm price around 80k, got {comm}"

    # 東京都港区: 住宅地 150万円以上、商業地 300万円以上
    res_minato, comm_minato = _get_nationwide_base_land_price("東京都", "港区")
    assert res_minato >= 1500000, f"Expected Tokyo Minato res price >= 1.5M, got {res_minato}"
    assert comm_minato >= 3000000, f"Expected Tokyo Minato comm price >= 3.0M, got {comm_minato}"

    # 静岡県知多郡/伊東市: 住宅地 3万〜8万円/㎡
    res_ito, comm_ito = _get_nationwide_base_land_price("静岡県", "伊東市")
    assert 30000 <= res_ito <= 90000, f"Expected Ito res price 30k-90k, got {res_ito}"

def test_bus_traffic_effective_walk_minutes():
    prop = MockProperty(
        senyuMenseki=73.75,
        address="愛知県知多郡南知多町",
        traffic="名鉄河和線 / 河和駅 【バス】28分 北大井 停歩7分",
        busUse1=1,
        railwayWalkMinute1=7,
        chikunengetsu="1996-06-01",
        kanrihi=93000000,  # バグデータ
        syuzenTsumitate=200000000,
    )
    feats = build_features_batch([prop], "mansion")
    feat = feats[0]
    # バス28分 + 停歩7分 => 等価徒歩分数は 30分以上であるべき
    assert feat["effective_walk_min"] >= 30, f"Effective walk min should be >= 30, got {feat['effective_walk_min']}"
    # 管理費の異常値（9300万円）がキャップされているべき
    assert feat["kanrihi"] <= 100000, f"Kanrihi should be capped, got {feat['kanrihi']}"

def test_shibata_vacant_house_valuation():
    prop = MockProperty(
        tochiMenseki=150.38,
        tatemonoMenseki=279.16,
        address="新潟県新発田市中央町",
        railwayWalkMinute1=10,
        kouzou="RC造",
        youseki=60.0,
        kenpei=60.0,
        chikunengetsu="1975-01-01",
    )
    feats = build_features_batch([prop], "kodate")
    feat = feats[0]
    # 新潟県新発田市の中央値地価は 35万円/㎡ ではなく 5万円/㎡ 以下であるべき
    assert feat["average_land_price"] <= 70000, f"Shibata land price should be <= 70,000, got {feat['average_land_price']}"
    # 従って残余地価や還元価値も 7,000万円 ではなく 1,500万円 以下であるべき
    assert feat["residual_land_value"] <= 1500, f"Residual land value should be <= 1,500万, got {feat['residual_land_value']}"

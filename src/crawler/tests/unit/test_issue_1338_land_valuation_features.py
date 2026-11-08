# -*- coding: utf-8 -*-
"""
Issue #1338: 土地価格推定の乖離是正テスト
- 取引事例比較法 (mkt_comparison_value) における土地面積 (tochi_area) 反映（50㎡固定バグの解消）
- setsumen / douro フィールドからの間口・前面道路幅員・方角・道路種別のフォールバック抽出
- 建築条件 (has_kenchiku_joken)・地勢 (chisei_score, is_flat_terrain)・防火地域 (bouka_score)・私道負担 (has_private_road_burden) の数値特徴量化
- 借地権・地代負担・心理的瑕疵・土地固有特徴量の FEATURE_SETS['tochi']（および関連種別）への完全配線
"""
import pytest
from package.ml.features import (
    FEATURE_SETS,
    build_features,
    calculate_appraisal_values,
)
from package.ml.features.appraisal import _extract_road_specs
from package.ml.features.parsers import (
    _calculate_desk_setback,
    parse_land_specific_features,
)


class DummyProp:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_tochi_mkt_comparison_value_scales_with_tochi_area():
    """土地 (tochi) の mkt_comparison_value が 50㎡ 固定にならず、tochi_area に比例して算出されること"""
    prop = DummyProp(kouzou="")
    mkt_master = {("東京都", "世田谷区", "tochi", 2): 80.0}  # 80万円/㎡

    small_vals = calculate_appraisal_values(
        property_obj=prop,
        property_type="tochi",
        area=0.0,
        tatemono_area=0.0,
        tochi_area=100.0,
        chikunen=20.0,
        max_youseki=200.0,
        average_land_price=800000,
        income=5000.0,
        mkt_comparison_master=mkt_master,
        address1="東京都",
        address2="世田谷区",
    )
    large_vals = calculate_appraisal_values(
        property_obj=prop,
        property_type="tochi",
        area=0.0,
        tatemono_area=0.0,
        tochi_area=300.0,
        chikunen=20.0,
        max_youseki=200.0,
        average_land_price=800000,
        income=5000.0,
        mkt_comparison_master=mkt_master,
        address1="東京都",
        address2="世田谷区",
    )

    assert small_vals.mkt_comparison_value == pytest.approx(8000.0)
    assert large_vals.mkt_comparison_value == pytest.approx(24000.0)
    assert large_vals.mkt_comparison_value == pytest.approx(small_vals.mkt_comparison_value * 3.0)


def test_extract_road_specs_supports_setsumen_and_douro():
    """三井・住友・東急等の setsumen や douro フィールドから間口・幅員・方角・種別が抽出されること"""
    prop = DummyProp(
        maguchi=None,
        setsumen=8.5,
        roadWidth=None,
        douroHaba=5.2,
        roadDirection="",
        douroMuki="南東",
        roadType="",
        douroKubun="公道",
        setsudou="",
        douro="南東側 公道 幅員5.2m 接面8.5m",
        chimoku="宅地",
    )
    maguchi_val, road_width_val, road_dir, road_type, _, _ = _extract_road_specs(prop)
    assert maguchi_val == pytest.approx(8.5)
    assert road_width_val == pytest.approx(5.2)
    assert road_dir == "南東"
    assert road_type == "公道"

    # douro テキストのみからのフォールバック検証
    prop_text_only = DummyProp(
        maguchi=None,
        setsumen=None,
        roadWidth=None,
        douroHaba=None,
        setsudou="",
        douro="北西側 私道 幅員3.0m 接面7.2m",
    )
    m_val2, rw_val2, r_dir2, r_type2, _, _ = _extract_road_specs(prop_text_only)
    assert m_val2 == pytest.approx(7.2)
    assert rw_val2 == pytest.approx(3.0)
    assert r_dir2 == "北西"
    assert r_type2 == "私道"

    # セットバック机上計算でも setsumen / douro が使われること (幅員3.0m -> 後退0.5m * 間口7.2m = 3.6㎡)
    sb_area = _calculate_desk_setback(prop_text_only)
    assert sb_area == pytest.approx(3.6)


def test_parse_land_specific_features():
    """建築条件・地勢・防火規制・私道負担の数値特徴量化テスト"""
    # 1. 建築条件付き・傾斜地・防火地域・私道負担あり
    prop_cond = DummyProp(
        kenchikuJoken="建築条件付",
        chisei="傾斜地",
        boukaChiiki="防火地域",
        privateRoadBurden="私道負担あり 15.2㎡",
        shidoMenseki=15.2,
    )
    feats_cond = parse_land_specific_features(prop_cond, "")
    assert feats_cond["has_kenchiku_joken"] == 1.0
    assert feats_cond["chisei_score"] < 0.85
    assert feats_cond["is_flat_terrain"] == 0.0
    assert feats_cond["bouka_score"] == pytest.approx(1.05)
    assert feats_cond["has_private_road_burden"] == 1.0

    # 2. 建築条件なし・平坦・準防火・私道負担なし
    prop_clean = DummyProp(
        kenchikuJoken="建築条件なし",
        chisei="平坦",
        boukaChiiki="準防火地域",
        privateRoadBurden="無",
        shidoMenseki=0.0,
    )
    feats_clean = parse_land_specific_features(prop_clean, "建築条件なし 更地")
    assert feats_clean["has_kenchiku_joken"] == 0.0
    assert feats_clean["chisei_score"] == pytest.approx(1.00)
    assert feats_clean["is_flat_terrain"] == 1.0
    assert feats_clean["bouka_score"] == pytest.approx(1.00)
    assert feats_clean["has_private_road_burden"] == 0.0


@pytest.mark.django_db
def test_tochi_feature_sets_include_critical_land_and_rights_features():
    """FEATURE_SETS['tochi'] に借地権・地代・瑕疵・土地固有特徴量が含まれ、build_features で数値出力されること"""
    expected_tochi_features = [
        "has_kenchiku_joken",
        "chisei_score",
        "is_flat_terrain",
        "bouka_score",
        "has_private_road_burden",
        "is_leasehold",
        "monthly_land_rent",
        "annual_land_rent",
        "land_rent_liability",
        "land_rent_ratio",
        "has_psychological_defect",
    ]
    for stage in ("first", "second"):
        for col in expected_tochi_features:
            assert col in FEATURE_SETS["tochi"][stage], f"'{col}' missing from FEATURE_SETS['tochi']['{stage}']"

    prop = DummyProp(
        address="東京都世田谷区玉川1丁目",
        address1="東京都",
        address2="世田谷区",
        station1="二子玉川",
        railwayWalkMinute1=8,
        tochiMenseki=150.0,
        price=90000000,
        youseki=200,
        kenpei=60,
        youtoChiiki="第一種低層住居専用地域",
        kenchikuJoken="建築条件付",
        chisei="ひな段",
        boukaChiiki="準防火地域",
        privateRoadBurden="負担あり 10㎡",
        tochikenri="普通借地権",
        chidai=25000,
        biko="告知事項あり",
    )
    feats = build_features(prop, "tochi")
    for col in expected_tochi_features:
        assert col in feats
        assert isinstance(feats[col], (int, float))

    assert feats["has_kenchiku_joken"] == 1.0
    assert feats["chisei_score"] == pytest.approx(0.92)
    assert feats["is_flat_terrain"] == 0.0
    assert feats["has_private_road_burden"] == 1.0
    assert feats["is_leasehold"] == 1.0
    assert feats["monthly_land_rent"] == pytest.approx(2.5)
    assert feats["has_psychological_defect"] == 1.0

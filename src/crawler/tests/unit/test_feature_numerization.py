# -*- coding: utf-8 -*-
"""
特徴量完全数値化テスト (test_feature_numerization.py)

文字列（方角、道路種別、接道形態、地目、構造、会社、用途地域、間取り、階数等）が
機械学習モデル向けに完全数値化（連続スコア、方位角、順序ランク、ダミーフラグ等）
されているかを網羅的に検証。
"""
import pytest
from package.ml.features import (
    parse_road_direction_features,
    parse_road_type_features,
    parse_road_structure_features,
    parse_chimoku_features,
    parse_kouzou_features,
    parse_company_features,
    parse_youto_zone_features,
    parse_madori_layout_features,
    parse_floor_features,
    build_features,
    FEATURE_SETS,
)


class MockProperty:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_road_direction_numerization():
    """接道方角の数値化（角度・採光スコア・南向きフラグ）テスト"""
    south = parse_road_direction_features("南")
    assert south["road_direction_angle"] == 180.0
    assert south["sunlight_score"] == 1.00
    assert south["is_south_facing"] == 1.0

    north = parse_road_direction_features("北")
    assert north["road_direction_angle"] == 0.0
    assert north["sunlight_score"] == 0.75
    assert north["is_south_facing"] == 0.0

    southeast = parse_road_direction_features("南東")
    assert southeast["road_direction_angle"] == 135.0
    assert southeast["sunlight_score"] == 0.95
    assert southeast["is_south_facing"] == 1.0


def test_road_type_numerization():
    """道路種別の数値化（公道・私道スコア）テスト"""
    pub = parse_road_type_features("公道")
    assert pub["road_type_score"] == 1.00
    assert pub["is_public_road"] == 1.0
    assert pub["is_private_road"] == 0.0

    pri = parse_road_type_features("私道")
    assert pri["road_type_score"] == 0.90
    assert pri["is_public_road"] == 0.0
    assert pri["is_private_road"] == 1.0


def test_road_structure_numerization():
    """接道構造・形態の数値化（角地・両面道路プレミアム）テスト"""
    corner = parse_road_structure_features("角地")
    assert corner["road_structure_score"] == 1.08
    assert corner["is_corner_lot"] == 1.0
    assert corner["is_double_sided_road"] == 0.0

    double = parse_road_structure_features("両面道路")
    assert double["road_structure_score"] == 1.06
    assert double["is_double_sided_road"] == 1.0

    mid = parse_road_structure_features("中間地")
    assert mid["road_structure_score"] == 1.00
    assert mid["is_corner_lot"] == 0.0


def test_chimoku_numerization():
    """地目の数値化（宅地・雑種地・農地・山林スコア）テスト"""
    res = parse_chimoku_features("宅地")
    assert res["chimoku_score"] == 1.00
    assert res["is_residential_chimoku"] == 1.0

    forest = parse_chimoku_features("山林")
    assert forest["chimoku_score"] == 0.70
    assert forest["is_residential_chimoku"] == 0.0


def test_kouzou_numerization():
    """建物構造の数値化（耐久ランク・耐火スコア・RC/木造フラグ）テスト"""
    rc = parse_kouzou_features("RC")
    assert rc["kouzou_durability_rank"] == 4.0
    assert rc["kouzou_fireproof_score"] == 1.00
    assert rc["is_rc_or_src"] == 1.0
    assert rc["is_wood"] == 0.0

    wood = parse_kouzou_features("木造")
    assert wood["kouzou_durability_rank"] == 1.0
    assert wood["kouzou_fireproof_score"] == 0.60
    assert wood["is_rc_or_src"] == 0.0
    assert wood["is_wood"] == 1.0


def test_company_numerization():
    """不動産会社の数値化（大手ティア・ブランド力）テスト"""
    major = parse_company_features("mitsui")
    assert major["company_tier"] == 3.0
    assert major["is_major_company"] == 1.0

    other = parse_company_features("athome")
    assert other["company_tier"] == 1.0
    assert other["is_major_company"] == 0.0


def test_youto_zone_numerization():
    """用途地域規制の数値化（住居・商業・工業系フラグおよび住環境ランク）テスト"""
    teiso = parse_youto_zone_features("第1種低層住居専用地域")
    assert teiso["is_residential_zone"] == 1.0
    assert teiso["is_commercial_zone"] == 0.0
    assert teiso["zone_rank"] == 5.0

    comm = parse_youto_zone_features("商業地域")
    assert comm["is_residential_zone"] == 0.0
    assert comm["is_commercial_zone"] == 1.0
    assert comm["zone_rank"] == 3.0


def test_madori_and_floor_numerization():
    """間取りおよび所在階の数値化テスト"""
    madori = parse_madori_layout_features("3LDK")
    assert madori["room_count"] == 3.0
    assert madori["has_ldk"] == 1.0
    assert madori["is_studio"] == 0.0

    studio = parse_madori_layout_features("1R")
    assert studio["room_count"] == 1.0
    assert studio["is_studio"] == 1.0

    floor = parse_floor_features("5階", "15階建")
    assert floor["floor_number"] == 5.0
    assert floor["total_floors"] == 15.0
    assert floor["floor_ratio"] == pytest.approx(0.333, abs=0.01)
    assert floor["is_top_floor"] == 0.0
    assert floor["is_first_floor"] == 0.0


def test_all_features_strictly_numeric():
    """全4種別のFEATURE_SETSに含まれる全特徴量がすべて数値型（int/float）であることを検証"""
    prop = MockProperty(
        senyuMenseki=65.0,
        tochiMenseki=100.0,
        tatemonoMenseki=90.0,
        chikunengetsu="2010-04-01",
        railwayWalkMinute1=6,
        address1="東京都",
        address2="世田谷区",
        station1="三軒茶屋駅",
        company="mitsui",
        kouzou="RC造",
        roadDirection="南東",
        roadType="公道",
        roadStructure="角地",
        chimoku="宅地",
        youtoChiiki="第1種低層住居専用地域",
        madori="3LDK",
        kai="5階",
        chijo="10階建"
    )

    for ptype in ["mansion", "kodate", "apartment", "tochi"]:
        feats = build_features(prop, ptype)
        first_cols = FEATURE_SETS[ptype]["first"]
        for col in first_cols:
            assert col in feats, f"Missing feature '{col}' in feats for {ptype}"
            val = feats[col]
            assert isinstance(val, (int, float)), f"Feature '{col}' in {ptype} must be numeric, got {type(val)}: {val}"

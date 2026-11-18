# -*- coding: utf-8 -*-
"""Issue #1565: 割安物件通知一次スクリーニングにおける乗降客数非公開・データなし駅の足切りテスト"""
from types import SimpleNamespace
from unittest.mock import patch

from scripts.ops.send_recommendations import (
    _evaluate_candidate,
    is_excessive_walk_minutes,
    is_depopulated_station_area,
    MAX_RECOMMEND_WALK_MINUTES,
    MIN_RECOMMEND_PASSENGER_VOLUME,
)


def _prop(**kwargs):
    base = {
        "pageUrl": "https://example.com/p1",
        "price": 30000000,
        "station1": "渋谷",
        "railwayWalkMinute1": 7,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _eval(ptype="mansion", pred=4500.0):
    return SimpleNamespace(
        id=1,
        property_type=ptype,
        property_url="https://example.com/p1",
        investment_score=None,
        total_investment_score=None,
        first_stage_predicted_price=pred,
        second_stage_predicted_price=None,
    )


def test_constants():
    assert MAX_RECOMMEND_WALK_MINUTES == 14
    assert MIN_RECOMMEND_PASSENGER_VOLUME == 10000


def test_walk_minutes_filter():
    # 徒歩14分以内は合格
    prop_10min = _prop(railwayWalkMinute1=10)
    assert is_excessive_walk_minutes(prop_10min) is False

    prop_14min = _prop(railwayWalkMinute1=14)
    assert is_excessive_walk_minutes(prop_14min) is False

    # 徒歩15分以上は足切り除外
    prop_15min = _prop(railwayWalkMinute1=15)
    assert is_excessive_walk_minutes(prop_15min) is True

    prop_20min = _prop(railwayWalkMinute1=20)
    assert is_excessive_walk_minutes(prop_20min) is True

    # 文字列フィールドからの抽出
    prop_str = _prop(railwayWalkMinute1=None, railwayWalkMinute1Str="徒歩18分")
    assert is_excessive_walk_minutes(prop_str) is True

    prop_str_ok = _prop(railwayWalkMinute1=None, railwayWalkMinute1Str="8分")
    assert is_excessive_walk_minutes(prop_str_ok) is False

    # 複数経路がある場合：最短経路が14分以内なら合格
    prop_multi = _prop(
        station1="遠い駅",
        railwayWalkMinute1=18,
        station2="近い駅",
        railwayWalkMinute2=6,
    )
    assert is_excessive_walk_minutes(prop_multi) is False

    # 複数経路がすべて15分以上なら足切り除外
    prop_multi_far = _prop(
        station1="駅A",
        railwayWalkMinute1=16,
        station2="駅B",
        railwayWalkMinute2=22,
    )
    assert is_excessive_walk_minutes(prop_multi_far) is True

    # 交通情報が未記載の場合は徒歩フィルタでは除外しない（フェールセーフ）
    prop_no_info = SimpleNamespace(pageUrl="https://example.com/p_none", price=30000000)
    assert is_excessive_walk_minutes(prop_no_info) is False


def test_station_passenger_volume_filter():
    # 1. 乗降客数1万人以上の駅は合格
    with patch("scripts.ops.send_recommendations.query_station_volume") as mock_vol:
        mock_vol.return_value = 50000
        prop = _prop(station1="中目黒", railwayWalkMinute1=5)
        assert is_depopulated_station_area(prop) is False

    # 2. 乗降客数1万人未満の過疎駅は足切り除外
    with patch("scripts.ops.send_recommendations.query_station_volume") as mock_vol:
        mock_vol.return_value = 2500  # 1日2500人
        prop_depop = _prop(station1="過疎駅", railwayWalkMinute1=5)
        assert is_depopulated_station_area(prop_depop) is True

    # 3. 乗降客数が非公開・データなしの駅（None）も足切り除外 (Issue #1565)
    with patch("scripts.ops.send_recommendations.query_station_volume") as mock_vol:
        mock_vol.return_value = None
        prop_unknown = _prop(station1="非公開駅", railwayWalkMinute1=5)
        assert is_depopulated_station_area(prop_unknown) is True

    # 4. 駅情報が一切ない物件は駅の判定ができないため除外しない（フェールセーフ・Issue #1244等の互換性）
    prop_no_station = SimpleNamespace(pageUrl="https://example.com/no_station", price=30000000)
    assert is_depopulated_station_area(prop_no_station) is False

    # 5. 複数駅がある場合：1駅が非公開/データなしでも、もう1駅が1万人以上なら合格
    with patch("scripts.ops.send_recommendations.query_station_volume") as mock_vol:
        def side_effect(st_name):
            if "非公開" in st_name:
                return None
            return 80000
        mock_vol.side_effect = side_effect

        prop_multi = _prop(
            station1="非公開駅",
            railwayWalkMinute1=5,
            station2="主要駅",
            railwayWalkMinute2=8,
        )
        assert is_depopulated_station_area(prop_multi) is False

    # 6. 複数駅がある場合：非公開駅と過疎駅（1万人未満）のみの場合は足切り除外
    with patch("scripts.ops.send_recommendations.query_station_volume") as mock_vol:
        def side_effect2(st_name):
            if "非公開" in st_name:
                return None
            return 3000
        mock_vol.side_effect = side_effect2

        prop_multi_sparse = _prop(
            station1="非公開駅",
            railwayWalkMinute1=5,
            station2="過疎駅",
            railwayWalkMinute2=8,
        )
        assert is_depopulated_station_area(prop_multi_sparse) is True


def test_evaluate_candidate_integrates_walk_and_station_filters():
    # 1. 正常な物件（徒歩7分、乗降客数5万人）-> 通過
    with patch("scripts.ops.send_recommendations.query_station_volume") as mock_vol:
        mock_vol.return_value = 50000
        prop_ok = _prop(station1="恵比寿", railwayWalkMinute1=7)
        is_rec, _reason, _prio = _evaluate_candidate(_eval(), prop_ok)
        assert is_rec is True

    # 2. 徒歩15分以上の物件 -> 一次フィルタでスキップ
    with patch("scripts.ops.send_recommendations.query_station_volume") as mock_vol:
        mock_vol.return_value = 50000
        prop_far = _prop(station1="恵比寿", railwayWalkMinute1=16)
        is_rec, _reason, prio = _evaluate_candidate(_eval(), prop_far)
        assert is_rec is False
        assert prio == 0.0

    # 3. 過疎駅（乗降客数4,000人）の物件 -> 一次フィルタでスキップ
    with patch("scripts.ops.send_recommendations.query_station_volume") as mock_vol:
        mock_vol.return_value = 4000
        prop_sparse = _prop(station1="閑散駅", railwayWalkMinute1=6)
        is_rec, _reason, prio = _evaluate_candidate(_eval(), prop_sparse)
        assert is_rec is False
        assert prio == 0.0

    # 4. 乗降客数非公開・データなし駅の物件 -> 一次フィルタでスキップ (Issue #1565)
    with patch("scripts.ops.send_recommendations.query_station_volume") as mock_vol:
        mock_vol.return_value = None
        prop_unknown = _prop(station1="非公開駅", railwayWalkMinute1=6)
        is_rec, _reason, prio = _evaluate_candidate(_eval(), prop_unknown)
        assert is_rec is False
        assert prio == 0.0

    # 5. 投資物件にも同様に足切りが適用されること
    with patch("scripts.ops.send_recommendations.query_station_volume") as mock_vol:
        mock_vol.return_value = None
        prop_inv_unknown = _prop(station1="非公開駅", railwayWalkMinute1=5)
        eval_inv = _eval(ptype="investmentapartment", pred=5000.0)
        eval_inv.total_investment_score = 90.0
        eval_inv.investment_score = 90.0
        is_rec, _reason, prio = _evaluate_candidate(eval_inv, prop_inv_unknown)
        assert is_rec is False
        assert prio == 0.0

# -*- coding: utf-8 -*-
"""Issue #1244: 割安物件ピックアップ対象からバス利用物件を除外する。"""
from types import SimpleNamespace

from scripts.ops.send_recommendations import _evaluate_candidate, is_bus_access_property


def _prop(**kwargs):
    base = {"pageUrl": "https://example.com/p", "price": 10000000}
    base.update(kwargs)
    return SimpleNamespace(**base)


def _eval(ptype="mansion", pred=1333.0):
    return SimpleNamespace(
        id=1, property_type=ptype, property_url="https://example.com/p",
        investment_score=None, total_investment_score=None,
        first_stage_predicted_price=pred, second_stage_predicted_price=None,
    )


def test_bus_only_property_is_excluded():
    prop = _prop(station1="中山", busUse1=1, busWalkMinute1=12)
    assert is_bus_access_property(prop) is True
    assert _evaluate_candidate(_eval(), prop)[0] is False


def test_bus_minute_without_flag_is_bus():
    prop = _prop(station1="中山", busUse1=None, busWalkMinute1=8)
    assert is_bus_access_property(prop) is True


def test_walk_route_alongside_bus_is_kept():
    prop = _prop(station1="中山", busUse1=1, busWalkMinute1=12, station2="鴨居", busUse2=0)
    assert is_bus_access_property(prop) is False
    assert _evaluate_candidate(_eval(), prop)[0] is True


def test_no_station_info_is_kept():
    prop = _prop()
    assert is_bus_access_property(prop) is False
    assert _evaluate_candidate(_eval(), prop)[0] is True


def test_investment_bus_property_is_excluded():
    prop = _prop(station1="中山", busUse1=1)
    assert _evaluate_candidate(_eval("investmentapartment"), prop)[0] is False

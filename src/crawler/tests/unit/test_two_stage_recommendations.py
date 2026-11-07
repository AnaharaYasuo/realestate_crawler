# -*- coding: utf-8 -*-
import pytest
from unittest.mock import MagicMock, patch
from scripts.ops.send_recommendations import (
    _get_property_category,
    _rank_by_qualitative_score,
    _select_two_stage_recommendations,
)

def test_get_property_category():
    """物件種別から4大カテゴリ（mansion, kodate, tochi, investment）への分類を検証"""
    assert _get_property_category("mansion") == "mansion"
    assert _get_property_category("kodate") == "kodate"
    assert _get_property_category("tochi") == "tochi"
    assert _get_property_category("investmentapartment") == "investment"
    assert _get_property_category("investmentkodate") == "investment"
    assert _get_property_category("apartment") == "investment"
    assert _get_property_category("invest_apartment") == "investment"
    assert _get_property_category("other_unknown") == "other"


def test_rank_by_qualitative_score():
    """定性レーティング(AAA/AA/A/B)およびML割安度優先度による複合スコアリングを検証"""
    # 候補1: AAA, ML優先度 30.0 -> 定性重視で上位
    rec_aaa = MagicMock()
    rec_aaa.investment_rating = "AAA"
    score_aaa = _rank_by_qualitative_score(rec_aaa, ml_priority=30.0)

    # 候補2: AA, ML優先度 35.0
    rec_aa = MagicMock()
    rec_aa.investment_rating = "AA"
    score_aa = _rank_by_qualitative_score(rec_aa, ml_priority=35.0)

    # 候補3: A, ML優先度 40.0
    rec_a = MagicMock()
    rec_a.investment_rating = "A"
    score_a = _rank_by_qualitative_score(rec_a, ml_priority=40.0)

    # 候補4: B, ML優先度 50.0
    rec_b = MagicMock()
    rec_b.investment_rating = "B"
    score_b = _rank_by_qualitative_score(rec_b, ml_priority=50.0)

    assert score_aaa > score_aa
    assert score_aa > score_a
    assert score_a > score_b


def test_select_two_stage_recommendations_filters_and_limits():
    """各種別ごとに上位5件（計最大20件）が選定されることを検証"""
    candidates_by_category = {
        "mansion": [],
        "kodate": [],
        "tochi": [],
        "investment": [],
    }

    # 各カテゴリに10件ずつ候補を作成
    for cat in ["mansion", "kodate", "tochi", "investment"]:
        for i in range(10):
            eval_rec = MagicMock()
            eval_rec.id = f"{cat}_{i}"
            eval_rec.property_url = f"https://example.com/{cat}/{i}"
            eval_rec.property_type = cat
            # 上位5件にAAA、次がAA、Aと設定
            eval_rec.investment_rating = "AAA" if i < 3 else ("AA" if i < 6 else "A")
            prop = MagicMock()
            ml_priority = 30.0 - i
            reason = "割安"
            candidates_by_category[cat].append((ml_priority, eval_rec, prop, reason))

    selected = _select_two_stage_recommendations(
        candidates_by_category,
        quota_per_category=5,
    )

    # 全体件数は 4カテゴリ × 5件 = 20件
    assert len(selected) == 20

    # 各カテゴリからちょうど5件ずつ選出されていること
    cat_counts = {}
    for item in selected:
        cat = _get_property_category(item[1].property_type)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    
    assert cat_counts["mansion"] == 5
    assert cat_counts["kodate"] == 5
    assert cat_counts["tochi"] == 5
    assert cat_counts["investment"] == 5


def test_extract_property_display_info_and_report_args():
    """物件表示用情報の抽出およびレポート生成関数の引数整合性を検証 (Issue #1314)"""
    from scripts.ops.send_recommendations import _extract_property_display_info

    prop = MagicMock()
    prop.price = 35000000
    prop.address = "東京都世田谷区桜丘4丁目"
    for i in ["", "1", "2", "3", "Kyoto"]:
        setattr(prop, f"address{i}", "東京都世田谷区桜丘4丁目" if i == "" else None)
    for i in range(1, 4):
        setattr(prop, f"railway{i}", None)
        setattr(prop, f"station{i}", None)
        setattr(prop, f"bus{i}", None)
        setattr(prop, f"busStation{i}", None)
        setattr(prop, f"railwayWalkMinute{i}Str", None)
    prop.traffic = "小田急線 千歳船橋駅 徒歩10分"

    eval_rec = MagicMock()
    eval_rec.property_type = "mansion"
    eval_rec.first_stage_predicted_price = 4500
    eval_rec.second_stage_predicted_price = None

    ptype_jp, asking_price_man, pred_price, address, access = _extract_property_display_info(prop, eval_rec)

    assert ptype_jp == "中古マンション"
    assert asking_price_man == 3500
    assert pred_price == 4500.0
    assert "世田谷区" in address
    assert "千歳船橋駅" in access

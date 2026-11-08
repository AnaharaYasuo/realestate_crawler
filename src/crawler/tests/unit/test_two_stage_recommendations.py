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


def test_select_two_stage_recommendations_prioritizes_existing_rating_and_ml_priority():
    """未評価（rating なし）と評価済み（rating あり）が混在する場合のスコアリング順序を検証"""
    candidates_by_category = {
        "mansion": [
            # 1. 未評価だがML割安度が極めて高い (ml_priority=50.0 -> スコア 200 + 50 = 250)
            (50.0, MagicMock(id=1, property_type="mansion", investment_rating=None), MagicMock(), "超割安"),
            # 2. AAA評価 (rating=AAA, ml_priority=25.0 -> スコア 1000 + 25 = 1025)
            (25.0, MagicMock(id=2, property_type="mansion", investment_rating="AAA"), MagicMock(), "AAA"),
            # 3. 未評価 (ml_priority=30.0 -> スコア 200 + 30 = 230)
            (30.0, MagicMock(id=3, property_type="mansion", investment_rating=""), MagicMock(), "割安"),
        ]
    }
    selected = _select_two_stage_recommendations(candidates_by_category, quota_per_category=2)
    assert len(selected) == 2
    # 1位はAAA (id=2), 2位は未評価だが高ML優先度 (id=1)
    assert selected[0][1].id == 2
    assert selected[1][1].id == 1


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


def test_send_recommendations_lazy_report_generation_and_timeout():
    """send_recommendations において最終選抜分のみレポート生成され、予算枯渇時にスキップされることを検証"""
    from scripts.ops import send_recommendations as sr_module

    # モック候補の準備
    mock_candidates = []
    for i in range(10):
        rec = MagicMock()
        rec.id = i
        rec.property_url = f"https://example.com/prop/{i}"
        rec.property_type = "mansion"
        rec.investment_rating = None
        rec.ai_evaluation_summary = None
        rec.is_slack_notified = False
        rec.is_published = True
        rec.needs_recrawl = False
        rec.first_stage_predicted_price = 4000
        rec.second_stage_predicted_price = None
        mock_candidates.append(rec)

    mock_prop = MagicMock()
    mock_prop.price = 30000000
    mock_prop.pageUrl = "https://example.com/prop/0"

    with patch.object(sr_module, "close_old_connections"), \
         patch.object(sr_module, "bound_mysql_timeouts"), \
         patch.object(sr_module, "_notify_status"), \
         patch.object(sr_module, "_fetch_recommendation_candidates", return_value=mock_candidates), \
         patch.object(sr_module, "batch_resolve_properties", return_value={rec.property_url: mock_prop for rec in mock_candidates}), \
         patch.object(sr_module, "_evaluate_candidate", return_value=(True, "割安", 30.0)), \
         patch.object(sr_module, "generate_professional_and_danchou_report") as mock_gen_report, \
         patch.object(sr_module, "_dispatch_single_recommendation", return_value=True) as mock_dispatch, \
         patch.object(sr_module.time, "sleep"):

        # 1. 正常系: 5件選抜され、選抜された5件のみレポート生成が呼ばれる
        sr_module.send_recommendations()
        assert mock_gen_report.call_count == 5
        assert mock_dispatch.call_count == 5

    # 2. タイムアウト系: 残り時間が0の場合、レポート生成がスキップされ通知のみ行われる
    with patch.object(sr_module, "close_old_connections"), \
         patch.object(sr_module, "bound_mysql_timeouts"), \
         patch.object(sr_module, "_notify_status"), \
         patch.object(sr_module, "_fetch_recommendation_candidates", return_value=mock_candidates), \
         patch.object(sr_module, "batch_resolve_properties", return_value={rec.property_url: mock_prop for rec in mock_candidates}), \
         patch.object(sr_module, "_evaluate_candidate", return_value=(True, "割安", 30.0)), \
         patch.object(sr_module, "generate_professional_and_danchou_report") as mock_gen_report, \
         patch.object(sr_module, "_dispatch_single_recommendation", return_value=True) as mock_dispatch, \
         patch.object(sr_module.time, "sleep"), \
         patch.object(sr_module, "time") as mock_time:

        mock_time.time.side_effect = [1000.0, 2000.0, 2000.0, 2000.0]

        sr_module.send_recommendations()
        # タイムアウトにより生成はスキップされるが配信は5件完遂
        assert mock_gen_report.call_count == 0
        assert mock_dispatch.call_count == 5

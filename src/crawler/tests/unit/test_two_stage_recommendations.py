# -*- coding: utf-8 -*-
import pytest
from unittest.mock import MagicMock, patch
from scripts.ops.send_recommendations import (
    _get_property_category,
    _rank_by_capital_gain_score,
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


def test_rank_by_capital_gain_score_and_qualitative_score():
    """ML理論価格アンカリングを排除し、AIキャピタルゲインスコアおよび定性レーティング優先を検証 (Issue #1333)"""
    # 候補1: AAA評価 + AIキャピタルゲインスコア 95点 -> 400 + 95 = 495点
    rec1 = MagicMock()
    rec1.investment_rating = "AAA"
    rec1.capital_gain_score = 95.0
    score1 = _rank_by_capital_gain_score(rec1)

    # 候補2: AAA評価 + AIキャピタルゲインスコア 70点 -> 400 + 70 = 470点
    rec2 = MagicMock()
    rec2.investment_rating = "AAA"
    rec2.capital_gain_score = 70.0
    score2 = _rank_by_capital_gain_score(rec2)

    # 候補3: AA評価 + AIキャピタルゲインスコア 90点 -> 300 + 90 = 390点
    rec3 = MagicMock()
    rec3.investment_rating = "AA"
    rec3.capital_gain_score = 90.0
    score3 = _rank_by_capital_gain_score(rec3)

    # 候補4: A評価 + AIキャピタルゲインスコア 50点 -> 200 + 50 = 250点
    rec4 = MagicMock()
    rec4.investment_rating = "A"
    rec4.capital_gain_score = 50.0
    score4 = _rank_by_capital_gain_score(rec4)

    # 候補5: 未評価 (ratingなし, cg_scoreなし) -> 50点 (ML理論価格による加算は一切行われない)
    rec5 = MagicMock()
    rec5.investment_rating = None
    rec5.capital_gain_score = None
    # ml_priority=999.0 を渡しても反映されない
    score5 = _rank_by_capital_gain_score(rec5, ml_priority=999.0)

    assert score1 > score2
    assert score2 > score3
    assert score3 > score4
    assert score4 > score5
    assert score5 == 50.0

    # 後方互換性エイリアス _rank_by_qualitative_score の検証
    assert _rank_by_qualitative_score(rec1) == score1


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
            # 上位5件に高いキャピタルゲインスコアと高レーティングを設定
            eval_rec.investment_rating = "AAA" if i < 3 else ("AA" if i < 6 else "A")
            eval_rec.capital_gain_score = 90.0 - (i * 5)
            prop = MagicMock()
            ml_priority = 10.0 + i  # ML理論価格優先度は逆転していても無視される
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

    # 各カテゴリ内でキャピタルゲインスコア上位が選出されていること (i=0が1位)
    for cat in ["mansion", "kodate", "tochi", "investment"]:
        cat_selected = [item for item in selected if _get_property_category(item[1].property_type) == cat]
        assert cat_selected[0][1].id == f"{cat}_0"


def test_select_two_stage_recommendations_prioritizes_ai_capital_gain():
    """未評価（rating なし）とAI評価済み（capital_gain_scoreあり）が混在する場合のスコアリング順序を検証"""
    candidates_by_category = {
        "mansion": [
            # 1. 未評価 (ml_priority=50.0だがスコアは50点)
            (50.0, MagicMock(id=1, property_type="mansion", investment_rating=None, capital_gain_score=None), MagicMock(), "超割安"),
            # 2. AAA評価 + 高キャピタルゲイン (rating=AAA, cg_score=90 -> 490点)
            (25.0, MagicMock(id=2, property_type="mansion", investment_rating="AAA", capital_gain_score=90.0), MagicMock(), "AAA"),
            # 3. 未評価 (ml_priority=30.0 -> 50点)
            (30.0, MagicMock(id=3, property_type="mansion", investment_rating="", capital_gain_score=None), MagicMock(), "割安"),
        ]
    }
    selected = _select_two_stage_recommendations(candidates_by_category, quota_per_category=2)
    assert len(selected) == 2
    # 1位はAAA + 高キャピタルゲイン (id=2)
    assert selected[0][1].id == 2


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
        rec.capital_gain_score = None
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

        # 1. 正常系: 3件選抜され、選抜された3件のみレポート生成が呼ばれる
        sr_module.send_recommendations()
        assert mock_gen_report.call_count == 3
        assert mock_dispatch.call_count == 3

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
        # タイムアウトにより生成はスキップされるが配信は3件完遂
        assert mock_gen_report.call_count == 0
        assert mock_dispatch.call_count == 3

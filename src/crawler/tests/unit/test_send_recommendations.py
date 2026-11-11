# -*- coding: utf-8 -*-
import pytest
import datetime
from django.utils import timezone
from unittest.mock import patch
from package.models.evaluation import PropertyEvaluation
from scripts.ops.send_recommendations import send_recommendations, normalize_asking_price_man

@pytest.mark.django_db
def test_send_recommendations_query_syntax():
    """PropertyEvaluation モデルに対する直近48時間クエリが FieldError を出さずに実行できることを検証"""
    threshold_48h = timezone.now() - datetime.timedelta(hours=48)
    
    # analyzed_at を使ったクエリが例外なく成功すること
    try:
        from django.db.models import Q
        candidates = list(PropertyEvaluation.objects.filter(
            is_slack_notified=False
        ).filter(
            Q(analyzed_at__gte=threshold_48h) | Q(analyzed_at__isnull=True)
        )[:10])
        assert isinstance(candidates, list)
    except Exception as e:
        pytest.fail(f"Query raised unexpected exception: {e}")

@pytest.mark.django_db
def test_send_recommendations_execution(monkeypatch):
    """send_recommendations() が例外なく完走することを検証"""
    with patch("scripts.ops.send_recommendations.send_slack_message", return_value=True):
        try:
            send_recommendations()
        except Exception as e:
            pytest.fail(f"send_recommendations() crashed: {e}")

def test_normalize_asking_price_man():
    """価格単位の正規化処理が万円単位および円単位の両方で正しく動作することを検証"""
    # 1. 円単位の通常価格（例: 4590万円 = 45,900,000円）
    assert normalize_asking_price_man(45900000) == 4590
    assert normalize_asking_price_man(100000000) == 10000
    assert normalize_asking_price_man(30000000) == 3000

    # 2. 過去データの万円単位の価格（例: 4590）が0にならず4590となること（Issue #235）
    assert normalize_asking_price_man(4590) == 4590
    assert normalize_asking_price_man(3000) == 3000
    assert normalize_asking_price_man(99999) == 99999

    # 3. 0やNoneなどのエッジケース
    assert normalize_asking_price_man(0) == 0
    assert normalize_asking_price_man(None) == 0
    assert normalize_asking_price_man(-100) == 0


def test_evaluate_candidate_requires_positive_predicted_price_and_discount():
    """理論予測価格が未算出(0/None)または実売価格以下の物件が推奨されないことを検証 (Issue #1239)"""
    from scripts.ops.send_recommendations import _evaluate_candidate
    from unittest.mock import MagicMock

    prop = MagicMock()
    prop.price = 20000000  # 2000万円

    eval_rec = MagicMock()
    eval_rec.property_type = "investmentapartment"
    eval_rec.total_investment_score = 95.0  # 高スコア

    # 1. 理論価格が未算出(0)の場合: 高スコアでも絶対に推奨しない
    eval_rec.first_stage_predicted_price = 0
    eval_rec.second_stage_predicted_price = None
    is_rec, reason, prio = _evaluate_candidate(eval_rec, prop)
    assert is_rec is False
    assert prio == 0.0

    # 2. 理論価格が実売価格以下(1800万円 <= 2000万円)の場合: 推奨しない
    eval_rec.first_stage_predicted_price = 1800
    is_rec, reason, prio = _evaluate_candidate(eval_rec, prop)
    assert is_rec is False

    # 3. 割安率が基準未満(2100万円、5%割安)の場合: 推奨しない
    eval_rec.first_stage_predicted_price = 2100
    is_rec, reason, prio = _evaluate_candidate(eval_rec, prop)
    assert is_rec is False

    # 4. 割安率が適正範囲(2600万円、23.1%割安)の場合: 割安理由で推奨
    eval_rec.first_stage_predicted_price = 2600
    is_rec, reason, prio = _evaluate_candidate(eval_rec, prop)
    assert is_rec is True
    assert "割安" in reason
    assert prio > 70.0

    # 5. 二次スクリーニングが存在するため一次スクリーニングでの割安度上限閾値は不要 (Issue #1348)
    # 高い割安度（3倍超: 8000万円対2000万円 = 75.0%割安）でも一次スクリーニングを通過
    eval_rec.first_stage_predicted_price = 8000
    is_rec, reason, prio = _evaluate_candidate(eval_rec, prop)
    assert is_rec is True
    assert "割安" in reason



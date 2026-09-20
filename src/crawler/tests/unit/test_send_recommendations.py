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


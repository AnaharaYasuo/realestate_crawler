# -*- coding: utf-8 -*-
import pytest
import datetime
from django.utils import timezone
from unittest.mock import patch, MagicMock
from package.models.evaluation import PropertyEvaluation
from scripts.ops.send_recommendations import send_recommendations, clean_val, get_prop_dates

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

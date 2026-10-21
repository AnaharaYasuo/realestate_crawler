import pytest
from unittest.mock import MagicMock, patch
from django.utils import timezone
import datetime


@pytest.mark.django_db
def test_fetch_recommendation_candidates_limits_and_orders():
    from package.models.evaluation import PropertyEvaluation
    from scripts.ops.send_recommendations import _fetch_recommendation_candidates

    # Create dummy records
    now = timezone.now()
    eval1 = PropertyEvaluation.objects.create(
        company="mitsui",
        property_type="mansion",
        property_id=101,
        property_url="https://example.com/p1",
        is_published=True,
        is_slack_notified=False,
        needs_recrawl=False,
        analyzed_at=now,
    )
    eval2 = PropertyEvaluation.objects.create(
        company="mitsui",
        property_type="mansion",
        property_id=102,
        property_url="https://example.com/p2",
        is_published=True,
        is_slack_notified=True, # already notified
        needs_recrawl=False,
        analyzed_at=now,
    )

    candidates = list(_fetch_recommendation_candidates(limit=10))
    urls = [c.property_url for c in candidates]
    assert "https://example.com/p1" in urls
    assert "https://example.com/p2" not in urls


@pytest.mark.django_db
def test_batch_resolve_properties():
    from package.models.evaluation import PropertyEvaluation
    from scripts.ops.send_recommendations import batch_resolve_properties
    from package.models.mitsui import MitsuiMansion

    m1 = MitsuiMansion.objects.create(
        pageUrl="https://example.com/m1",
        propertyName="Test Mansion 1",
        price=5000,
    )
    e1 = PropertyEvaluation.objects.create(
        company="mitsui",
        property_type="mansion",
        property_id=m1.id,
        property_url="https://example.com/m1",
        is_published=True,
        is_slack_notified=False,
    )

    resolved = batch_resolve_properties([e1])
    assert "https://example.com/m1" in resolved
    assert resolved["https://example.com/m1"].propertyName == "Test Mansion 1"

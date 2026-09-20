# -*- coding: utf-8 -*-
"""バルクML評価における地代負債の永続化テスト。"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from package.models.evaluation import PropertyEvaluation
from scripts.ops import run_bulk_ml_evaluation as bulk_evaluation


def _property(property_id, url, *, chidai=None, chidai_str=""):
    return SimpleNamespace(
        id=property_id,
        pageUrl=url,
        price=50000000,
        chidai=chidai,
        chidaiStr=chidai_str,
    )


def _model_for(items):
    class AthomeKodate:
        pass

    AthomeKodate.objects = MagicMock()
    AthomeKodate.objects.all.return_value = items
    return AthomeKodate


def _patch_bulk_dependencies(monkeypatch, predictions):
    evaluation_manager = bulk_evaluation.PropertyEvaluation.objects
    monkeypatch.setattr(evaluation_manager, "bulk_create", MagicMock())
    monkeypatch.setattr(evaluation_manager, "bulk_update", MagicMock())
    monkeypatch.setattr(
        bulk_evaluation,
        "bulk_predict_first_stage",
        MagicMock(return_value=predictions),
    )
    monkeypatch.setattr(bulk_evaluation, "find_duplicate_property", MagicMock(return_value=None))
    monkeypatch.setattr(bulk_evaluation, "close_old_connections", MagicMock())
    return evaluation_manager


def test_bulk_evaluation_persists_land_rent_for_new_records(monkeypatch):
    """新規評価で数値・文字列・欠損の各地代を正しく永続化すること"""
    items = [
        _property(1, "https://example.com/1", chidai=25000),
        _property(2, "https://example.com/2", chidai_str="年額240,000円"),
        _property(3, "https://example.com/3"),
    ]
    model = _model_for(items)
    manager = _patch_bulk_dependencies(monkeypatch, [1000, 1000, 1000])

    evaluated, skipped = bulk_evaluation._evaluate_single_model(
        model,
        existing_eval_map={},
        force=False,
        limit_per_model=None,
    )

    assert (evaluated, skipped) == (3, 0)
    records = manager.bulk_create.call_args.args[0]
    assert [(r.monthly_land_rent, r.land_rent_liability) for r in records] == [
        (25000, Decimal("600")),
        (20000, Decimal("480")),
        (None, None),
    ]
    manager.bulk_create.assert_called_once()
    manager.bulk_update.assert_not_called()


def test_bulk_evaluation_updates_land_rent_fields_on_existing_record(monkeypatch):
    """再評価時に既存レコードの地代値とbulk_update対象フィールドを更新すること"""
    item = _property(7, "https://example.com/existing", chidai_str="月額12,500円")
    model = _model_for([item])
    existing = PropertyEvaluation(
        id=99,
        property_url=item.pageUrl,
        company="athome",
        property_type="kodate",
        property_id=item.id,
        first_stage_predicted_price=900,
    )
    manager = _patch_bulk_dependencies(monkeypatch, [1000])

    evaluated, skipped = bulk_evaluation._evaluate_single_model(
        model,
        existing_eval_map={item.pageUrl: existing},
        force=True,
        limit_per_model=None,
    )

    assert (evaluated, skipped) == (1, 0)
    updated_records = manager.bulk_update.call_args.args[0]
    update_fields = manager.bulk_update.call_args.kwargs["fields"]
    assert updated_records == [existing]
    assert existing.monthly_land_rent == 12500
    assert existing.land_rent_liability == Decimal("300")
    assert "monthly_land_rent" in update_fields
    assert "land_rent_liability" in update_fields
    manager.bulk_create.assert_not_called()

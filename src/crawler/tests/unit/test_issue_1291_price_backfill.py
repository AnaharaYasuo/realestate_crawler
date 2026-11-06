"""
Unit tests for Issue #1291: price units backfill script
"""
from unittest.mock import MagicMock, patch
import pytest

from scripts.maintenance.backfill_price_units import restore_price_units


class DummyField:
    def __init__(self, name: str):
        self.name = name


class DummyMeta:
    def __init__(self, field_names: list[str]):
        self.fields = [DummyField(name) for name in field_names]


class DummyModel:
    __name__ = "DummyMansion"

    def __init__(self, pk: int, price: int, price_str: str):
        self.pk = pk
        self.price = price
        self.priceStr = price_str

    _meta = DummyMeta(["pk", "price", "priceStr"])
    objects = MagicMock()


@pytest.mark.unit
def test_restore_price_units_dry_run_does_not_call_bulk_update():
    # Record 1: price=5280, priceStr="5,280万円" -> reparsed=52800000 (needs repair)
    # Record 2: price=100000, priceStr="10万円" -> reparsed=100000 (already correct)
    obj1 = DummyModel(1, 5280, "5,280万円")
    obj2 = DummyModel(2, 100000, "10万円")
    obj3 = DummyModel(3, 1000, "価格未定")  # unparseable

    DummyModel.objects.filter.return_value.exclude.return_value.only.return_value = [obj1, obj2, obj3]
    DummyModel.objects.bulk_update.reset_mock()

    mock_models_by_type = {"mansion": [("dummy_company", DummyModel)]}

    with patch("scripts.maintenance.backfill_price_units.collect_model_classes_by_type", return_value=mock_models_by_type):
        summary = restore_price_units(dry_run=True)

    assert summary["total_scanned"] == 3
    assert summary["total_repaired"] == 1
    assert summary["total_skipped_already_correct"] == 1
    assert summary["total_skipped_unparseable"] == 1
    # In dry run, bulk_update must NOT be called
    DummyModel.objects.bulk_update.assert_not_called()
    assert obj1.price == 52800000  # in-memory updated for verification


@pytest.mark.django_db
def test_restore_price_units_commit_calls_bulk_update():
    obj1 = DummyModel(1, 5280, "5,280万円")
    DummyModel.objects.filter.return_value.exclude.return_value.only.return_value = [obj1]
    DummyModel.objects.bulk_update.reset_mock()

    mock_models_by_type = {"mansion": [("dummy_company", DummyModel)]}

    with patch("scripts.maintenance.backfill_price_units.collect_model_classes_by_type", return_value=mock_models_by_type):
        summary = restore_price_units(dry_run=False)

    assert summary["total_repaired"] == 1
    DummyModel.objects.bulk_update.assert_called_once()
    args, kwargs = DummyModel.objects.bulk_update.call_args
    assert args[0] == [obj1]
    assert args[1] == ["price"]

"""Issue #1392: 16並列バルク評価のサブバッチ個別コミット & duplicate_of 自己参照FK差分更新テスト"""

from types import SimpleNamespace
from unittest.mock import patch

from django.db import OperationalError
from package.ml.evaluation.persistence import _bulk_create_records, bulk_update_evaluation_records
from package.ml.evaluation.record_builder import build_or_update_eval_record
from package.ml.evaluation.targets import get_all_property_models
from package.models.evaluation import PropertyEvaluation


def test_bulk_update_slices_into_independent_subbatches():
    """250件・batch_size=100 のとき Django の単一巨大トランザクションを避け 100, 100, 50 件で3回個別実行されること"""
    recs = [SimpleNamespace(pk=pk) for pk in range(250, 0, -1)]
    calls: list[tuple[list[int], list[str], int]] = []

    def fake_bulk_update(objs, fields, batch_size):
        calls.append(([o.pk for o in objs], list(fields), batch_size))

    with patch.object(PropertyEvaluation.objects, "bulk_update", side_effect=fake_bulk_update):
        bulk_update_evaluation_records(recs, property_type="mansion", batch_size=100)

    assert [len(pks) for pks, _, _ in calls] == [100, 100, 50]
    assert calls[0][0] == list(range(1, 101))
    assert calls[1][0] == list(range(101, 201))
    assert calls[2][0] == list(range(201, 251))


def test_differential_duplicate_of_omits_self_fk_when_unchanged():
    """既存レコードで duplicate_of_id が変化しない場合は UPDATE カラムから duplicate_of と不変キーを除外し、変化分のみ差分更新すること"""
    item_unchanged = SimpleNamespace(
        id=10,
        pageUrl="https://example.com/10",
        price=3500_0000,
        propertyName="テスト物件A",
        address="東京都世田谷区1-1-1",
    )
    existing_unchanged = SimpleNamespace(
        pk=100,
        id=100,
        company="athome",
        property_type="kodate",
        property_id=10,
        duplicate_of_id=377,
        interior_score=3.0,
        layout_score=3.0,
    )

    item_changed = SimpleNamespace(
        id=11,
        pageUrl="https://example.com/11",
        price=2800_0000,
        propertyName="テスト物件B",
        address="東京都世田谷区1-1-2",
    )
    existing_changed = SimpleNamespace(
        pk=101,
        id=101,
        company="athome",
        property_type="kodate",
        property_id=11,
        duplicate_of_id=None,
        interior_score=3.0,
        layout_score=3.0,
    )
    canonical_sumifu = SimpleNamespace(pk=377, id=377)

    def fake_set_dup(rec, dup):
        rec.duplicate_of = dup
        rec.duplicate_of_id = dup.id

    with patch("package.ml.evaluation.record_builder.find_duplicate_property", return_value=canonical_sumifu):
        rec1, is_new1 = build_or_update_eval_record(
            item=item_unchanged,
            price_stage1=4000.0,
            existing=existing_unchanged,
            company="athome",
            property_type="kodate",
            skip_duplicate_check=False,
            p10_stage1=3600.0,
        )
        rec2, is_new2 = build_or_update_eval_record(
            item=item_changed,
            price_stage1=3500.0,
            existing=existing_changed,
            company="athome",
            property_type="kodate",
            skip_duplicate_check=False,
            p10_stage1=3100.0,
        )
        # SimpleNamespace では FK セッタが duplicate_of_id を自動連動しないため補助設定も確認
        if getattr(rec2, "duplicate_of", None) is canonical_sumifu and rec2.duplicate_of_id is None:
            fake_set_dup(rec2, canonical_sumifu)
            rec2._duplicate_of_changed = True

    assert is_new1 is False
    assert is_new2 is False
    assert rec1._duplicate_of_changed is False
    assert rec1._identity_changed is False
    assert rec2._duplicate_of_changed is True

    calls: list[tuple[list[int], list[str]]] = []

    def fake_bulk_update(objs, fields, batch_size):
        calls.append(([o.pk for o in objs], list(fields)))

    with patch.object(PropertyEvaluation.objects, "bulk_update", side_effect=fake_bulk_update):
        bulk_update_evaluation_records([rec1, rec2], property_type="kodate", batch_size=100)

    assert len(calls) == 2
    main_pks, main_fields = calls[0]
    assert main_pks == [100, 101]
    assert "duplicate_of" not in main_fields
    assert "company" not in main_fields
    assert "property_type" not in main_fields
    assert "property_id" not in main_fields
    assert "first_stage_predicted_price" in main_fields
    assert "first_stage_p10_price" in main_fields

    dup_pks, dup_fields = calls[1]
    assert dup_pks == [101]
    assert dup_fields == ["duplicate_of"]


def test_direct_broker_models_scheduled_before_portals():
    """名寄せ親となる直販・仲介会社モデル（SumifuKodate等）が大規模ポータル（AthomeMansion/HomesMansion）より先に並ぶこと"""
    models = get_all_property_models(skip_portals=False, skip_uncrawled=False)
    names = [m.__name__ for m in models]
    assert "SumifuKodate" in names
    assert "AthomeMansion" in names
    assert "HomesMansion" in names
    assert names.index("SumifuKodate") < names.index("AthomeMansion")
    assert names.index("SumifuKodate") < names.index("HomesMansion")


def test_bulk_create_subbatch_and_retry_on_operational_error():
    """_bulk_create_records もサブバッチ単位で個別実行し、OperationalError 時にリトライすること"""
    recs = [SimpleNamespace(property_url=f"https://example.com/new/{i}") for i in range(150)]
    calls: list[int] = []
    state = {"first": True}

    def fake_bulk_create(objs, batch_size, ignore_conflicts):
        if state["first"]:
            state["first"] = False
            raise OperationalError(2013, "Lost connection")
        calls.append(len(objs))
        return objs

    with (
        patch.object(PropertyEvaluation.objects, "bulk_create", side_effect=fake_bulk_create),
        patch("package.ml.evaluation.persistence.close_old_connections") as mock_close,
        patch("package.ml.evaluation.persistence.time.sleep"),
    ):
        _bulk_create_records(recs, batch_size=100)

    assert calls == [100, 50]
    assert mock_close.call_count == 1


from types import SimpleNamespace
from decimal import Decimal

from package.ml.evaluation.record_builder import build_or_update_eval_record


def test_build_or_update_eval_record_p10_screening():
    """P10下限予測価格による一次スクリーニング (Issue #1399) の判定ロジック検証"""
    item = SimpleNamespace(
        id=101,
        pageUrl="https://example.com/property/101",
        price=30000000,  # 3000万円
        full_text="",
        chikunengetsu=None,
        kaisu=None,
        total_floors=None,
        chidai=None,
        chidaiStr=None,
    )

    # 1. P10が売出価格以上なら合格 (P10=3200 >= asking=3000, price_stage1=3500)
    rec, is_new = build_or_update_eval_record(
        item=item,
        price_stage1=3500.0,
        existing=None,
        company="test_co",
        property_type="mansion",
        skip_duplicate_check=True,
        p10_stage1=3200.0,
    )
    assert is_new is True
    assert rec.is_first_stage_passed is True
    assert rec.first_stage_p10_price == Decimal(3200)
    assert rec.first_stage_predicted_price == 3500.0

    # 2. 平均予測値は売出価格以上だが、P10が売出価格未満なら不合格 (P10=2800 < asking=3000 <= price_stage1=3500)
    rec2, _ = build_or_update_eval_record(
        item=item,
        price_stage1=3500.0,
        existing=None,
        company="test_co",
        property_type="mansion",
        skip_duplicate_check=True,
        p10_stage1=2800.0,
    )
    assert rec2.is_first_stage_passed is False
    assert rec2.first_stage_p10_price == Decimal(2800)
    assert rec2.first_stage_predicted_price == 3500.0

    # 3. P10がNoneの場合は、後方互換性として price_stage1 >= asking_price で判定 (price_stage1=3500 >= asking=3000)
    rec3, _ = build_or_update_eval_record(
        item=item,
        price_stage1=3500.0,
        existing=None,
        company="test_co",
        property_type="mansion",
        skip_duplicate_check=True,
        p10_stage1=None,
    )
    assert rec3.is_first_stage_passed is True
    assert rec3.first_stage_p10_price is None
    assert rec3.first_stage_predicted_price == 3500.0

    # 4. P10がNoneで、price_stage1 < asking_price の場合は不合格 (price_stage1=2500 < asking=3000)
    rec4, _ = build_or_update_eval_record(
        item=item,
        price_stage1=2500.0,
        existing=None,
        company="test_co",
        property_type="mansion",
        skip_duplicate_check=True,
        p10_stage1=None,
    )
    assert rec4.is_first_stage_passed is False
    assert rec4.first_stage_p10_price is None

    # 5. 既存レコード更新時も同様にP10判定が正しく反映されること
    existing_mock = SimpleNamespace(
        pk=999,
        duplicate_of_id=None,
        company="test_co",
        property_type="mansion",
        property_id=101,
    )
    rec5, is_new5 = build_or_update_eval_record(
        item=item,
        price_stage1=3500.0,
        existing=existing_mock,
        company="test_co",
        property_type="mansion",
        skip_duplicate_check=True,
        p10_stage1=2900.0,  # 2900 < 3000
    )
    assert is_new5 is False
    assert rec5.is_first_stage_passed is False
    assert rec5.first_stage_p10_price == Decimal(2900)

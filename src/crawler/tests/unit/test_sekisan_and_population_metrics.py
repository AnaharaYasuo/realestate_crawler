import pytest
from unittest.mock import MagicMock, patch
from package.models.evaluation import PropertyEvaluation, LandPricePotential
from package.ml.evaluation.record_builder import build_or_update_eval_record
from package.ml.report_generator import generate_professional_and_danchou_report


class DummyProperty:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.django_db
def test_build_or_update_eval_record_calculates_sekisan_for_tochi():
    """土地物件でも estimated_sekisan_price が自動算出されて設定されることを検証 (Issue #1242)"""
    LandPricePotential.objects.create(
        prefecture="東京都",
        city="練馬区",
        average_land_price=443806,
        land_use="residential",
    )

    prop = DummyProperty(
        id=999991,
        company="nomu",
        pageUrl="https://www.nomu.com/land/id/test1/",
        address="東京都練馬区三原台3丁目",
        price=178000000,
        landArea=352.0,
        buildingArea=None,
        buildYear=None,
        construction=None,
    )

    rec, is_new = build_or_update_eval_record(
        item=prop,
        price_stage1=27000.0,
        existing=None,
        company="nomu",
        property_type="tochi",
        candidate_pool=[],
        skip_duplicate_check=True,
    )
    assert is_new is True
    assert rec.estimated_sekisan_price is not None
    assert rec.estimated_sekisan_price > 0
    # 練馬区三原台3丁目の積算公示地価約44万/㎡ * 352㎡ ≒ 15,622万円
    assert 10000 <= rec.estimated_sekisan_price <= 20000


@pytest.mark.django_db
def test_generate_professional_and_danchou_report_fallback_calculates_sekisan():
    """eval_rec に積算価格が未設定の場合でも、自動計算されてプロンプト・保存に反映されることを検証"""
    LandPricePotential.objects.create(
        prefecture="東京都",
        city="練馬区",
        average_land_price=443806,
        land_use="residential",
    )

    prop = DummyProperty(
        id=999992,
        company="nomu",
        pageUrl="https://www.nomu.com/land/id/test2/",
        address="東京都練馬区三原台3丁目",
        price=178000000,
        landArea=352.0,
        buildingArea=None,
        buildYear=None,
        construction=None,
        site_coverage_ratio=60.0,
        floor_area_ratio=300.0,
    )
    rec = PropertyEvaluation(
        property_id=prop.id,
        property_type="tochi",
        property_url=prop.pageUrl,
        first_stage_predicted_price=27000.0,
        estimated_sekisan_price=0.0,
    )
    rec.save = MagicMock()

    with patch("package.ml.report_generator.fetch_property_page_text", return_value=""), \
         patch("package.ml.report_generator.search_danchou_knowledge", return_value=[]), \
         patch("package.ml.report_generator.build_appraisal_context", return_value=None), \
         patch("package.ml.report_generator._call_gemini_api", return_value={"investment_rating": "A"}):
        
        with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy_key"}):
            report = generate_professional_and_danchou_report(
                rec, prop, "土地", 17800, 27000, prop.address, "石神井公園 徒歩22分"
            )
            assert report is not None
            assert rec.estimated_sekisan_price > 0
            assert 10000 <= rec.estimated_sekisan_price <= 20000

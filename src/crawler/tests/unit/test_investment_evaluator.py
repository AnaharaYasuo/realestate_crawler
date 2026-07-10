# -*- coding: utf-8 -*-
import pytest
from package.ml.investment_evaluator import (
    detect_structure_type,
    parse_chikunen,
    calculate_loan_term,
    calculate_sekisan_price,
    evaluate_investment_property
)
from package.models.evaluation import PropertyEvaluation, LandPricePotential
from django.utils import timezone
from decimal import Decimal

class DummyProperty:
    def __init__(self):
        self.id = 1
        self.price = 100000000  # 1億円 (10000万円)
        self.address = "東京都新宿区西新宿1-1"
        self.tochiMenseki = Decimal("100.00")
        self.tatemonoMenseki = Decimal("200.00")
        self.kouzou = "RC造"
        self.chikunengetsuStr = "2016年10月"
        self.chikunengetsu = None
        self.annualRent = 8000000  # 800万円
        self.grossYield = Decimal("8.00")
        self.pageUrl = "https://example.com/test-property-1"

def test_detect_structure_type():
    assert detect_structure_type("RC造") == "RC"
    assert detect_structure_type("木造2階建") == "W"
    assert detect_structure_type("軽量鉄骨造") == "S"
    assert detect_structure_type(None) == "W"

def test_parse_chikunen():
    current_year = timezone.now().year
    assert parse_chikunen("2016年10月") == current_year - 2016
    assert parse_chikunen("平成10年") == current_year - 1998
    assert parse_chikunen(None) == 20

def test_calculate_loan_term():
    assert calculate_loan_term("RC", 10) == 35  # 47 - 10 = 37 -> max_limit 35
    # 残存が短くても下限20年
    assert calculate_loan_term("W", 20) == 20   # 22 - 20 = 2 -> 下限20
    # 上限35年
    assert calculate_loan_term("RC", 5) == 35   # 47 - 5 = 42 -> 上限35

@pytest.mark.django_db
def test_evaluate_investment_property():
    prop = DummyProperty()
    
    # テスト用マスタデータをあらかじめ作成
    LandPricePotential.objects.create(
        prefecture="東京都",
        city="新宿区",
        average_land_price=500000,  # 50万円/㎡
        land_use="residential"
    )
    
    eval_rec = PropertyEvaluation(
        company="mitsui",
        property_type="investmentapartment",
        property_id=1,
        property_url=prop.pageUrl,
        first_stage_predicted_price=12000,  # 1.2億円 (割安)
        second_stage_predicted_price=11000
    )
    
    eval_rec = evaluate_investment_property(prop, eval_rec)
    
    # 期待値の計算検証
    # 土地: 100 * 50万 = 5000万 = 5000万円
    # 建物: 200 * 20万 * (残存 35 / 耐用 47) = 4000万 * 35/47 = 2978万円
    # 積算価格 = 5000 + 2978 = 7978万円
    # 積算価格比率 = 7978 / 10000 = 79.78%
    assert eval_rec.estimated_sekisan_price >= 7000
    assert eval_rec.net_operating_income == 640  # 800 * 80% = 640万円
    
    # 返済・キャッシュフローの検証
    assert eval_rec.debt_service > 300
    assert eval_rec.cash_flow > 0
    assert eval_rec.dscr > Decimal("1.0")
    assert eval_rec.coc_return > Decimal("0.0")
    assert eval_rec.total_investment_score > 0
    assert eval_rec.investment_score == eval_rec.total_investment_score

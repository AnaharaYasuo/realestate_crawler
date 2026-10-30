# -*- coding: utf-8 -*-
from unittest.mock import patch

from scripts.maintenance.repair_anomalous_predictions import repair_anomalous_records

class MockProperty:
    def __init__(self, pageUrl, price, propertyName="テスト物件"):
        self.pageUrl = pageUrl
        self.price = price
        self.propertyName = propertyName

class MockEvaluation:
    def __init__(self, property_type, first_stage_predicted_price, id=1, property_url="https://example.com/test"):
        self.id = id
        self.property_type = property_type
        self.first_stage_predicted_price = first_stage_predicted_price
        self.is_first_stage_passed = False
        self.total_investment_score = 0.0
        self.investment_score = 0.0
        self.cashflow_score = 0.0
        self.finance_score = 0.0
        self.estimated_sekisan_price = 0
        self.net_operating_income = 0
        self.debt_service = 0
        self.cash_flow = 0
        self.dscr = 0.0
        self.coc_return = 0.0
        self.sekisan_ratio = 0.0
        self.property_url = property_url

def test_repair_anomalous_records():
    """repair_anomalous_records が再推論結果で正しくレコードを更新することを検証"""
    prop = MockProperty("https://example.com/test1", 35600000)
    ev = MockEvaluation("investmentapartment", first_stage_predicted_price=174133.0, id=101)
    
    with patch("scripts.maintenance.repair_anomalous_predictions.bulk_predict_first_stage", return_value=[3603]), \
         patch("scripts.maintenance.repair_anomalous_predictions.evaluate_investment_property") as mock_eval_inv, \
         patch("scripts.maintenance.repair_anomalous_predictions.PropertyEvaluation.objects.bulk_update") as mock_bulk_update:
         
        pairs = [(ev, prop)]
        repaired = repair_anomalous_records(pairs)
        
        assert repaired == 1
        assert ev.first_stage_predicted_price == 3603
        assert ev.is_first_stage_passed is True
        mock_eval_inv.assert_called_once_with(prop, ev)
        mock_bulk_update.assert_called_once()

# -*- coding: utf-8 -*-
"""
借地物件における地代負債価値判定（投資NOI控除・実需特徴量/評価減価）の単体テスト (TDD)
"""
from decimal import Decimal

from package.ml.investment_evaluator import evaluate_investment_property
from package.models.evaluation import PropertyEvaluation
from package.ml.features import build_features


class MockProperty:
    def __init__(self, **kwargs):
        self.id = 1
        self.pageUrl = "https://example.com/item/1"
        self.propertyName = "テスト物件"
        self.price = 50000000  # 5,000万円
        self.priceStr = "5,000万円"
        self.address = "東京都中野区上高田５丁目"
        self.traffic = "西武新宿線 新井薬師前駅 徒歩7分"
        self.chikunengetsuStr = "2010年1月"
        self.kouzou = "木造"
        self.tochiMenseki = Decimal("80.0")
        self.tatemonoMenseki = Decimal("90.0")
        self.tochikenri = "借地権"
        self.biko = ""
        self.setsudou = "南側公道"
        self.notes = ""
        self.chidai = None
        self.chidaiStr = ""
        self.annualRent = 4000000  # 年間賃料400万円 (投資用)
        self.grossYield = Decimal("8.0")
        
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_investment_evaluator_deducts_actual_land_rent():
    """投資物件評価において、実額地代（月2万円=年24万円）がNOIから正確に控除されること"""
    # 1. 地代あり物件 (月20,000円 -> 年間24万円)
    prop_with_chidai = MockProperty(chidai=20000, tochikenri="借地権")
    eval_rec1 = PropertyEvaluation(property_url=prop_with_chidai.pageUrl, company="athome", property_type="investment_kodate")
    eval_res1 = evaluate_investment_property(prop_with_chidai, eval_rec1)
    
    # 2. 地代なし（所有権）物件
    prop_freehold = MockProperty(chidai=None, tochikenri="所有権")
    eval_rec2 = PropertyEvaluation(property_url=prop_freehold.pageUrl, company="athome", property_type="investment_kodate")
    eval_res2 = evaluate_investment_property(prop_freehold, eval_rec2)

    # 満室年収400万、Opex15% (340万) に対し、地代24万円が控除されていること
    # NOI(所有権) - NOI(借地) == 24万円
    noi_diff = float(eval_res2.net_operating_income) - float(eval_res1.net_operating_income)
    assert abs(noi_diff - 24.0) < 1.0, f"Expected NOI diff around 24(man-yen), got {noi_diff}"
    
    # 手残りキャッシュフロー(CF)も地代分減少していること
    cf_diff = float(eval_res2.cash_flow) - float(eval_res1.cash_flow)
    assert abs(cf_diff - 24.0) < 1.0


def test_features_builds_land_rent_debt_features():
    """実需（戸建・マンション・土地）特徴量生成において地代負債特徴量が正しく算出されること"""
    # 月額20,000円 (2.0万円) -> 年間24.0万円 -> 負債価値 (24.0 / 0.05) = 480.0万円
    prop = MockProperty(price=40000000, chidai=20000, tochikenri="普通賃借権")
    feats = build_features(prop, "kodate")
    
    assert "monthly_land_rent" in feats
    assert "annual_land_rent" in feats
    assert "land_rent_liability" in feats
    assert "land_rent_ratio" in feats
    
    assert feats["monthly_land_rent"] == 2.0
    assert feats["annual_land_rent"] == 24.0
    assert abs(feats["land_rent_liability"] - 480.0) < 0.1
    assert abs(feats["land_rent_ratio"] - (24.0 / 4000.0)) < 0.001
    assert feats["is_leasehold"] == 1.0


def test_features_handles_missing_land_rent():
    """地代記載なし（所有権等）の場合は負債特徴量が0.0で安全にフォールバックすること"""
    prop = MockProperty(price=40000000, chidai=None, tochikenri="所有権")
    feats = build_features(prop, "kodate")
    
    assert feats["monthly_land_rent"] == 0.0
    assert feats["annual_land_rent"] == 0.0
    assert feats["land_rent_liability"] == 0.0
    assert feats["land_rent_ratio"] == 0.0
    assert feats["is_leasehold"] == 0.0

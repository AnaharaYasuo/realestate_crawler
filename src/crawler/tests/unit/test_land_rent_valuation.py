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


def test_features_extracts_from_chidaistr_when_chidai_is_none():
    """chidaiがNoneでもchidaiStrが存在する場合、featuresで自動パースされること"""
    prop = MockProperty(price=3000, chidai=None, chidaiStr="月額 15,000円", tochikenri="賃借権")
    feats = build_features(prop, "kodate")

    assert feats["monthly_land_rent"] == 1.5
    assert feats["annual_land_rent"] == 18.0
    assert abs(feats["land_rent_liability"] - 360.0) < 0.1
    assert abs(feats["land_rent_ratio"] - (18.0 / 3000.0)) < 0.001


def test_features_extracts_from_text_fallback_for_leasehold():
    """借地権物件でchidai未設定でも、備考テキスト等の正規表現から地代が抽出されること"""
    prop = MockProperty(price=50000000, chidai=None, chidaiStr="", tochikenri="借地権", biko="地代（月額）3万円、更新料別途")
    feats = build_features(prop, "kodate")

    assert feats["monthly_land_rent"] == 3.0
    assert feats["annual_land_rent"] == 36.0
    assert abs(feats["land_rent_liability"] - 720.0) < 0.1


def test_features_extracts_annual_rent_from_text_fallback():
    """借地権物件で『地代 年額240,000円』等の年額表記が正しく月額に正規化されること"""
    prop = MockProperty(price=50000000, chidai=None, chidaiStr="", tochikenri="借地権", biko="地代 年額240,000円、別途保証金あり")
    feats = build_features(prop, "kodate")

    assert feats["monthly_land_rent"] == 2.0  # 240,000 / 12 = 20,000円 -> 2.0万円
    assert feats["annual_land_rent"] == 24.0
    assert abs(feats["land_rent_liability"] - 480.0) < 0.1

    prop2 = MockProperty(price=50000000, chidai=None, chidaiStr="", tochikenri="借地権", biko="借地料: 24万円/年")
    feats2 = build_features(prop2, "kodate")
    assert feats2["monthly_land_rent"] == 2.0
    assert feats2["annual_land_rent"] == 24.0


def test_investment_evaluator_leasehold_keyword_filtering():
    """『定期点検』『定期清掃』等の所有権物件が誤って借地権判定されないこと"""
    # 定期点検の所有権物件
    prop_freehold = MockProperty(tochikenri="所有権", biko="定期点検実施済み、定期清掃あり", chidai=None)
    eval_record = PropertyEvaluation(monthly_land_rent=None, land_rent_liability=None)
    res_freehold = evaluate_investment_property(prop_freehold, eval_record)
    assert res_freehold.monthly_land_rent is None
    assert res_freehold.land_rent_liability is None

    # 定期借地の物件
    prop_leasehold = MockProperty(tochikenri="定期借地権", biko="借地期間50年", chidai=None)
    eval_record2 = PropertyEvaluation(monthly_land_rent=None, land_rent_liability=None)
    res_leasehold = evaluate_investment_property(prop_leasehold, eval_record2)
    assert res_leasehold.monthly_land_rent is not None
    assert res_leasehold.monthly_land_rent > 0


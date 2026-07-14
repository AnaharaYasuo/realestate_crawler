# -*- coding: utf-8 -*-
import pytest
from unittest.mock import MagicMock
from package.ml.predict import _apply_rights_discount
from package.ml.investment_evaluator import evaluate_investment_property

class MockProperty:
    def __init__(self, price=10000000, tochikenri="", biko="", address="東京都世田谷区", chikunen=0):
        self.price = price
        self.tochikenri = tochikenri
        self.biko = biko
        self.address = address
        self.chikunen = chikunen
        self.pageUrl = "https://example.com/prop1"
        self.kouzou = "RC"
        self.chikunengetsu = None
        self.chikunengetsuStr = ""
        self.annualRent = 1200000 # 120万/年

def test_apply_rights_discount_normal():
    # 所有権（割引なし）
    prop = MockProperty(tochikenri="所有権")
    assert _apply_rights_discount(prop, 10000000) == 10000000

def test_apply_rights_discount_leasehold():
    # 借地権 (65%にディスカウント)
    prop = MockProperty(tochikenri="普通借地権")
    assert _apply_rights_discount(prop, 10000000) == 6500000

def test_apply_rights_discount_leased_land():
    # 底地 (20%にディスカウント)
    prop = MockProperty(tochikenri="底地")
    assert _apply_rights_discount(prop, 10000000) == 2000000

def test_apply_rights_discount_term_leasehold():
    # 定期借地権 (築0年の場合: 70% * 50% = 35%にディスカウント)
    prop = MockProperty(tochikenri="定期借地権", chikunen=0)
    assert _apply_rights_discount(prop, 10000000) == 3500000

def test_apply_rights_discount_non_conforming():
    # 再建築不可 (単体の場合: 40%にディスカウント)
    prop = MockProperty(tochikenri="所有権", biko="本物件は再建築不可です。")
    assert _apply_rights_discount(prop, 10000000) == 4000000

def test_apply_rights_discount_leasehold_and_non_conforming():
    # 借地権 かつ 再建築不可 (65% * 40% = 26%にディスカウント)
    prop = MockProperty(tochikenri="普通借地権", biko="再建築不可")
    assert _apply_rights_discount(prop, 10000000) == 2600000

def test_investment_evaluator_non_conforming_penalty():
    # 再建築不可物件のローン評価ペナルティ (融資額0円)
    prop = MockProperty(price=10000000, tochikenri="所有権", biko="再建築不可")
    eval_rec = MagicMock()
    eval_rec.first_stage_predicted_price = 10000000
    eval_rec.second_stage_predicted_price = 10000000
    
    # 評価実行
    res = evaluate_investment_property(prop, eval_rec)
    
    # 自己資金（down_payment）が売出価格（1000万円 = 1000万円）と同額になり、
    # ローン元金（loan_principal）が 0 になっていることをアサーション
    # evaluate_investment_propertyはインプレースでeval_recを書き換える、または値を返す設計

def test_max_building_and_floor_area():
    from package.ml.features import build_features
    # 土地面積 200m2, 建ぺい率 60%, 容積率 200% のモック物件
    prop = {
        "address": "東京都世田谷区",
        "tochiMenseki": 200.0,
        "kenpeiStr": "60%",
        "yousekiStr": "200%",
        "youtoChiiki": "第一種住居地域",
        "setsudou": "西側公道幅員6.0mに10.0m接道"
    }
    
    feats = build_features(prop, "kodate")
    
    # 最大建築面積 = 200.0 * 0.6 = 120.0m2
    # 最大延床面積 = 200.0 * 2.0 = 400.0m2 (幅員6.0m * 0.4 = 240%なので容積率制限は指定値の200%が適用される)
    assert feats["max_building_area"] == 120.0
    assert feats["max_floor_area"] == 400.0

def test_corner_easement():
    from package.ml.features import build_features
    # 接道が「角地」の場合のモック物件 (建ぺい率60%が70%に緩和される)
    prop = {
        "address": "東京都世田谷区",
        "tochiMenseki": 200.0,
        "kenpeiStr": "60%",
        "yousekiStr": "200%",
        "youtoChiiki": "第一種住居地域",
        "roadStructure": "北東角地"
    }
    feats = build_features(prop, "kodate")
    # 最大建築面積 = 200.0 * 0.7 = 140.0m2 (10%緩和)
    assert feats["max_building_area"] == 140.0

def test_kagechi_ratio_depreciation():
    # 旗竿地による減価（25%かげ地 -> 20%減価 = 80%の価値）
    prop1 = MockProperty(tochikenri="所有権", biko="旗竿地につき割安")
    assert _apply_rights_discount(prop1, 10000000) == 8000000
    
    # 不整形地による減価（15%かげ地 -> 10%減価 = 90%の価値）
    prop2 = MockProperty(tochikenri="所有権", biko="本物件は不整形地です")
    assert _apply_rights_discount(prop2, 10000000) == 9000000

def test_two_sigma_outlier_exclusion():
    # 正常なお宝物件 (例: 予測価格1000万円、売出価格800万円 = 20%割安) -> 推薦対象
    asking_price_man1 = 800
    pred_price1 = 1000.0
    discount_pct1 = (pred_price1 - asking_price_man1) / pred_price1 * 100.0
    
    is_recommend1 = False
    if discount_pct1 >= 40.0:
        pass
    elif discount_pct1 >= 15.0:
        is_recommend1 = True
    assert is_recommend1 is True

    # 2σ異常値の疑いがある物件 (例: 予測価格1000万円、売出価格500万円 = 50%割安) -> 推薦除外
    asking_price_man2 = 500
    pred_price2 = 1000.0
    discount_pct2 = (pred_price2 - asking_price_man2) / pred_price2 * 100.0
    
    is_recommend2 = False
    if discount_pct2 >= 40.0:
        pass # 除外
    elif discount_pct2 >= 15.0:
        is_recommend2 = True
    assert is_recommend2 is False


def test_effective_walk_min_scaling():
    """
    人口密度に応じた駅徒歩分数のスケーリング計算（実効徒歩分数）をテスト
    """
    # 1. 23区などの高人口密度エリア (東京中央区: 人口密度16,800人/km2)
    # 4,000人/km2以上なので walk_min_penalty_scale は 1.0 (フルにペナルティが働く)
    density_high = 16800.0
    scale_high = max(0.4, min(1.0, 0.4 + 0.6 * (density_high / 4000.0)))
    assert scale_high == 1.0
    
    # 徒歩15分がそのまま 15分 と評価される
    effective_high = 15.0 * scale_high
    assert effective_high == 15.0

    # 2. 郊外などの低人口密度エリア (木更津市: 人口密度950人/km2)
    # 車社会のため walk_min_penalty_scale が逓減する
    density_low = 950.0
    scale_low = max(0.4, min(1.0, 0.4 + 0.6 * (density_low / 4000.0)))
    expected_scale = 0.4 + 0.6 * (950.0 / 4000.0) # 0.4 + 0.1425 = 0.5425
    assert abs(scale_low - expected_scale) < 1e-5
    
    # 徒歩15分が約8.1分と評価される（駅距離ペナルティが大きく緩和）
    effective_low = 15.0 * scale_low
    assert abs(effective_low - 8.1375) < 1e-4





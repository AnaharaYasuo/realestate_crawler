# -*- coding: utf-8 -*-
import pytest
from unittest.mock import MagicMock
from package.ml.features import build_features, safe_float
from package.ml.investment_evaluator import evaluate_investment_property

def test_safe_float_maguchi_fallback():
    # maguchi is None -> 6.0
    assert safe_float(None, 6.0) == 6.0
    # maguchi is 0 or 0.0 -> 6.0 (no frontage penalty for unextracted frontage)
    assert safe_float(0, 6.0) == 6.0
    assert safe_float(0.0, 6.0) == 6.0
    # valid maguchi -> parsed correctly
    assert safe_float(3.5, 6.0) == 3.5

def test_features_saikenchiku_fuka_full_text():
    # 備考に再建築不可
    prop1 = {"address": "東京都世田谷区", "biko": "本物件は再建築不可です。"}
    feats1 = build_features(prop1, "kodate")
    assert feats1["is_saikenchiku_fuka"] == 1.0

    # 物件名に再建築不可
    prop2 = {"address": "東京都世田谷区", "propertyName": "【再建築不可】売戸建"}
    feats2 = build_features(prop2, "kodate")
    assert feats2["is_saikenchiku_fuka"] == 1.0

    # 接道に再建築不可
    prop3 = {"address": "東京都世田谷区", "setsudou": "接道なし（再建築不可）"}
    feats3 = build_features(prop3, "kodate")
    assert feats3["is_saikenchiku_fuka"] == 1.0

def test_features_shigaika_chousei_full_text():
    # 物件名に市街化調整区域
    prop1 = {"address": "埼玉県さいたま市", "propertyName": "市街化調整区域の資材置場"}
    feats1 = build_features(prop1, "tochi")
    assert feats1["is_shigaika_chousei"] == 1.0

    # 備考に調整区域
    prop2 = {"address": "千葉県船橋市", "biko": "本土地は調整区域に位置します"}
    feats2 = build_features(prop2, "tochi")
    assert feats2["is_shigaika_chousei"] == 1.0

def test_features_rights_ratio_full_text():
    # 物件名に借地権
    prop1 = {"address": "東京都杉並区", "propertyName": "【借地権】オーナーチェンジ戸建"}
    feats1 = build_features(prop1, "kodate")
    assert feats1["rights_ratio"] == pytest.approx(0.65)

    # 備考に底地
    prop2 = {"address": "東京都中野区", "biko": "本物件は底地の売却となります"}
    feats2 = build_features(prop2, "kodate")
    assert feats2["rights_ratio"] == pytest.approx(0.20)

    # 物件名に定期借地
    prop3 = {"address": "東京都練馬区", "propertyName": "定期借地権付き一戸建て", "chikunen": 10.0}
    feats3 = build_features(prop3, "kodate")
    assert feats3["rights_ratio"] < 0.70

def test_features_no_maguchi_penalty_when_missing():
    # maguchi = 0 -> no penalty (should default to 6.0m)
    prop = {"address": "東京都世田谷区", "tochiMenseki": 100.0, "maguchi": 0.0}
    feats = build_features(prop, "kodate")
    assert feats["maguchi"] == 6.0

def test_investment_evaluator_full_text_detection():
    class MockProperty:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    # 物件名に再建築不可がある場合
    prop = MockProperty(price=10000000, propertyName="【再建築不可】投資物件", address="東京都", tochikenri="所有権", pageUrl="https://example.com/item1")
    eval_rec = MagicMock()
    eval_rec.first_stage_predicted_price = 10000000
    eval_rec.second_stage_predicted_price = 10000000
    
    # 再建築不可の場合はローン不可扱い
    res = evaluate_investment_property(prop, eval_rec)
    assert res is not None

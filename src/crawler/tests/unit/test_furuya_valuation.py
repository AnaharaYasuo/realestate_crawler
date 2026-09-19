# -*- coding: utf-8 -*-
import pytest
from package.ml.features import build_features_batch


class MockProperty:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_standard_furuya_as_is():
    """現況渡し古家付き土地: 解体費用が控除されること"""
    prop = MockProperty(
        propertyName="世田谷区奥沢 土地（現況古家あり）",
        address="東京都世田谷区奥沢1-1-1",
        tochiMenseki=100.0,
        railwayWalkMinute1=7,
        setsudou="公道 西 5.0m",
        biko="現況古家あり、現況有姿渡し。建物面積約75㎡、木造2階建。",
        youseki=150.0,
        kenpei=60.0
    )
    feats = build_features_batch([prop], "tochi")
    feat = feats[0]

    assert feat["is_furuya"] == 1.0, "is_furuya flag must be 1.0"
    assert feat["has_demolition_condition"] == 0.0, "has_demolition_condition must be 0.0"
    assert feat["furuya_demolition_cost"] > 50.0, f"Demolition cost should be > 50万円, got {feat['furuya_demolition_cost']}"
    # 解体費用（約75㎡ * 1.4 = 105万円）が反映されていること
    assert feat["furuya_demolition_cost"] == pytest.approx(75.0 * 1.4, rel=1e-2)


def test_furuya_demolition_seller_responsibility():
    """解体更地渡し古家付き土地: 買主負担の解体費用がゼロであること"""
    prop = MockProperty(
        propertyName="世田谷区中町 土地（解体更地渡し）",
        address="東京都世田谷区中町2-2-2",
        tochiMenseki=120.0,
        railwayWalkMinute1=10,
        setsudou="公道 南 6.0m",
        biko="古家付売地ですが、売主負担にて解体後、更地渡しとなります。",
        youseki=150.0,
        kenpei=60.0
    )
    feats = build_features_batch([prop], "tochi")
    feat = feats[0]

    assert feat["is_furuya"] == 1.0, "is_furuya flag must be 1.0"
    assert feat["has_demolition_condition"] == 1.0, "has_demolition_condition must be 1.0"
    assert feat["furuya_demolition_cost"] == 0.0, f"Demolition cost should be 0.0 for seller demolition, got {feat['furuya_demolition_cost']}"


def test_furuya_saikenchiku_fuka_protection():
    """再建築不可＋古家付き土地: 解体費用控除を禁止し、建物利用・再生価値・オプション価値が加算されること"""
    prop = MockProperty(
        propertyName="世田谷区太子堂 土地（上物あり・再建築不可）",
        address="東京都世田谷区太子堂3-3-3",
        tochiMenseki=80.0,
        railwayWalkMinute1=6,
        setsudou="私道 2.5m 通路",
        biko="再建築不可。上物あり（木造平屋建、延床50㎡）。リノベーション、DIY賃貸向き。",
        youseki=100.0,
        kenpei=50.0
    )
    feats = build_features_batch([prop], "tochi")
    feat = feats[0]

    assert feat["is_saikenchiku_fuka"] == 1.0, "is_saikenchiku_fuka must be 1.0"
    assert feat["is_furuya"] == 1.0, "is_furuya must be 1.0"
    # 再建築不可では解体厳禁のため解体費用控除は0
    assert feat["furuya_demolition_cost"] == 0.0, "Demolition cost must be 0 for saikenchiku fuka"
    # 戸建賃貸・リノベ利用価値およびオプション価値が算出されていること
    assert feat["furuya_usable_value"] > 0.0, f"furuya_usable_value should be > 0, got {feat['furuya_usable_value']}"
    assert feat["furuya_option_value"] > 0.0, f"furuya_option_value should be > 0, got {feat['furuya_option_value']}"


def test_pure_land_without_furuya():
    """純更地（古家なし）: 古家関連特徴量がすべて0であること"""
    prop = MockProperty(
        propertyName="世田谷区深沢 土地（更地）",
        address="東京都世田谷区深沢4-4-4",
        tochiMenseki=150.0,
        railwayWalkMinute1=12,
        setsudou="公道 東 6.0m",
        biko="閑静な住宅街。更地につき即建築可能。建築条件なし。",
        youseki=100.0,
        kenpei=50.0
    )
    feats = build_features_batch([prop], "tochi")
    feat = feats[0]

    assert feat["is_furuya"] == 0.0, "is_furuya must be 0.0"
    assert feat["has_demolition_condition"] == 0.0, "has_demolition_condition must be 0.0"
    assert feat["furuya_demolition_cost"] == 0.0, "furuya_demolition_cost must be 0.0"
    assert feat["furuya_usable_value"] == 0.0, "furuya_usable_value must be 0.0"
    assert feat["furuya_option_value"] == 0.0, "furuya_option_value must be 0.0"


def test_furuya_prediction_integration():
    """古家付き土地の推論実行テスト: predict_first_stage が正常に数値を返すこと"""
    from package.ml.predict import predict_first_stage
    prop = {
        "propertyName": "世田谷区奥沢 土地（古家あり）",
        "propertyType": "tochi",
        "pageUrl": "http://example.com/test-furuya-pred-1",
        "price": 4500,
        "address1": "東京都",
        "address2": "世田谷区",
        "tochiMenseki": 100.0,
        "railwayWalkMinute1": 7,
        "setsudou": "公道 西 5.0m",
        "biko": "現況古家あり、現況有姿渡し。建物面積約75㎡、木造2階建。",
        "maguchi": 6.0,
        "roadWidth": 5.0,
    }
    pred_price = predict_first_stage(prop)
    assert isinstance(pred_price, int)
    assert pred_price > 0


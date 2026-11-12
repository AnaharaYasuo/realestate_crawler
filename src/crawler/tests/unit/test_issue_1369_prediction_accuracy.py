"""
Issue #1369: 価格推定精度劣化（MdAPE 22.22%）の根本原因修正に関する単体テスト

検証対象:
1. ParserBase._get_specs が後続の担当店舗情報テーブルの「所在地」等で物件概要を上書きしないこと
2. ParserBase._split_address が先頭の郵便番号（〒NNN-NNNN）を除去して都道府県・市区町村を分割すること
3. clean_training_data が店舗ビル住所汚染（〒...ビル...階）および都道府県/市区町村欠損レコードを機械的に除外すること
4. bulk_predict_first_stage / ModelRegistry.preload が location_encoder・ensemble_weights・smearing_factors をバイパスせず適用すること
5. legal_furuya / land_valuation_extras / parsers が法43条無接道（建築基準法に定める道路に接していない）、借地権設定底地（月々徴収する地代）、私道部分内訳面積を正しく検出・控除すること
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from bs4 import BeautifulSoup
import numpy as np
import pandas as pd

from package.ml.features.land_valuation_extras import _detect_special_sale_share
from package.ml.features.legal_furuya import extract_legal_and_furuya_features
from package.ml.inference.model_registry import ModelRegistry, set_default_registry
from package.ml.predict import (
    _load_ensemble_weights,
    _load_smearing_factors,
    bulk_predict_first_stage,
)
from package.ml.training.cleaning import clean_training_data
from package.parser.daiwaParser import DaiwaTochiParser
from package.utils.data_validator import PropertyDataValidator


def test_daiwa_parser_does_not_overwrite_property_address_with_shop_office_address():
    """後続の担当店舗情報テーブルの『所在地』が物件概要の『所在地』を上書きしないこと"""
    html = """
    <html>
      <head><title>東京都八王子市下恩方町 ｜土地購入｜大和ハウスリアルエステート</title></head>
      <body>
        <h1>八王子市下恩方町土地</h1>
        <h2>物件概要</h2>
        <table>
          <tr><th>物件種目</th><td>売地</td></tr>
          <tr><th>価格</th><td>1,180万円</td></tr>
          <tr><th>所在地</th><td>東京都八王子市下恩方町</td></tr>
          <tr><th>土地面積</th><td>218.32m²</td></tr>
        </table>
        <h2>担当店舗情報</h2>
        <h3>東京西営業所</h3>
        <table>
          <tr><th>所在地</th><td>〒 180-0003 武蔵野市吉祥寺南町2-3-15（吉祥寺フコク生命ビル5階）</td></tr>
          <tr><th>連絡先</th><td>TEL 0120-601-303</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = DaiwaTochiParser()
    addr = parser._parseAddress(soup)
    assert addr == "東京都八王子市下恩方町"
    a1, a2, a3 = parser._split_address(addr)
    assert a1 == "東京都"
    assert a2 == "八王子市"
    assert a3 == "下恩方町"


def test_split_address_strips_leading_postal_code():
    """_split_address が先頭の郵便番号『〒180-0003 』を除去して都道府県補完・市区町村分割できること"""
    parser = DaiwaTochiParser()
    a1, a2, a3 = parser._split_address("〒180-0003 武蔵野市吉祥寺南町2-3-15")
    assert a1 == "東京都"
    assert a2 == "武蔵野市"
    assert a3 == "吉祥寺南町2-3-15"


def test_clean_training_data_excludes_office_address_and_missing_municipality():
    """clean_training_data が郵便番号＋ビル階数表記の店舗住所汚染および都道府県・市区町村欠損レコードを除外すること"""
    rows = []
    for i in range(30):
        rows.append({
            "price": 5000.0 + i * 100.0,
            "area": 80.0 + (i % 10),
            "chikunen": 10.0,
            "prefecture": "東京都",
            "city": "世田谷区",
            "address": f"東京都世田谷区成城{i % 5 + 1}丁目",
            "micro_land_price": 600000.0,
            "average_land_price": 550000.0,
            "is_special_sale_share": 0.0,
        })
    # 店舗ビル住所汚染レコード
    rows.append({
        "price": 1180.0,
        "area": 218.0,
        "chikunen": 0.0,
        "prefecture": "東京都",
        "city": "千代田区",
        "address": "〒102-0072千代田区飯田橋2丁目18番2号（大和ハウス九段ビル4階）",
        "micro_land_price": 2100000.0,
        "average_land_price": 2000000.0,
        "is_special_sale_share": 0.0,
    })
    # 都道府県・市区町村が空欄の汚染レコード
    rows.append({
        "price": 4500.0,
        "area": 75.0,
        "chikunen": 5.0,
        "prefecture": "",
        "city": "",
        "address": "不明住所",
        "micro_land_price": 500000.0,
        "average_land_price": 500000.0,
        "is_special_sale_share": 0.0,
    })
    df = pd.DataFrame(rows)
    cleaned = clean_training_data(df, "tochi")
    assert not cleaned["address"].str.contains("大和ハウス九段ビル").any()
    assert not (cleaned["prefecture"] == "").any()
    assert not (cleaned["city"] == "").any()


def test_preload_and_bulk_predict_first_stage_applies_location_encoder_and_weights(tmp_path):
    """bulk_predict_first_stage が location_encoder・ensemble_weights・smearing_factors をバイパスせず適用すること"""
    (tmp_path / "dummy.joblib").write_bytes(b"0")
    reg = ModelRegistry(model_dir=str(tmp_path))
    loc_enc_mock = MagicMock()
    loc_enc_mock.transform.return_value = (
        pd.Series([4.8], dtype=float),
        pd.Series([4.7], dtype=float),
    )
    reg.set_custom_location_encoders({"mansion": {"first": loc_enc_mock}})
    reg.set_custom_weights({"mansion": {"first": {"lgb": 1.0}}})
    reg.set_custom_smearing_factors({"mansion": {"first": 1.05}})

    model_mock = MagicMock()
    model_mock.predict.side_effect = lambda df: np.array([float(df["anchor_log_unit_price"].iloc[0])])
    reg.set_custom_models("mansion", "first_stage", {"lgb": model_mock})
    reg.set_custom_market_master({})

    set_default_registry(reg)
    try:
        assert _load_ensemble_weights()["mansion"]["first"]["lgb"] == 1.0
        assert _load_smearing_factors()["mansion"]["first"] == 1.05

        prop = SimpleNamespace(
            property_type="mansion",
            senyuMenseki=70.0,
            chikunengetsu="2015-05-01",
            address="東京都渋谷区広尾4丁目",
            address1="東京都",
            address2="渋谷区",
            address3="広尾4丁目",
            station1="広尾",
            toho1=5,
            price=12000,
        )
        preds = bulk_predict_first_stage([prop])
        assert len(preds) == 1
        assert preds[0] > 0
        assert loc_enc_mock.transform.called, "bulk_predict_first_stage must call location_encoder.transform!"
    finally:
        set_default_registry(None)


def test_legal_furuya_and_private_road_area_extraction():
    """法43条無接道・借地権設定底地・私道部分面積内訳が正しく抽出されること"""
    # 1. 建築基準法に定める道路に接していない -> is_saikenchiku_fuka == 1.0
    res_unbuildable = extract_legal_and_furuya_features(
        property_type="tochi",
        combined_text="対象不動産は、建築基準法に定める道路に接していないため、再建築時には建築審査会の同意を得て特定行政庁の許可を得る必要があります。",
        chikunen=0.0,
        tochi_area=184.8,
        tatemono_area=0.0,
        average_land_price=480000.0,
        scale_discount=1.0,
        cost_approach_value=8000.0,
        income_approach_value=5000.0,
        residual_land_value=7000.0,
    )
    assert res_unbuildable["is_saikenchiku_fuka"] == 1.0

    # 2. 借地権が設定されている土地（月々徴収する地代） -> 底地 (rights_ratio == 0.20) かつ special_sale_share == 1.0
    sokochi_text = "借地権（賃借権）が設定されている土地です。月々徴収する地代の額は150,940円です。"
    res_sokochi = extract_legal_and_furuya_features(
        property_type="tochi",
        combined_text=sokochi_text,
        chikunen=0.0,
        tochi_area=391.19,
        tatemono_area=0.0,
        average_land_price=1100000.0,
        scale_discount=0.85,
        cost_approach_value=35000.0,
        income_approach_value=15000.0,
        residual_land_value=30000.0,
    )
    assert res_sokochi["rights_ratio"] == 0.20
    assert _detect_special_sale_share(sokochi_text) == 1.0

    # 3. 私道部分面積の控除 (例: 288.54平米の内訳 ・私道部分284平米)
    prop_road = SimpleNamespace(
        tochiMenseki=117.11,
        biko="○288.54平米の内訳 ・私道部分284平米（持分6分の1） ・未利用地部分4.54平米（持分6分の1）",
    )
    assert _detect_special_sale_share(prop_road.biko) == 1.0


def test_property_data_validator_detects_office_address_contamination():
    """PropertyDataValidator.validate_property が担当店舗・ビル階数住所の誤抽出をゴミデータ（不正）として検知すること"""
    prop = SimpleNamespace(
        propertyName="ブランズ渋谷",
        address="〒102-0072千代田区飯田橋2丁目18番2号（大和ハウス九段ビル4階）",
        traffic="山手線 渋谷駅 徒歩8分",
        railway1="山手線",
        station1="渋谷",
        railwayWalkMinute1=8,
        price=85000000,
        senyuMenseki=65.0,
        madori="2LDK",
        chikunengetsuStr="2018年3月",
        kaisu="5階",
    )
    is_valid, reasons = PropertyDataValidator.validate_property(prop, "mansion")
    assert not is_valid
    assert any("担当店舗・ビル階数住所" in r for r in reasons)

    # 専有面積10㎡以下（例: 表面利回り5.58%との取り違え疑い）の区分マンションも面積異常として検知すること
    prop_tiny_area = SimpleNamespace(
        propertyName="パシフィック白金台",
        address="東京都港区白金台４丁目",
        traffic="東京メトロ南北線 白金台駅 徒歩7分",
        railway1="東京メトロ南北線",
        station1="白金台",
        railwayWalkMinute1=7,
        price=25800000,
        senyuMenseki=5.58,
        madori="ワンルーム",
        chikunengetsuStr="1977年3月",
        kaisu="2階",
    )
    is_valid_tiny, reasons_tiny = PropertyDataValidator.validate_property(prop_tiny_area, "mansion")
    assert not is_valid_tiny
    assert any("面積異常" in r for r in reasons_tiny)

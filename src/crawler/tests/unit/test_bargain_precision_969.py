from package.ml.features.builder import build_features
from package.ml.features.parsers import calculate_area_and_setback
from package.models.homes import HomesMansion
from package.parser.homesParser import HomesMansionParser
from package.utils.property_type_detector import PropertyTypeDetector
from package.utils.url_router import UrlRouter

def test_property_type_detector_distinguishes_unit_investment_mansion():
    """区分投資マンション（利回り表記＋専有面積または所在階）が apartment ではなく mansion と判定されること"""
    # ベルエール宇部文京町相当のスペック
    specs = {
        "物件名": "ベルエール宇部文京町",
        "表面利回り": "19.82%",
        "満室想定年収": "68.4万円",
        "現況": "賃貸中",
        "専有面積": "73.85㎡",
        "土地面積": "1848.35㎡",
        "建物構造": "SRC造",
    }
    # 辞書オブジェクトからの判定
    detected = PropertyTypeDetector.detect_from_object(specs)
    assert detected == "mansion", f"Expected mansion but got {detected}"

def test_property_type_detector_commercial_building_not_kodate():
    """商業ビル・一棟売りビルが土地＋建物面積があっても kodate にフォールバックしないこと"""
    obj = {
        "propertyName": "茂原市 一棟売りビル",
        "tochiMenseki": 530.43,
        "tatemonoMenseki": 1015.00,
    }
    detected = PropertyTypeDetector.detect_from_object(obj)
    assert detected in ["apartment", "investment", "building"], f"Expected apartment/building but got {detected}"
    assert detected != "kodate", "Commercial building must not be classified as kodate"

def test_mansion_features_tochi_area_is_zero():
    """mansion 特徴量において tochi_area が常に 0.0 固定となり価格インフレを防ぐこと"""
    prop = {
        "propertyName": "ベルエール宇部文京町",
        "price": 3450000,
        "senyuMenseki": 73.85,
        "tochiMenseki": 1848.35, # 敷地全体面積
        "address": "山口県宇部市文京町8-12",
        "grossYield": 19.82,
        "annualRent": 684000,
        "kouzou": "SRC造",
        "chikunengetsu": "1991-09-01",
    }
    _area, _tatemono_area, tochi_area, _setback_ratio = calculate_area_and_setback(prop, "mansion")
    assert tochi_area == 0.0, f"Expected tochi_area to be 0.0 for mansion, but got {tochi_area}"

    feat = build_features(prop, "mansion")
    assert feat["tochi_menseki"] == 0.0
    # 原価法計算で土地代（1848平米分）が混入していないこと
    # 山口県宇部市の公示地価ベースで559坪なら数千万円〜数億円になるが、mansionなら建物＋区分持分のみで数百万円程度に抑まる
    assert feat["cost_approach_value"] < 10000.0, f"cost_approach_value should be reasonable for unit mansion, got {feat['cost_approach_value']}"


def test_homes_invest_unit_mansion_routes_to_mansion_parser():
    """投資用Homes URLで区分マンションと判定された場合、UrlRouterがHomesMansionParserを解決してHomesMansionに格納されること"""
    url = "https://toushi.homes.co.jp/bukkendetail/12345/"
    specs = {
        "物件名": "ベルエール宇部文京町",
        "表面利回り": "19.82%",
        "専有面積": "73.85㎡",
        "土地面積": "1848.35㎡",
    }
    parser = UrlRouter.create_parser(url=url, specs=specs)
    assert isinstance(parser, HomesMansionParser), f"Expected HomesMansionParser, got {parser}"
    entity = parser.createEntity()
    assert isinstance(entity, HomesMansion), f"Expected HomesMansion entity, got {type(entity)}"


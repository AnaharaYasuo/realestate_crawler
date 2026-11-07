import math
import pytest
from unittest.mock import MagicMock
from package.ml.features.builder import build_features
from package.ml.features.feature_sets import FEATURE_SETS

class DummyTochi:
    pageUrl = "https://example.com/tochi/1"
    address = "東京都世田谷区成城"
    address1 = "東京都"
    address2 = "世田谷区"
    price = 50000000
    tochiMenseki = 350.0
    roadWidth = 3.2
    setback_ratio = 0.05
    youtoChiiki = "第一種低層住居専用地域"
    kenpei = 50.0
    youseki = 100.0
    chimoku = "宅地"

class DummyKodate:
    pageUrl = "https://example.com/kodate/1"
    address = "東京都練馬区石神井町"
    address1 = "東京都"
    address2 = "練馬区"
    price = 45000000
    tochiMenseki = 220.0
    tatemonoMenseki = 100.0
    roadWidth = 4.5
    setback_ratio = 0.0
    youtoChiiki = "第一種低層住居専用地域"
    kenpei = 50.0
    youseki = 100.0
    chimoku = "畑"
    kouzou = "木造"
    chikunengetsu = "2015-01"

class DummyApartment:
    pageUrl = "https://example.com/apartment/1"
    address = "大阪府吹田市江坂"
    address1 = "大阪府"
    address2 = "吹田市"
    price = 80000000
    tochiMenseki = 500.0
    tatemonoMenseki = 300.0
    roadWidth = 6.0
    setback_ratio = 0.0
    youtoChiiki = "近隣商業地域"
    kenpei = 80.0
    youseki = 300.0
    chimoku = "雑種地"
    kouzou = "鉄骨造"
    chikunengetsu = "2010-01"

def test_tochi_scale_disparity_and_low_price_features():
    """土地モデルで log_tochi_menseki, narrow_road_penalty が正しく生成されることを検証"""
    prop = DummyTochi()
    feats = build_features(prop, "tochi")
    
    assert "log_tochi_menseki" in feats
    assert feats["log_tochi_menseki"] == round(math.log(feats["tochi_menseki"]), 4)
    assert "narrow_road_penalty" in feats
    # roadWidth < 4.0 なので 0.80 ペナルティ
    assert feats["narrow_road_penalty"] == 0.80
    assert "scale_discount" in feats
    # 350m2 > 150m2 なので scale_discount < 1.0
    assert feats["scale_discount"] < 1.0

def test_cross_type_deployment_to_kodate_and_apartment():
    """戸建て・アパートモデルへの横断展開（log_tochi_menseki, narrow_road_penalty, chimoku_score）を検証"""
    # 1. 戸建て
    kodate = DummyKodate()
    kodate_feats = build_features(kodate, "kodate")
    assert "log_tochi_menseki" in kodate_feats
    assert kodate_feats["log_tochi_menseki"] == round(math.log(220.0), 4)
    assert kodate_feats["narrow_road_penalty"] == 1.0  # roadWidth >= 4.0
    assert kodate_feats["scale_discount"] < 1.0  # 220m2 > 150m2
    assert kodate_feats["chimoku_score"] == 0.94  # 畑の実勢ディスカウント率
    
    # 2. アパート
    apt = DummyApartment()
    apt_feats = build_features(apt, "apartment")
    assert "log_tochi_menseki" in apt_feats
    assert apt_feats["log_tochi_menseki"] == round(math.log(500.0), 4)
    assert apt_feats["narrow_road_penalty"] == 1.0
    assert apt_feats["scale_discount"] < 1.0  # 500m2 > 300m2
    assert apt_feats["chimoku_score"] == 0.92  # 雑種地の実勢ディスカウント率

def test_feature_sets_consistency():
    """FEATURE_SETS の各種別に新設特徴量が含まれていることを検証"""
    for ptype in ["tochi", "kodate", "apartment"]:
        for stage in ["first", "second"]:
            f_set = FEATURE_SETS[ptype][stage]
            assert "log_tochi_menseki" in f_set, f"log_tochi_menseki missing in {ptype}.{stage}"
            assert "narrow_road_penalty" in f_set, f"narrow_road_penalty missing in {ptype}.{stage}"
            assert "scale_discount" in f_set, f"scale_discount missing in {ptype}.{stage}"
            assert "chimoku_score" in f_set, f"chimoku_score missing in {ptype}.{stage}"

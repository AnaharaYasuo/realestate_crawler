# -*- coding: utf-8 -*-
"""
建物マスタ (BuildingMaster) & 名寄せリゾルバ 単体テスト
"""
import pytest
import os
import django

# Django環境のセットアップ（単体テスト実行用）
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "realestate_crawler.settings")
try:
    django.setup()
except Exception:
    pass

from package.models.building_master import BuildingMaster
from package.utils.building_resolver import BuildingResolver, normalize_building_name, normalize_building_address


def test_normalize_building_name():
    """建物名の部屋番号・広告文言・全半角正規化テスト"""
    raw_names = [
        "パークコート浜離宮 ザ タワー 2901号室",
        "【即入居可】パークコート浜離宮　ザ　タワー（29階）",
        "パークコート浜離宮　ザ・タワー 3階部分",
        "パークコート浜離宮ザタワー",
    ]
    normalized = [normalize_building_name(n) for n in raw_names]
    # すべて「パークコート浜離宮ザタワー」に正規化されること
    assert len(set(normalized)) == 1
    assert "パークコート浜離宮" in normalized[0]
    assert "2901" not in normalized[0]
    assert "即入居可" not in normalized[0]


def test_normalize_building_address():
    """住所の町丁目正規化テスト"""
    addr1 = "東京都港区浜松町１丁目２－３　パークコート2901"
    addr2 = "東京都港区浜松町1丁目2番3号"
    addr3 = "東京都港区浜松町1-2-3"

    norm1 = normalize_building_address(addr1)
    norm2 = normalize_building_address(addr2)
    norm3 = normalize_building_address(addr3)

    assert norm1 == "東京都港区浜松町1丁目"
    assert norm2 == "東京都港区浜松町1丁目"
    assert norm3 == "東京都港区浜松町1丁目"


@pytest.mark.django_db
def test_building_resolver_get_or_create():
    """リゾルバによる建物マスタ生成および既存マスタからのスペック自動伝搬テスト"""
    resolver = BuildingResolver()

    prop1 = {
        "propertyName": "ザ・パークハウス晴海タワーズ クロノレジデンス 15階",
        "address": "東京都中央区晴海2-3-30",
        "developer_brand": "三菱地所レジデンス（ザ・パークハウス）",
        "contractor_name": "鹿島建設",
        "earthquake_resistance": "免震",
        "elevator_available": True,
        "hallway_type": "内廊下",
        "total_units": 883
    }

    # 1件目: 新規作成
    bm1, created1 = resolver.resolve_and_update(prop1)
    assert created1 is True
    assert bm1.developer_brand == "三菱地所レジデンス（ザ・パークハウス）"
    assert bm1.elevator_available is True
    assert bm1.hallway_type == "内廊下"
    assert bm1.contractor_tier == "super_general"

    # 2件目: 同一棟の別部屋（スペック未記載でもマスタから自動補完）
    prop2 = {
        "propertyName": "【オーナーチェンジ】ザ・パークハウス晴海タワーズ　クロノレジデンス 3201号室",
        "address": "東京都中央区晴海2丁目3番30号",
        # ブランドや施工、EV等の情報が欠落している物件
    }

    bm2, created2 = resolver.resolve_and_update(prop2)
    assert created2 is False # 既存マスタにヒット
    assert bm2.id == bm1.id
    # マスタから自動補完されたスペック
    assert bm2.developer_brand == "三菱地所レジデンス（ザ・パークハウス）"
    assert bm2.elevator_available is True
    assert bm2.hallway_type == "内廊下"
    assert bm2.total_units == 883

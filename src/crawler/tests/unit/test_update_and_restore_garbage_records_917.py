# -*- coding: utf-8 -*-
"""
ゴミレコード・欠損データの UPDATE 復旧スクリプトの単体テスト (Issue #917)
"""
from unittest.mock import patch, MagicMock
import pytest

from scripts.maintenance.update_and_restore_garbage_records import (
    extract_kenbiya_address_from_url,
    normalize_mitsui_garbage_record,
    extract_nomura_madori,
    update_and_restore_records,
)


def test_extract_kenbiya_address_from_url():
    """健美家URLのスラッグから都道府県・市区町村・結合住所が正しく抽出されること"""
    url1 = "https://www.kenbiya.com/pp1/s/tokyo/setagaya-ku/re_4765126tpl/"
    pref, city, full = extract_kenbiya_address_from_url(url1)
    assert pref == "東京都"
    assert city == "世田谷区"
    assert full == "東京都世田谷区"

    url2 = "https://www.kenbiya.com/pp1/s/tokyo/mitaka-shi/re_4765094lo3/"
    pref, city, full = extract_kenbiya_address_from_url(url2)
    assert pref == "東京都"
    assert city == "三鷹市"
    assert full == "東京都三鷹市"


def test_normalize_mitsui_garbage_record():
    """三井レコードでラベル名そのものが入っているカラムがクリアされ、物件名は保持されること"""
    item = MagicMock()
    item.propertyName = "パークシティ中野 ザ タワー エアーズ"
    item.priceStr = "価格"
    item.price = 0
    item.address = "所在地"
    item.madori = "間取り"
    item.senyuMensekiStr = "専有面積"
    item.senyuMenseki = None

    changed_fields = normalize_mitsui_garbage_record(item)
    assert "priceStr" in changed_fields
    assert "address" in changed_fields
    assert "madori" in changed_fields
    assert "senyuMensekiStr" in changed_fields

    assert item.propertyName == "パークシティ中野 ザ タワー エアーズ"
    assert item.priceStr == ""
    assert item.price == 0
    assert item.address == ""
    assert item.madori == ""
    assert item.senyuMensekiStr == ""


def test_extract_nomura_madori():
    """物件名や備考から間取りを正規表現抽出できること"""
    assert extract_nomura_madori("三鷹市野崎2丁目 中古一戸建て 3SLDK", "") == "3SLDK"
    assert extract_nomura_madori("世田谷区", "南向き4LDK+Sの邸宅") == "4LDK+S"
    assert extract_nomura_madori("間取り情報なし", "") == ""


def test_update_and_restore_records_dry_run():
    """dry_run=True の場合、実更新が行われず件数のみ返却されること"""
    with patch("scripts.maintenance.update_and_restore_garbage_records.restore_mitsui_records") as mock_m:
        mock_m.return_value = {"MitsuiMansion": 10}
        res = update_and_restore_records(dry_run=True, target="mitsui")
        assert res.get("MitsuiMansion", 0) == 10


def test_update_and_restore_records_production_safety():
    """本番DB接続時に dry_run=False で実行した場合、RuntimeError で遮断されること"""
    with patch("scripts.maintenance.update_and_restore_garbage_records.assert_production_db_safety") as mock_guard:
        mock_guard.side_effect = RuntimeError("Blocked direct modification on production DB")
        with pytest.raises(RuntimeError) as exc:
            update_and_restore_records(dry_run=False, target="mitsui")
        assert "Blocked direct modification" in str(exc.value)

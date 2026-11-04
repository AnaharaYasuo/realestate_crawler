import pytest
from bs4 import BeautifulSoup
from unittest.mock import MagicMock

from package.parser.athomeParser import AthomeMansionParser, AthomeInvestmentApartmentParser
from package.parser.baseParser import SkipPropertyException
from package.utils.data_validator import PropertyDataValidator


def test_athome_basement_floor_detection():
    """地下階表記（地下1階 / B1F等）が所在階として正しく認識されること"""
    html = """
    <html>
    <head><title>テストマンション 地下1階</title></head>
    <body>
        <h1>テストマンション</h1>
        <table>
            <tr><th>階数 / 階建</th><td>地下1階 / 地上10階 地下1階建</td></tr>
            <tr><th>価格</th><td>3,500万円</td></tr>
            <tr><th>専有面積</th><td>65.0m2</td></tr>
        </table>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AthomeMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.athome.co.jp/mansion/6981791235/"
    item.kaisuStr = "地下1階 / 地上10階 地下1階建"

    parser._ensure_mansion_located_floor(item, soup, item.pageUrl)
    assert PropertyDataValidator._has_located_floor(item.kaisuStr)

    valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert not any("所在階が未抽出" in r for r in reasons)


def test_athome_buy_other_missing_building_area_skipped():
    """athome buy_other で建物面積・延床面積がない物件は一棟アパートとして不正登録されずスキップされること"""
    html = """
    <html>
    <head><title>売その他 投資用</title></head>
    <body>
        <h1>売その他</h1>
        <table>
            <tr><th>物件種目</th><td>売その他</td></tr>
            <tr><th>価格</th><td>1,500万円</td></tr>
            <tr><th>土地面積</th><td>150.0m2</td></tr>
            <tr><th>建物面積</th><td>-</td></tr>
        </table>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AthomeInvestmentApartmentParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.athome.co.jp/buy_other/1198396219/"

    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, soup)

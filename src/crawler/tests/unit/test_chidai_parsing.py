# -*- coding: utf-8 -*-
"""
地代（借地料）パース抽出機能の単体テスト (TDD)
"""
from bs4 import BeautifulSoup

from package.utils import converter
from package.parser.baseParser import ParserBase
from package.parser.athomeParser import AthomeKodateParser
from package.models.athome import AthomeKodate


class DummyParser(ParserBase):
    def getCharset(self):
        return "utf-8"

    def createEntity(self):
        return AthomeKodate()

    def _parsePrice(self, response, specs=None):
        return 50000000

    def _parsePriceStr(self, response, specs=None):
        return "5,000万円"

    def _parseAddress(self, response, specs=None):
        return "東京都中野区上高田５丁目"

    def _parsePropertyName(self, response, specs=None):
        return "中野区上高田 戸建て"

    def _parseTransport1(self, response, specs=None):
        return "西武新宿線 新井薬師前駅 徒歩7分"


def test_converter_parse_chidai_various_formats():
    """様々な地代表記（月額、年額、期間併記、万円表記）が月額円（int）に正規化されること"""
    # 期間併記（アットホーム典型例）
    assert converter.parse_chidai("20年 20,000円") == 20000
    assert converter.parse_chidai("30年 15,500円/月") == 15500
    assert converter.parse_chidai("期間20年 月額20,000円") == 20000
    
    # 万円表記
    assert converter.parse_chidai("2万円") == 20000
    assert converter.parse_chidai("月額2.5万円") == 25000
    assert converter.parse_chidai("2.0万円/月") == 20000
    assert converter.parse_chidai("1万2000円") == 12000
    
    # 円表記
    assert converter.parse_chidai("20,000円") == 20000
    assert converter.parse_chidai("20000円/月") == 20000
    assert converter.parse_chidai("月額 35,000 円") == 35000
    
    # 年額表記（月額換算: / 12）
    assert converter.parse_chidai("年額120,000円") == 10000
    assert converter.parse_chidai("24万円/年") == 20000
    assert converter.parse_chidai("年間240,000円") == 20000

    # 欠損・無効値・相談等
    assert converter.parse_chidai("－") is None
    assert converter.parse_chidai("-") is None
    assert converter.parse_chidai("―") is None
    assert converter.parse_chidai("--") is None
    assert converter.parse_chidai("なし") is None
    assert converter.parse_chidai("無") is None
    assert converter.parse_chidai("未定") is None
    assert converter.parse_chidai("相談") is None
    assert converter.parse_chidai("0円") is None
    assert converter.parse_chidai("") is None
    assert converter.parse_chidai(None) is None
    assert converter.parse_chidai("無効な文字列") is None

    # 数字のみフォールバック
    assert converter.parse_chidai("30000") == 30000
    assert converter.parse_chidai("360000/年") == 30000


def test_parser_base_parse_chidai_from_specs():
    """ParserBase が specs 辞書から地代フィールドを自動検知して抽出できること"""
    parser = DummyParser()
    
    # パターン1: 借地期間・地代（月額）
    specs1 = {"借地期間・地代（月額）": "20年 20,000円", "土地権利": "普通賃借権"}
    assert parser._parseChidai(None, specs=specs1) == 20000
    assert parser._parseChidaiStr(None, specs=specs1) == "20年 20,000円"
    
    # パターン2: 地代
    specs2 = {"地代": "月額 25,000円", "土地権利": "借地権"}
    assert parser._parseChidai(None, specs=specs2) == 25000
    
    # パターン3: 借地料
    specs3 = {"借地料": "18,000円/月"}
    assert parser._parseChidai(None, specs=specs3) == 18000


def test_athome_kodate_target_property_html_parsing():
    """ユーザー指定URLの実ページ相当HTMLから地代および借地権が完全抽出されること"""
    html = """
    <html>
    <head><title>【アットホーム】中野区 上高田５丁目 2階建 ３ＬＤＫ[6991051405]</title></head>
    <body>
      <div id="detailTitleArea"><h2><em>中野区 上高田５丁目 戸建て</em></h2></div>
      <table>
        <tr><th>価格</th><td>4,380万円</td></tr>
        <tr><th>所在地</th><td>東京都中野区上高田５丁目</td></tr>
        <tr><th>交通</th><td>西武新宿線 / 新井薬師前駅 徒歩7分</td></tr>
        <tr><th>土地面積</th><td>65.40㎡</td></tr>
        <tr><th>建物面積</th><td>78.20㎡</td></tr>
        <tr><th>土地権利</th><td>普通賃借権</td></tr>
        <tr><th>借地期間・地代（月額）</th><td>20年 20,000円</td></tr>
        <tr><th>権利金</th><td>－</td></tr>
      </table>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AthomeKodateParser()
    item = AthomeKodate()
    item = parser._parsePropertyDetailPage(item, soup)
    item = parser.clean_parsed_item(item)
    
    # 地代フィールドの検証
    assert item.tochikenri == "普通賃借権"
    assert item.chidai == 20000
    assert item.chidaiStr == "20年 20,000円"

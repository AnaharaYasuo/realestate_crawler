# -*- coding: utf-8 -*-
"""
ヘッダー行・ラベル名誤登録防止ガードの単体テスト (Issue #917)
"""
import pytest
from bs4 import BeautifulSoup
from unittest.mock import MagicMock

from package.parser.baseParser import SkipPropertyException
from package.parser.mitsuiParser import MitsuiMansionParser


def test_base_parser_assert_not_header_row():
    """ParserBase._assert_not_header_row がヘッダー行を検出して SkipPropertyException を送出すること"""
    parser = MitsuiMansionParser()

    # 1. priceStr がヘッダー行
    for bad_price in ["価格", "販売価格", "物件価格", "価格（非課税）", "価格(非課税)"]:
        item = MagicMock()
        item.priceStr = bad_price
        item.address = "東京都港区芝浦1丁目"
        with pytest.raises(SkipPropertyException) as exc:
            parser._assert_not_header_row(item)
        assert "Header row detected" in str(exc.value)

    # 2. address がヘッダー行
    for bad_addr in ["所在地", "住所", "物件所在地"]:
        item = MagicMock()
        item.priceStr = "5,980万円"
        item.address = bad_addr
        with pytest.raises(SkipPropertyException) as exc:
            parser._assert_not_header_row(item)
        assert "Header row detected" in str(exc.value)

    # 3. 正常な物件データは例外を送出しないこと
    valid_item = MagicMock()
    valid_item.priceStr = "5,980万円"
    valid_item.address = "東京都港区芝浦1丁目"
    # 例外が送出されないことを確認
    parser._assert_not_header_row(valid_item)


def test_mitsui_parser_skips_header_row():
    """三井パーサーがヘッダー行のみのHTMLをパースした際に SkipPropertyException を送出すること"""
    mansion_parser = MitsuiMansionParser()
    item = mansion_parser.createEntity()

    header_html = """
    <html>
      <body>
        <h1 class="headline1">パークシティ中野 ザ タワー エアーズ</h1>
        <table>
          <tr><th>価格</th><td>価格</td></tr>
          <tr><th>所在地</th><td>所在地</td></tr>
          <tr><th>間取り</th><td>間取り</td></tr>
          <tr><th>専有面積</th><td>専有面積</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(header_html, "html.parser")

    with pytest.raises(SkipPropertyException):
        mansion_parser._parsePropertyDetailPage(item, soup)


def test_mitsui_parser_accepts_valid_property():
    """三井パーサーが正常な物件HTMLをパースした際は正常にデータを返すこと"""
    mansion_parser = MitsuiMansionParser()
    item = mansion_parser.createEntity()

    valid_html = """
    <html>
      <body>
        <h1 class="headline1">パークシティ中野 ザ タワー エアーズ 1001号室</h1>
        <div class="text-price-regular">8,500万円</div>
        <table>
          <tr><th>所在地</th><td>東京都中野区中野4丁目</td></tr>
          <tr><th>間取り</th><td>2LDK</td></tr>
          <tr><th>専有面積</th><td>55.2㎡</td></tr>
          <tr><th>築年月</th><td>2026年3月</td></tr>
          <tr><th>交通</th><td>JR中央線 中野駅 徒歩5分</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(valid_html, "html.parser")
    result = mansion_parser._parsePropertyDetailPage(item, soup)
    assert result.address == "東京都中野区中野4丁目"
    assert result.madori == "2LDK"

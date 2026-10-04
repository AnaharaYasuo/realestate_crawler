# -*- coding: utf-8 -*-
"""
Issue #677 回帰テスト: SmtrcMansion バリデーションおよび floorType / kyutaishin パース検証
"""
import datetime
from decimal import Decimal
from bs4 import BeautifulSoup
import pytest

from package.models.smtrc import SmtrcMansion, SmtrcKodate, SmtrcTochi, SmtrcInvestment
from package.parser.smtrcParser import SmtrcMansionParser


def test_smtrc_mansion_models_blank_true():
    """SmtrcMansion および関連モデルの null=True フィールドで full_clean() がエラーなく通ることを検証"""
    mansion = SmtrcMansion(
        url="https://smtrc.jp/detail/CompareDetails?propertyCode=NF72C9013&pageId=D010",
        propertyName="テストマンション",
        price=50000000,
        address="東京都港区麻布十番1-1-1",
    )
    # full_clean() should pass without field validation errors on optional fields
    mansion.full_clean()
    assert mansion.floorType_chijo is None
    assert mansion.floorType_chika is None
    assert mansion.floorType_kai is None
    assert mansion.kyutaishin is None


def test_smtrc_mansion_parser_floor_and_kyutaishin():
    """SmtrcMansionParser が所在階（地上/地下）と旧耐震フラグ、構造を正しくパースすることを検証"""
    parser = SmtrcMansionParser()
    item = parser.createEntity()

    sample_html = """
    <html>
      <body>
        <h1 class="property-name">ライオンズマンション麻布十番</h1>
        <div class="price-value">4,980万円</div>
        <table class="spec-table">
          <tr><th>所在地</th><td>東京都港区麻布十番</td></tr>
          <tr><th>専有面積</th><td>65.50㎡</td></tr>
          <tr><th>所在階</th><td>3階 / 地上10階 地下1階建</td></tr>
          <tr><th>築年月</th><td>1980年5月</td></tr>
          <tr><th>構造</th><td>鉄骨鉄筋コンクリート造</td></tr>
          <tr><th>総戸数</th><td>45戸</td></tr>
          <tr><th>管理費</th><td>15,000円</td></tr>
          <tr><th>修繕積立金</th><td>12,000円</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(sample_html, "html.parser")
    parsed_item = parser._parsePropertyDetailPage(item, soup)

    assert parsed_item.floorType_kai == 3
    assert parsed_item.floorType_chijo == 10
    assert parsed_item.floorType_chika == 1
    assert parsed_item.floorType_kouzou == "ＳＲＣ造"
    assert parsed_item.kyutaishin == 1  # 1980 < 1982 => 旧耐震
    assert parsed_item.senyuMenseki == Decimal("65.50")
    assert parsed_item.soukosu == 45
    assert parsed_item.kanrihi == 15000
    assert parsed_item.syuzenTsumitate == 12000

    # full_clean() should pass cleanly
    parsed_item.url = "https://smtrc.jp/detail/CompareDetails?propertyCode=NF72C9013&pageId=D010"
    parsed_item.full_clean()

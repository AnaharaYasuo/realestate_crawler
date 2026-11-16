import pytest
from decimal import Decimal
from bs4 import BeautifulSoup
from package.parser.homesParser import HomesInvestmentApartmentParser

@pytest.mark.asyncio
async def test_homes_investment_kodate_land_area_preservation():
    """専有面積が「不明」と記載された一棟貸家・アパートで、土地面積が消失せず保持されることを検証 (Issue #1544)"""
    html = """
    <html>
      <head><title>【ホームズ】埼玉県鶴ヶ島市の一棟売りアパート (利回り: 13.00％ 価格: 600万円)</title></head>
      <body>
        <h1>埼玉県鶴ヶ島市 脚折町3丁目貸家</h1>
        <table>
          <tr><th>価格</th><td>600万円</td></tr>
          <tr><th>利回り</th><td>13.00%</td></tr>
          <tr><th>満室想定年収</th><td>78万円</td></tr>
          <tr><th>土地面積</th><td>120.68㎡ 【36.5坪】</td></tr>
          <tr><th>建物面積</th><td>57.72㎡</td></tr>
          <tr><th>専有面積(最小 - 最大)</th><td>不明</td></tr>
          <tr><th>所在階／階数</th><td>2階建/1戸</td></tr>
          <tr><th>土地権利</th><td>所有権</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = HomesInvestmentApartmentParser()
    item = parser.createEntity()
    item = parser._parsePropertyDetailPage(item, soup)

    assert item.tochiMenseki == Decimal("120.68")
    assert item.tatemonoMenseki == Decimal("57.72")
    assert item.price == 6000000
    assert getattr(item, "propertyType", "Apartment") != "Mansion"

@pytest.mark.asyncio
async def test_homes_investment_unit_mansion_valid_exclusive_area():
    """有効な専有面積数値がある区分投資マンションでは、正常に区分判定され土地面積がクリアされることを検証"""
    html = """
    <html>
      <head><title>【ホームズ】東京都新宿区の区分マンション</title></head>
      <body>
        <h1>パークハイツ新宿 305号室</h1>
        <table>
          <tr><th>価格</th><td>1,500万円</td></tr>
          <tr><th>利回り</th><td>6.50%</td></tr>
          <tr><th>満室想定年収</th><td>97.5万円</td></tr>
          <tr><th>土地面積</th><td>300.00㎡</td></tr>
          <tr><th>建物面積</th><td>25.50㎡</td></tr>
          <tr><th>専有面積</th><td>25.50㎡</td></tr>
          <tr><th>所在階</th><td>3階</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = HomesInvestmentApartmentParser()
    item = parser.createEntity()
    item = parser._parsePropertyDetailPage(item, soup)

    assert item.tochiMenseki is None
    assert getattr(item, "senyuMenseki", None) == Decimal("25.50")
    assert getattr(item, "propertyType", None) == "Mansion"

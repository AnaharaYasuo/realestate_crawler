from bs4 import BeautifulSoup
from package.parser.athomeParser import AthomeKodateParser, AthomeMansionParser


def test_athome_mansion_buy_other_does_not_require_land_area():
    html = """
    <html><head><title>売その他 マンション</title></head><body>
    <div id="detailTitleArea"><h2><em>テストマンション 3階</em></h2></div>
    <table>
      <tr><th>価格</th><td>2,500万円</td></tr>
      <tr><th>所在地</th><td>東京都渋谷区1-1-1</td></tr>
      <tr><th>間取り</th><td>2LDK</td></tr>
      <tr><th>専有面積</th><td>55.00㎡</td></tr>
      <tr><th>階建/階</th><td>5階建 / 3階</td></tr>
      <tr><th>物件種目</th><td>中古マンション</td></tr>
    </table>
    </body></html>
    """
    parser = AthomeMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.athome.co.jp/buy_other/1198396219/"
    item._switched_from_property_type = "tochi"
    soup = BeautifulSoup(html, "html.parser")
    result = parser._parsePropertyDetailPage(item, soup)
    assert result.senyuMenseki == 55.0


def test_athome_kodate_buy_other_allowed_when_switched():
    html = """
    <html><head><title>売その他 戸建</title></head><body>
    <div id="detailTitleArea"><h2><em>テスト戸建</em></h2></div>
    <table>
      <tr><th>価格</th><td>950万円</td></tr>
      <tr><th>所在地</th><td>東京都府中市紅葉丘2丁目</td></tr>
      <tr><th>間取り</th><td>3DK</td></tr>
      <tr><th>土地面積</th><td>100.00㎡</td></tr>
      <tr><th>建物面積</th><td>80.00㎡</td></tr>
      <tr><th>物件種目</th><td>売その他</td></tr>
    </table>
    </body></html>
    """
    parser = AthomeKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.athome.co.jp/buy_other/1171717507/"
    item._switched_from_property_type = "tochi"
    soup = BeautifulSoup(html, "html.parser")
    result = parser._parsePropertyDetailPage(item, soup)
    assert result.price == 9500000

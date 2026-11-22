from bs4 import BeautifulSoup

from package.parser.mitsuiParser import MitsuiKodateParser, MitsuiTochiParser
from package.parser.tohoParser import TohoKodateParser


def test_toho_get_specs_extracts_tab_std():
    html = """
    <html><body>
      <div class="tab_std">
        <div class="hyo_t">所在地</div>
        <div class="hyo_txt">東京都八王子市大楽寺町</div>
      </div>
      <div class="tab_std">
        <div class="hyo_t">間取り</div>
        <div class="hyo_txt">4SLDK</div>
      </div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = TohoKodateParser()
    specs = parser._get_specs(soup)
    assert specs["所在地"] == "東京都八王子市大楽寺町"
    assert specs["間取り"] == "4SLDK"


def test_mitsui_kodate_allows_switched_from_tochi_url():
    html = """
    <html><body>
      <h1>テスト物件</h1>
      <table>
        <tr><th>所在地</th><td>京都府京都市上京区</td></tr>
        <tr><th>価格</th><td>4,280万円</td></tr>
        <tr><th>建物面積</th><td>90.00㎡</td></tr>
        <tr><th>土地面積</th><td>100.00㎡</td></tr>
      </table>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/tochi/bkdetail/FYL7QA10/"
    item._switched_from_property_type = "tochi"
    parsed = parser._parsePropertyDetailPage(item, soup)
    assert parsed.address == "京都府京都市上京区"


def test_mitsui_tochi_allows_switched_from_kodate_url():
    html = """
    <html><body>
      <h1>テスト土地</h1>
      <table>
        <tr><th>所在地</th><td>東京都世田谷区</td></tr>
        <tr><th>価格</th><td>5,000万円</td></tr>
        <tr><th>土地面積</th><td>100.00㎡</td></tr>
      </table>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiTochiParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/kodate/bkdetail/FN3BRA06/"
    item._switched_from_property_type = "kodate"
    parsed = parser._parsePropertyDetailPage(item, soup)
    assert parsed.address == "東京都世田谷区"

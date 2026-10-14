from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase
from package.parser.mitsuiParser import MitsuiKodateParser, MitsuiMansionParser
from package.parser.athomeParser import AthomeKodateParser
from package.parser.afrParser import AfrKodateParser
from package.utils.data_validator import PropertyDataValidator


def test_base_parser_rejects_non_property_urls():
    """/support/, /mikata/, /guide/, /manual/, /column/ などの非物件URLが拒否されること"""
    urls = [
        "https://www.rehouse.co.jp/buy/kodate/support/mikata/",
        "https://www.rehouse.co.jp/buy/mansion/guide/first/",
        "https://www.athome.co.jp/manual/flow/",
        "https://www.athome.co.jp/column/point/",
    ]
    for u in urls:
        assert ParserBase._is_non_property_href(u) is True


def test_mitsui_kodate_madori_and_traffic():
    """三井戸建で間取り・交通・接道が抽出されバリデータを通過すること"""
    html = """
    <html>
      <head><title>三井のリハウス 戸建て詳細</title></head>
      <body>
        <h1>世田谷区 桜新町 戸建</h1>
        <table>
          <tr><th>間取り</th><td>4LDK</td></tr>
          <tr><th>建物面積</th><td>105.5m²</td></tr>
          <tr><th>土地面積</th><td>120.0m²</td></tr>
          <tr><th>築年月</th><td>2018年3月</td></tr>
          <tr><th>価格</th><td>8,980万円</td></tr>
          <tr><th>所在地</th><td>東京都世田谷区桜新町1丁目</td></tr>
          <tr><th>交通</th><td><p>東急田園都市線 「桜新町」駅 徒歩5分</p></td></tr>
          <tr><th>道路状況</th><td>南側 公道 幅員約6.0ｍ 接面約10.5ｍ</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/kodate/bkdetail/FSDBRA09/"
    item = parser._parsePropertyDetailPage(item, soup)

    assert item.madori == "4LDK"
    assert "桜新町" in item.traffic
    assert float(item.douroHaba) > 0
    assert float(item.setsumen) > 0

    is_valid, reasons = PropertyDataValidator.validate_property(item, "kodate")
    assert is_valid is True, f"Validation failed: {reasons}"


def test_mitsui_mansion_floor_and_traffic():
    """三井マンションで所在階と交通が抽出されバリデータを通過すること"""
    html = """
    <html>
      <head><title>三井のリハウス マンション詳細</title></head>
      <body>
        <h1>グランドメゾン品川</h1>
        <table>
          <tr><th>間取り</th><td>3LDK</td></tr>
          <tr><th>専有面積</th><td>75.2m²</td></tr>
          <tr><th>築年月</th><td>2015年11月</td></tr>
          <tr><th>価格</th><td>7,480万円</td></tr>
          <tr><th>所在地</th><td>東京都品川区東品川2丁目</td></tr>
          <tr><th>所在階 / 階建</th><td>5階 / 地上15階建</td></tr>
          <tr><th>交通</th><td><p>JR山手線 「品川」駅 徒歩10分</p></td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/mansion/bkdetail/F15BRA1B/"
    item = parser._parsePropertyDetailPage(item, soup)

    assert item.kaisu == 5
    assert "5階" in item.kaisuStr
    assert "品川" in item.traffic

    is_valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert is_valid is True, f"Validation failed: {reasons}"


def test_athome_kodate_madori_and_chikunengetsu_fallback():
    """アットホーム戸建で間取りと完成時期（築年月フォールバック）が抽出されバリデータを通過すること"""
    html = """
    <html>
      <head><title>【アットホーム】横浜市港北区 新築一戸建て｜新築一戸建て購入の物件情報</title></head>
      <body>
        <table>
          <tr><th>間取り</th><td>4LDK</td></tr>
          <tr><th>建物面積</th><td>98.5m²</td></tr>
          <tr><th>土地面積</th><td>110.0m²</td></tr>
          <tr><th>完成時期</th><td>2023年6月</td></tr>
          <tr><th>価格</th><td>5,280万円</td></tr>
          <tr><th>所在地</th><td>神奈川県横浜市港北区大倉山3丁目</td></tr>
          <tr><th>交通</th><td>東急東横線 / 大倉山駅 徒歩8分</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AthomeKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.athome.co.jp/kodate/1003225887"
    item = parser._parsePropertyDetailPage(item, soup)

    assert item.madori == "4LDK"
    assert "2023年" in item.chikunengetsuStr
    assert item.chikunengetsu is not None

    is_valid, reasons = PropertyDataValidator.validate_property(item, "kodate")
    assert is_valid is True, f"Validation failed: {reasons}"


def test_afr_kodate_property_name_fallback():
    """ヘーベルハウスでH2/H1がない場合でもtitleから物件名が抽出されること"""
    html = """
    <html>
      <head><title>旭化成ヘーベルハウス 世田谷ステージ | 旭化成ホームズ</title></head>
      <body>
        <table>
          <tr><th>間取り</th><td>3LDK</td></tr>
          <tr><th>価格</th><td>6,500万円</td></tr>
          <tr><th>所在地</th><td>東京都世田谷区桜上水</td></tr>
          <tr><th>交通</th><td>京王線 桜上水駅 徒歩7分</td></tr>
          <tr><th>土地面積</th><td>100m²</td></tr>
          <tr><th>建物面積</th><td>90m²</td></tr>
          <tr><th>築年月</th><td>2019年5月</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AfrKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.hebel-haus.com/buy/kodate/detail/?bno=12345"
    item = parser._parsePropertyDetailPage(item, soup)

    assert item.propertyName != ""
    assert "世田谷" in item.propertyName

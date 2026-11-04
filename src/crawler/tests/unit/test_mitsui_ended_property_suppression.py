import pytest
from bs4 import BeautifulSoup
from unittest.mock import MagicMock

from package.parser.mitsuiParser import MitsuiMansionParser, MitsuiKodateParser
from package.parser.baseParser import ListingEndedException


def test_mitsui_mansion_ended_listing_raises_exception():
    """三井のリハウスの掲載終了・成約済ページ（中野エアーズ等）で ListingEndedException が送出されること"""
    html = """
    <html>
    <head><title>パークシティ中野 ザ タワー エアーズの物件情報（FKJBFA06）｜三井のリハウス</title></head>
    <body>
        <div class="property-detail-container">
            <h1>パークシティ中野 ザ タワー エアーズ</h1>
            <p>申し訳ございません。お探しの物件は、掲載が終了したか、成約済みになった可能性があります。</p>
        </div>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKJBFA06/"

    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(item, soup)


def test_mitsui_kodate_ended_listing_raises_exception():
    """三井のリハウス戸建ての掲載終了ページで ListingEndedException が送出されること"""
    html = """
    <html>
    <head><title>堺市美原区さつき野東2丁目の物件情報（FNABEA0A）｜三井のリハウス</title></head>
    <body>
        <h1>堺市美原区さつき野東2丁目</h1>
        <div>お探しの物件は、掲載が終了したか、成約済みになった可能性があります。</div>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/kodate/bkdetail/FNABEA0A/"

    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(item, soup)


def test_mitsui_mansion_property_detail_infos_traffic():
    """property-detail-infos クラス内に配置された交通情報を正しくパースすること"""
    html = """
    <html>
    <head><title>白金ザ・スカイ 東棟</title></head>
    <body>
        <h1>白金ザ・スカイ 東棟</h1>
        <div class="property-detail-infos">
            交通 東京メトロ南北線 白金高輪駅 徒歩3分 都営三田線 白金高輪駅 徒歩3分
            所在地 東京都港区白金１丁目
        </div>
        <table>
            <tr><th>物件種別</th><td>中古マンション</td></tr>
            <tr><th>価格</th><td>56,000万円</td></tr>
            <tr><th>専有面積</th><td>114.34m2</td></tr>
            <tr><th>間取り</th><td>2LDK</td></tr>
            <tr><th>階数 / 階建</th><td>44階 / 地上45階 地下1階建</td></tr>
            <tr><th>築年月</th><td>2023年02月築</td></tr>
        </table>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/mansion/bkdetail/F15BTA33/"

    parsed_item = parser._parsePropertyDetailPage(item, soup)
    assert parsed_item.traffic != ""
    assert "白金高輪" in parsed_item.traffic
    assert parsed_item.station1 == "白金高輪"

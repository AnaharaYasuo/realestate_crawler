"""Unit tests for Odakyu investment migration to ls1.odakyu-chukai.com (Issue #874)."""
import asyncio
from decimal import Decimal

from bs4 import BeautifulSoup

from package.models.odakyu import OdakyuInvestment
from package.parser.odakyuParser import OdakyuInvestmentParser


def test_odakyu_investment_ls1_parse_root_yields_property_links():
    """Verify listing page on ls1.odakyu-chukai.com extracts /properties/<id> URLs."""
    html = """
    <html><body>
      <div class="property-list">
        <a href="/properties/177378">高円寺南アパート</a>
        <a href="/properties/146808">ZOOM横浜関内</a>
        <a href="https://ls1.odakyu-chukai.com/properties/181350">一棟アパート エステートピア</a>
        <a href="/about">About Us</a>
      </div>
    </body></html>
    """
    parser = OdakyuInvestmentParser()
    soup = BeautifulSoup(html, "html.parser")

    async def collect():
        return [u async for u in parser.parseRootPage(soup)]

    links = asyncio.run(collect())
    assert "https://ls1.odakyu-chukai.com/properties/177378" in links
    assert "https://ls1.odakyu-chukai.com/properties/146808" in links
    assert "https://ls1.odakyu-chukai.com/properties/181350" in links
    assert len(links) == 3


def test_odakyu_investment_ls1_detail_page_parse():
    """Verify detail page parse on ls1.odakyu-chukai.com extracts all required specs."""
    html = """
    <html><body>
      <h1>高円寺南アパート</h1>
      <h3>物件概要</h3>
      <dl>
        <dt>所在地</dt><dd>東京都杉並区高円寺南５丁目</dd>
        <dt>交通</dt><dd>東京メトロ丸ノ内線「東高円寺」駅 徒歩5分</dd>
        <dt>価格</dt><dd>15,000万円</dd>
        <dt>オーナーチェンジ</dt><dd>あり</dd>
        <dt>想定利回り</dt><dd>5.16%</dd>
        <dt>土地面積</dt><dd>105.19㎡(約31.82坪)/公簿</dd>
        <dt>土地権利</dt><dd>所有権</dd>
        <dt>建物(専有)面積</dt><dd>112.38㎡(約33.99坪)</dd>
        <dt>間取り</dt><dd>1R</dd>
        <dt>築年月</dt><dd>2023年11月</dd>
        <dt>総戸数</dt><dd>10</dd>
        <dt>建物構造</dt><dd>木造</dd>
        <dt>現況</dt><dd>賃貸中</dd>
        <dt>物件番号</dt><dd>VD0121</dd>
      </dl>
    </body></html>
    """
    parser = OdakyuInvestmentParser()
    soup = BeautifulSoup(html, "html.parser")
    item = OdakyuInvestment()
    item.pageUrl = "https://ls1.odakyu-chukai.com/properties/177378"

    parsed = parser._parsePropertyDetailPage(item, soup)
    assert parsed.propertyName == "高円寺南アパート"
    assert parsed.price == 150000000
    assert parsed.grossYield == Decimal("5.16")
    assert parsed.annualRent == 7740000
    assert parsed.monthlyRent == 645000
    assert parsed.address == "東京都杉並区高円寺南５丁目"
    assert parsed.address1 == "東京都"
    assert parsed.address2 == "杉並区"
    assert parsed.address3 == "高円寺南５丁目"
    assert parsed.tatemonoMenseki == Decimal("112.38")
    assert parsed.tochiMenseki == Decimal("105.19")
    assert parsed.kouzou == "木造"
    assert parsed.currentStatus == "賃貸中"

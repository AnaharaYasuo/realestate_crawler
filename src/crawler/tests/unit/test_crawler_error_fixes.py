# -*- coding: utf-8 -*-
import pytest
from bs4 import BeautifulSoup
from package.parser.nomuraParser import NomuraMansionParser
from package.parser.sumifuParser import SumifuMansionParser, SumifuTochiParser
from package.parser.baseParser import SkipPropertyException
from package.utils.url_router import UrlRouter


def test_nomura_price_extraction_with_nested_spans():
    """野村不動産の複数spanで構成された価格（例: 5億9,900万円）の全額抽出を検証"""
    html = """
    <html>
    <body>
        <h1>プラウドタワー渋谷</h1>
        <div class="text">
            <div class="name">プラウドタワー渋谷</div>
            <div class="price"><span class="num">5</span><span class="unit">億</span><span class="num">9,900</span><span class="unit">万円</span></div>
        </div>
        <table>
            <tr><th>所在地</th><td>東京都渋谷区</td></tr>
            <tr><th>専有面積</th><td>70.5m2</td></tr>
        </table>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = NomuraMansionParser()
    price_str = parser._parsePriceStr(soup)
    assert "5億" in price_str and "9,900万" in price_str, f"Extracted price_str unexpected: {price_str}"
    price = parser._parsePrice(soup)
    assert price == 599000000, f"Expected 599000000, got {price}"


@pytest.mark.asyncio
async def test_sumifu_list_filtering():
    """住友ステップ一覧ページで他種別（戸建て・土地）や賃貸リンクが除外されることを検証"""
    html = """
    <html>
    <body>
        <div id="searchResultBlock">
            <a class="property-info-anchor" href="/mansion/detail_11111/">マンション1</a>
            <a class="property-info-anchor" href="/kodate/detail_22222/">戸建て1（除外対象）</a>
            <a class="property-info-anchor" href="/tochi/detail_33333/">土地1（除外対象）</a>
            <a class="property-info-anchor" href="/chintai/detail/44444/">賃貸1（除外対象）</a>
            <a class="property-info-anchor" href="/inquiry/form/">問い合わせ（除外対象）</a>
        </div>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = SumifuMansionParser()
    extracted_urls = [url async for url in parser.parsePropertyListPage(soup)]
    assert len(extracted_urls) == 1, f"Expected 1 mansion URL, got {extracted_urls}"
    assert "mansion/detail_11111" in extracted_urls[0]


def test_url_router_stepon_underscore_and_pro():
    """UrlRouter が住友不動産の detail_12345/ 形式および投資用 /pro/detail_ 形式を解決できることを検証"""
    mansion_url = "https://www.stepon.co.jp/mansion/detail_36693072/"
    route_mansion = UrlRouter.resolve(mansion_url)
    assert route_mansion is not None, f"Failed to resolve {mansion_url}"
    assert route_mansion["site"] == "sumifu"
    assert route_mansion["property_type"] == "mansion"

    kodate_url = "https://www.stepon.co.jp/kodate/detail_12345678/"
    route_kodate = UrlRouter.resolve(kodate_url)
    assert route_kodate is not None, f"Failed to resolve {kodate_url}"
    assert route_kodate["property_type"] == "kodate"

    invest_url = "https://www.stepon.co.jp/pro/detail_99999999/"
    route_invest = UrlRouter.resolve(invest_url)
    assert route_invest is not None, f"Failed to resolve {invest_url}"
    assert route_invest["site"] == "sumifu"
    assert route_invest["property_type"] == "apartment"


@pytest.mark.asyncio
async def test_base_parser_non_property_url_skip():
    """非物件URL（宣伝、360度ツアー、賃貸など）が即座に SkipPropertyException となることを検証"""
    parser = SumifuMansionParser()
    non_property_urls = [
        "https://www.livable.co.jp/shiritai/user/baibai/benefit/",
        "https://www.rehouse.co.jp/buy/360/building/",
        "https://www.stepon.co.jp/chintai/detail/1613C811/",
        "https://www.stepon.co.jp/inquiry/stepon/input/",
    ]
    for url in non_property_urls:
        with pytest.raises(SkipPropertyException):
            await parser.parsePropertyDetailPage(session=None, url=url)


def test_sumifu_none_replace_safety():
    """sumifuParser の利回りや地勢等で NoneType.replace 例外が発生しないことを検証"""
    from package.parser.sumifuParser import SumifuInvestmentApartmentParser
    parser = SumifuInvestmentApartmentParser()
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    # Gross yield with empty specs
    y = parser._parseGrossYield(soup)
    assert y == 0

    tochi_parser = SumifuTochiParser()
    c = tochi_parser._parseChisei(soup)
    assert c == "-"

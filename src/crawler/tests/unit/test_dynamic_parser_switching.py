# -*- coding: utf-8 -*-
import pytest
from unittest.mock import AsyncMock, patch
from package.utils.url_router import UrlRouter
from package.parser.sumifuParser import SumifuMansionParser, SumifuKodateParser, SumifuInvestmentApartmentParser
from package.models.sumifu import SumifuMansion, SumifuKodate, SumifuInvestmentApartment


def test_url_router_create_parser():
    """UrlRouter.create_parser が適切なパーサーインスタンスを生成できることを検証"""
    # 1. 通常のURL解決
    parser_mansion = UrlRouter.create_parser("https://www.stepon.co.jp/mansion/detail_12345/")
    assert isinstance(parser_mansion, SumifuMansionParser)

    # 2. property_type 指定による動的解決
    parser_kodate = UrlRouter.create_parser(
        "https://www.stepon.co.jp/mansion/detail_12345/",
        property_type="kodate"
    )
    assert isinstance(parser_kodate, SumifuKodateParser)

    # 3. 投資用種別の動的解決
    parser_invest = UrlRouter.create_parser(
        "https://www.stepon.co.jp/mansion/detail_12345/",
        property_type="apartment"
    )
    assert isinstance(parser_invest, SumifuInvestmentApartmentParser)

    # 4. 未対応URL
    assert UrlRouter.create_parser("https://unknown-site.com/detail/1") is None


@pytest.mark.asyncio
async def test_base_parser_switches_mansion_to_kodate(caplog):
    """MansionParser が詳細ページ到着時に戸建てHTMLを検知し、KodateParserに自己切り替えすることを検証"""
    url = "https://www.stepon.co.jp/mansion/detail_12345/"
    kodate_html = """
    <html>
    <head><title>【住友不動産ステップ】横浜市青葉区の中古一戸建て</title></head>
    <body>
        <h1>横浜市青葉区美しが丘 中古一戸建て</h1>
        <div class="c_price_wrap">4,500万円</div>
        <table class="table-row">
            <tr><th>物件種別</th><td>中古一戸建</td></tr>
            <tr><th>価格</th><td>4,500万円</td></tr>
            <tr><th>所在地</th><td>神奈川県横浜市青葉区美しが丘</td></tr>
            <tr><th>土地面積</th><td>120.5㎡</td></tr>
            <tr><th>建物面積</th><td>95.2㎡</td></tr>
            <tr><th>間取り</th><td>3LDK</td></tr>
            <tr><th>築年月</th><td>2018年5月</td></tr>
            <tr><th>構造</th><td>木造</td></tr>
        </table>
    </body>
    </html>
    """.encode("utf-8")

    parser = SumifuMansionParser()
    assert parser.property_type == "mansion"

    session = AsyncMock()
    with patch.object(parser, "_getContent", return_value=kodate_html):
        with caplog.at_level("INFO"):
            item = await parser.parsePropertyDetailPage(session, url)

    # 返却エンティティが戸建てモデル（SumifuKodate）であり、正しくパースされていること
    assert isinstance(item, SumifuKodate)
    assert item.price == 45000000
    assert "横浜市青葉区" in item.address
    assert "[PropertyTypeSwitch]" in caplog.text
    assert "detected 'kodate'" in caplog.text


@pytest.mark.asyncio
async def test_base_parser_switches_mansion_to_investment(caplog):
    """MansionParser が詳細ページ到着時に利回り・投資用シグナルを検知し、InvestmentParserに自己切り替えすることを検証"""
    url = "https://www.stepon.co.jp/mansion/detail_99999/"
    invest_html = """
    <html>
    <head><title>【住友不動産ステップ】世田谷区 収益一棟アパート</title></head>
    <body>
        <h1>世田谷区桜 投資用一棟売りアパート</h1>
        <div class="c_price_wrap">8,500万円</div>
        <table class="table-row">
            <tr><th>物件種別</th><td>一棟売りアパート</td></tr>
            <tr><th>価格</th><td>8,500万円</td></tr>
            <tr><th>所在地</th><td>東京都世田谷区桜</td></tr>
            <tr><th>表面利回り</th><td>7.2%</td></tr>
            <tr><th>年間予定賃料</th><td>612万円</td></tr>
            <tr><th>構造</th><td>木造</td></tr>
            <tr><th>総戸数</th><td>6戸</td></tr>
        </table>
    </body>
    </html>
    """.encode("utf-8")

    parser = SumifuMansionParser()
    session = AsyncMock()
    with patch.object(parser, "_getContent", return_value=invest_html):
        with caplog.at_level("INFO"):
            item = await parser.parsePropertyDetailPage(session, url)

    assert isinstance(item, SumifuInvestmentApartment)
    assert item.price == 85000000
    assert float(item.grossYield) == 7.2
    assert "[PropertyTypeSwitch]" in caplog.text
    assert "detected 'apartment'" in caplog.text


@pytest.mark.asyncio
async def test_base_parser_keeps_same_parser_when_type_matches(caplog):
    """MansionParser が詳細ページ到着時にマンションHTMLである場合、パーサー切り替えを行わずそのまま実行することを検証"""
    url = "https://www.stepon.co.jp/mansion/detail_55555/"
    mansion_html = """
    <html>
    <head><title>【住友不動産ステップ】港区高輪の中古マンション</title></head>
    <body>
        <h1>高輪タワーレジデンス 10階</h1>
        <div class="c_price_wrap">9,800万円</div>
        <table class="table-row">
            <tr><th>物件種別</th><td>中古マンション</td></tr>
            <tr><th>価格</th><td>9,800万円</td></tr>
            <tr><th>所在地</th><td>東京都港区高輪</td></tr>
            <tr><th>専有面積</th><td>65.4㎡</td></tr>
            <tr><th>間取り</th><td>2LDK</td></tr>
            <tr><th>築年月</th><td>2020年1月</td></tr>
            <tr><th>構造</th><td>RC</td></tr>
        </table>
    </body>
    </html>
    """.encode("utf-8")

    parser = SumifuMansionParser()
    session = AsyncMock()
    with patch.object(parser, "_getContent", return_value=mansion_html):
        with caplog.at_level("INFO"):
            item = await parser.parsePropertyDetailPage(session, url)

    assert isinstance(item, SumifuMansion)
    assert item.price == 98000000
    assert "[PropertyTypeSwitch]" not in caplog.text

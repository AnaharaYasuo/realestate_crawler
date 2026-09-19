# -*- coding: utf-8 -*-
import datetime
from decimal import Decimal
import inspect
from bs4 import BeautifulSoup
import pytest

from package.parser.baseParser import InvestmentParserBase
from package.utils.url_router import UrlRouter


SAMPLE_KENBIYA_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <title>世田谷区 5,980万円 5.67％ 一棟アパート（No.4721854dw3）｜健美家</title>
</head>
<body>
    <dl>
        <dt>価格</dt><dd>5,980万円</dd>
        <dt>満室時利回り</dt><dd>5.67％利回りの詳細を問い合わせる</dd>
        <dt>交通</dt><dd>東急世田谷線 宮の坂駅 徒歩12分小田急小田原線 経堂駅 徒歩13分</dd>
        <dt>満室時年収/月収</dt><dd>339.6万円 / 28.3万円情報の見方</dd>
        <dt>住所</dt><dd>東京都世田谷区桜2-7地図</dd>
        <dt>物件名</dt><dd>世田谷区桜2丁目アパート</dd>
        <dt>築年月</dt><dd>1990年6月（築36年）</dd>
        <dt>土地権利</dt><dd>所有権</dd>
        <dt>建物構造</dt><dd>木造2階建 総戸数4戸</dd>
        <dt>土地面積</dt><dd>91.56m²【27.69坪】</dd>
        <dt>建物面積</dt><dd>99.02m²</dd>
        <dt>用途地域</dt><dd>第一種低住専</dd>
        <dt>間取り</dt><dd>2DK×1戸  1R×1戸  1DK×2戸住戸の専有面積：23m²～27m²</dd>
        <dt>建ぺい/容積率</dt><dd>60 ％ / 150 ％</dd>
        <dt>接道状況</dt><dd>北東側約4m</dd>
        <dt>引渡</dt><dd>相談</dd>
        <dt>現況</dt><dd>賃貸中入居状況を問い合わせる</dd>
    </dl>
</body>
</html>
"""


def test_kenbiya_parser_inherits_investment_base():
    from package.parser.kenbiyaParser import KenbiyaInvestmentApartmentParser

    assert issubclass(KenbiyaInvestmentApartmentParser, InvestmentParserBase)
    # Ensure all abstract methods are implemented
    assert not inspect.isabstract(KenbiyaInvestmentApartmentParser)


def test_kenbiya_parser_html_extraction():
    from package.parser.kenbiyaParser import KenbiyaInvestmentApartmentParser

    parser = KenbiyaInvestmentApartmentParser()
    soup = BeautifulSoup(SAMPLE_KENBIYA_HTML, "html.parser")
    item = parser.createEntity()
    item.pageUrl = "https://www.kenbiya.com/pp2/s/tokyo/setagaya-ku/re_4721854dw3/"

    parsed_item = parser._parsePropertyDetailPage(item, soup)
    parsed_item = parser.clean_parsed_item(parsed_item)

    assert parsed_item.price == 59800000
    assert parsed_item.priceStr == "5,980万円"
    assert parsed_item.grossYield == Decimal("5.67")
    assert parsed_item.annualRent == 3396000
    assert parsed_item.monthlyRent == 283000
    assert parsed_item.address == "東京都世田谷区桜2-7"
    assert parsed_item.propertyName == "世田谷区桜2丁目アパート"
    assert parsed_item.chikunengetsu == datetime.date(1990, 6, 1)
    assert parsed_item.kouzou == "木造2階建"
    assert parsed_item.soukosu == 4
    assert parsed_item.tochiMenseki == Decimal("91.56")
    assert parsed_item.tatemonoMenseki == Decimal("99.02")
    assert parsed_item.kenpei == Decimal("60.0")
    assert parsed_item.youseki == Decimal("150.0")
    assert parsed_item.setsudou == "北東側約4m"
    assert parsed_item.youtoChiiki == "第一種低住専"
    assert parsed_item.tochikenri == "所有権"
    assert parsed_item.currentStatus == "賃貸中"
    assert parsed_item.genkyo == "賃貸中"
    assert parsed_item.station1 == "宮の坂"
    assert parsed_item.walkMinutes1 == 12


def test_url_router_kenbiya_resolution():
    url = "https://www.kenbiya.com/pp2/s/tokyo/setagaya-ku/re_4721854dw3/"
    route = UrlRouter.resolve(url)

    assert route is not None
    assert route["site"] == "kenbiya"
    assert route["property_type"] == "apartment"
    assert route["parser_cls"] == "KenbiyaInvestmentApartmentParser"
    assert route["model_cls"] == "KenbiyaInvestmentApartment"

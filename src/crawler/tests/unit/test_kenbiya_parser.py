# -*- coding: utf-8 -*-
import datetime
from decimal import Decimal
import inspect
from bs4 import BeautifulSoup

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
    routes = [
        ("https://www.kenbiya.com/pp1/s/tokyo/adachi-ku/re_47223989xb/", "kenbiya", "mansion", "KenbiyaMansionParser", "KenbiyaMansion"),
        ("https://www.kenbiya.com/pp2/s/tokyo/setagaya-ku/re_4721854dw3/", "kenbiya", "apartment", "KenbiyaInvestmentApartmentParser", "KenbiyaInvestmentApartment"),
        ("https://www.kenbiya.com/pp3/s/tokyo/adachi-ku/re_4721852cvo/", "kenbiya", "apartment", "KenbiyaInvestmentBuildingParser", "KenbiyaInvestmentBuilding"),
        ("https://www.kenbiya.com/pp4/s/tokyo/adachi-ku/re_4720631znv/", "kenbiya", "apartment", "KenbiyaInvestmentBuildingParser", "KenbiyaInvestmentBuilding"),
        ("https://www.kenbiya.com/pp8/s/tokyo/adachi-ku/re_4720946geb/", "kenbiya", "kodate", "KenbiyaKodateParser", "KenbiyaKodate"),
        ("https://www.kenbiya.com/pp5/s/tokyo/adachi-ku/re_4718878jfv/", "kenbiya", "tochi", "KenbiyaTochiParser", "KenbiyaTochi"),
    ]
    for url, site, ptype, parser_name, model_name in routes:
        route = UrlRouter.resolve(url)
        assert route is not None, f"Failed to route {url}"
        assert route["site"] == site
        assert route["property_type"] == ptype
        assert route["parser_cls"] == parser_name
        assert route["model_cls"] == model_name


SAMPLE_KENBIYA_MANSION_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>足立区 700万円 区分マンション｜健美家</title></head>
<body>
    <dl>
        <dt>価格</dt><dd>700万円</dd>
        <dt>満室時利回り</dt><dd>9.42％利回りの詳細を問い合わせる</dd>
        <dt>交通</dt><dd>東京メトロ千代田線 北綾瀬駅 徒歩16分</dd>
        <dt>満室時年収/月収</dt><dd>66万円 / 5.5万円情報の見方</dd>
        <dt>住所</dt><dd>東京都足立区大谷田5丁目</dd>
        <dt>物件名</dt><dd>北綾瀬ダイヤモンドマンション 302号室</dd>
        <dt>築年月</dt><dd>1991年7月（築35年）</dd>
        <dt>建物構造/階数</dt><dd>RC造3階/5階建 総戸数30戸</dd>
        <dt>管理費/修繕積立</dt><dd>9,976円 / 9,786円</dd>
        <dt>専有面積</dt><dd>22.27m²（バルコニー 3.68m²）</dd>
        <dt>間取り</dt><dd>1R 東向き</dd>
        <dt>現況</dt><dd>賃貸中</dd>
        <dt>土地権利</dt><dd>所有権</dd>
    </dl>
</body>
</html>
"""

def test_kenbiya_mansion_parser():
    from package.parser.kenbiyaParser import KenbiyaMansionParser
    from package.parser.baseParser import MansionParserBase

    assert issubclass(KenbiyaMansionParser, MansionParserBase)
    assert not inspect.isabstract(KenbiyaMansionParser)

    parser = KenbiyaMansionParser()
    soup = BeautifulSoup(SAMPLE_KENBIYA_MANSION_HTML, "html.parser")
    item = parser.createEntity()
    parsed_item = parser._parsePropertyDetailPage(item, soup)
    parsed_item = parser.clean_parsed_item(parsed_item)

    assert parsed_item.price == 7000000
    assert parsed_item.priceStr == "700万円"
    assert parsed_item.grossYield == Decimal("9.42")
    assert parsed_item.annualRent == 660000
    assert parsed_item.monthlyRent == 55000
    assert parsed_item.address == "東京都足立区大谷田5丁目"
    assert parsed_item.propertyName == "北綾瀬ダイヤモンドマンション 302号室"
    assert parsed_item.chikunengetsu == datetime.date(1991, 7, 1)
    assert parsed_item.senyuMenseki == Decimal("22.27")
    assert parsed_item.balconyMenseki == Decimal("3.68")
    assert parsed_item.madori == "1R"
    assert parsed_item.direction == "東"
    assert parsed_item.floor == 3
    assert parsed_item.totalFloor == 5
    assert parsed_item.soukosu == 30
    assert parsed_item.kanrihi == 9976
    assert parsed_item.shuzenTsumitate == 9786
    assert parsed_item.currentStatus == "賃貸中"


SAMPLE_KENBIYA_KODATE_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>足立区 7699万円 戸建賃貸｜健美家</title></head>
<body>
    <dl>
        <dt>価格</dt><dd>7,699万円</dd>
        <dt>交通</dt><dd>つくばエクスプレス 六町駅 徒歩9分</dd>
        <dt>住所</dt><dd>東京都足立区南花畑1丁目</dd>
        <dt>物件名</dt><dd>足立区南花畑1丁目 新築一戸建て</dd>
        <dt>築年月</dt><dd>2027年1月（新築）</dd>
        <dt>土地権利</dt><dd>所有権</dd>
        <dt>建物構造</dt><dd>木造3階建 総戸数1戸</dd>
        <dt>土地面積</dt><dd>65.94m²【19.94坪】</dd>
        <dt>建物面積</dt><dd>125.85m²</dd>
        <dt>建ぺい/容積率</dt><dd>60 ％ / 200 ％</dd>
        <dt>用途地域</dt><dd>準工業</dd>
        <dt>接道状況</dt><dd>一方</dd>
        <dt>地目</dt><dd>宅地</dd>
        <dt>現況</dt><dd>未完成</dd>
    </dl>
</body>
</html>
"""

def test_kenbiya_kodate_parser():
    from package.parser.kenbiyaParser import KenbiyaKodateParser
    from package.parser.baseParser import KodateParserBase

    assert issubclass(KenbiyaKodateParser, KodateParserBase)
    assert not inspect.isabstract(KenbiyaKodateParser)

    parser = KenbiyaKodateParser()
    soup = BeautifulSoup(SAMPLE_KENBIYA_KODATE_HTML, "html.parser")
    item = parser.createEntity()
    parsed_item = parser._parsePropertyDetailPage(item, soup)
    parsed_item = parser.clean_parsed_item(parsed_item)

    assert parsed_item.price == 76990000
    assert parsed_item.priceStr == "7,699万円"
    assert parsed_item.address == "東京都足立区南花畑1丁目"
    assert parsed_item.propertyName == "足立区南花畑1丁目 新築一戸建て"
    assert parsed_item.chikunengetsu == datetime.date(2027, 1, 1)
    assert parsed_item.tochiMenseki == Decimal("65.94")
    assert parsed_item.tatemonoMenseki == Decimal("125.85")
    assert parsed_item.kenpei == Decimal("60.0")
    assert parsed_item.youseki == Decimal("200.0")
    assert parsed_item.setsudou == "一方"
    assert parsed_item.youtoChiiki == "準工業"
    assert parsed_item.chimoku == "宅地"
    assert parsed_item.currentStatus == "未完成"


SAMPLE_KENBIYA_TOCHI_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>足立区 6790万円 投資用土地・事業用地｜健美家</title></head>
<body>
    <dl>
        <dt>価格</dt><dd>6,790万円</dd>
        <dt>物件名</dt><dd>足立区竹の塚3丁目 土地</dd>
        <dt>交通</dt><dd>東武伊勢崎線 西新井駅 徒歩24分</dd>
        <dt>住所</dt><dd>東京都足立区竹の塚3丁目</dd>
        <dt>土地面積</dt><dd>115.75m²【35.01坪】</dd>
        <dt>建ぺい/容積率</dt><dd>60 ％ / 300 ％</dd>
        <dt>用途地域</dt><dd>第一種住居</dd>
        <dt>地目</dt><dd>宅地</dd>
        <dt>接道状況</dt><dd>一方</dd>
        <dt>土地権利</dt><dd>所有権</dd>
        <dt>現況</dt><dd>更地</dd>
    </dl>
</body>
</html>
"""

def test_kenbiya_tochi_parser():
    from package.parser.kenbiyaParser import KenbiyaTochiParser
    from package.parser.baseParser import TochiParserBase

    assert issubclass(KenbiyaTochiParser, TochiParserBase)
    assert not inspect.isabstract(KenbiyaTochiParser)

    parser = KenbiyaTochiParser()
    soup = BeautifulSoup(SAMPLE_KENBIYA_TOCHI_HTML, "html.parser")
    item = parser.createEntity()
    parsed_item = parser._parsePropertyDetailPage(item, soup)
    parsed_item = parser.clean_parsed_item(parsed_item)

    assert parsed_item.price == 67900000
    assert parsed_item.priceStr == "6,790万円"
    assert parsed_item.address == "東京都足立区竹の塚3丁目"
    assert parsed_item.propertyName == "足立区竹の塚3丁目 土地"
    assert parsed_item.tochiMenseki == Decimal("115.75")
    assert parsed_item.kenpei == Decimal("60.0")
    assert parsed_item.youseki == Decimal("300.0")
    assert parsed_item.setsudou == "一方"
    assert parsed_item.youtoChiiki == "第一種住居"
    assert parsed_item.chimoku == "宅地"
    assert parsed_item.tochikenri == "所有権"
    assert parsed_item.currentStatus == "更地"


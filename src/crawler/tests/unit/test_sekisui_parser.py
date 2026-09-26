import datetime
import ssl
from bs4 import BeautifulSoup
from package.parser.sekisuiParser import SekisuiMansionParser, SekisuiKodateParser
from package.models.sekisui import SekisuiMansion, SekisuiKodate
from package.utils import converter



def test_sekisui_mansion_parser():
    parser = SekisuiMansionParser()
    item = parser.createEntity()
    assert isinstance(item, SekisuiMansion)


def test_sekisui_kodate_parser():
    parser = SekisuiKodateParser()
    item = parser.createEntity()
    assert isinstance(item, SekisuiKodate)


def test_api_proc_base_connector_disables_tls_tickets():
    """Akamai CDN blocks requests with TLS session tickets; verify OP_NO_TICKET is set."""
    from package.api.sekisui import ParseSekisuiMansionStartAsync

    proc = ParseSekisuiMansionStartAsync()
    loop = proc._getActiveEventLoop()
    connector = proc._generateConnector(loop)
    try:
        assert connector._ssl.options & ssl.OP_NO_TICKET, "ssl.OP_NO_TICKET must be set in _generateConnector to prevent Akamai 403"
    finally:
        loop.run_until_complete(connector.close())




def test_converter_parse_chikunengetsu_wareki_and_seireki():
    """Verify parse_chikunengetsu handles both western calendar and Japanese wareki eras."""
    assert converter.parse_chikunengetsu("2020年3月") == datetime.date(2020, 3, 1)
    assert converter.parse_chikunengetsu("1998年11月") == datetime.date(1998, 11, 1)
    assert converter.parse_chikunengetsu("昭和54年12月") == datetime.date(1979, 12, 1)
    assert converter.parse_chikunengetsu("平成10年3月") == datetime.date(1998, 3, 1)
    assert converter.parse_chikunengetsu("令和2年5月") == datetime.date(2020, 5, 1)
    assert converter.parse_chikunengetsu("令和元年5月") == datetime.date(2019, 5, 1)
    assert converter.parse_chikunengetsu("令和元年") == datetime.date(2019, 5, 1)
    assert converter.parse_chikunengetsu("昭和元年") == datetime.date(1926, 12, 1)
    assert converter.parse_chikunengetsu("平成元年") == datetime.date(1989, 1, 1)
    assert converter.parse_chikunengetsu("不詳") is None
    assert converter.parse_chikunengetsu("-") is None
    assert converter.parse_chikunengetsu(None) is None
    assert converter.parse_chikunengetsu("令和元年1月") is None
    assert converter.parse_chikunengetsu("昭和元年1月") is None
    assert converter.parse_chikunengetsu("平成31年5月") is None
    assert converter.parse_chikunengetsu("昭和65年1月") is None


def test_sekisui_mansion_chikunengetsu_and_floors_parsing():
    """Verify SekisuiMansionParser extracts chikunengetsu and building floor types from specs."""
    parser = SekisuiMansionParser()
    html = """
    <html><body>
    <dl><dt>完成時期（築年月）</dt><dd>昭和54年12月</dd></dl>
    <dl><dt>構造・階数</dt><dd>SRC11階建て</dd></dl>
    <dl><dt>所在階</dt><dd>6階</dd></dl>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    specs = parser._get_specs(soup)

    chikunengetsu = parser._parseChikunengetsu(soup, specs)
    assert chikunengetsu == datetime.date(1979, 12, 1)

    chijo = parser._parseFloorTypeChijo(soup, specs)
    chika = parser._parseFloorTypeChika(soup, specs)
    kai = parser._parseFloorTypeKai(soup, specs)
    assert chijo == 11
    assert chika == 0
    assert kai == 6

    # When property has basement floors
    soup_with_basement = BeautifulSoup(
        "<dl><dt>構造・階数</dt><dd>RC造地上14階地下2階建</dd></dl>", "html.parser"
    )
    specs_with_basement = parser._get_specs(soup_with_basement)
    assert parser._parseFloorTypeChijo(soup_with_basement, specs_with_basement) == 14
    assert parser._parseFloorTypeChika(soup_with_basement, specs_with_basement) == 2

    # When structure field has only material but 階数 has floor count
    soup_split_floors = BeautifulSoup(
        "<dl><dt>構造・階数</dt><dd>SRC造</dd><dt>階数</dt><dd>10階建</dd></dl>", "html.parser"
    )
    specs_split_floors = parser._get_specs(soup_split_floors)
    assert parser._parseFloorTypeChijo(soup_split_floors, specs_split_floors) == 10
    assert parser._parseFloorTypeChika(soup_split_floors, specs_split_floors) == 0

    # When structure has no floor numbers, chika and chijo should return None
    soup_no_floors = BeautifulSoup("<dl><dt>構造・階数</dt><dd>SRC造</dd></dl>", "html.parser")
    specs_no_floors = parser._get_specs(soup_no_floors)
    assert parser._parseFloorTypeChijo(soup_no_floors, specs_no_floors) is None
    assert parser._parseFloorTypeChika(soup_no_floors, specs_no_floors) is None

    # When 所在階 is missing, floorType_kai should not fall back to total floors
    soup_no_kai = BeautifulSoup("<dl><dt>階数</dt><dd>11階</dd></dl>", "html.parser")
    specs_no_kai = parser._get_specs(soup_no_kai)
    assert parser._parseFloorTypeKai(soup_no_kai, specs_no_kai) is None


def test_sekisui_mansion_model_validation_allows_blank_optional_fields():
    """Verify SekisuiMansion allows blank/None for optional numeric and date fields."""
    mansion = SekisuiMansion(
        pageUrl="https://sumusite.sekisuihouse.co.jp/kanto/mansion/detail/TEST001/",
        propertyName="テストマンション",
        priceStr="1000万円",
        price=10000000,
        address="東京都品川区",
        chikunengetsu=None,
        floorType_chijo=None,
        floorType_chika=None,
        floorType_kai=None,
    )
    # full_clean should succeed without ValidationError
    mansion.full_clean()


def test_sekisui_mansion_parse_and_save_persists_extracted_values():
    """Verify end-to-end parsing from fixture HTML into SekisuiMansion and database round-trip."""
    parser = SekisuiMansionParser()
    html = """
    <html><body>
    <h1>グランドメゾン品川テスト</h1>
    <div class="property-detail">
        <dl><dt>物件名</dt><dd>グランドメゾン品川テスト</dd></dl>
        <dl><dt>価格</dt><dd>5,980万円</dd></dl>
        <dl><dt>所在地</dt><dd>東京都品川区東品川1丁目</dd></dl>
        <dl><dt>専有面積</dt><dd>70.50㎡</dd></dl>
        <dl><dt>間取り</dt><dd>3LDK</dd></dl>
        <dl><dt>完成時期（築年月）</dt><dd>昭和54年12月</dd></dl>
        <dl><dt>構造・階数</dt><dd>SRC11階建て</dd></dl>
        <dl><dt>所在階</dt><dd>6階</dd></dl>
    </div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    item = parser.createEntity()
    item.pageUrl = "https://sumusite.sekisuihouse.co.jp/kanto/mansion/detail/TEST_PERSIST_001/"
    item = parser._parsePropertyDetailPage(item, soup)
    item.full_clean()
    item.save()

    reloaded = SekisuiMansion.objects.get(pageUrl="https://sumusite.sekisuihouse.co.jp/kanto/mansion/detail/TEST_PERSIST_001/")
    assert reloaded.chikunengetsu == datetime.date(1979, 12, 1)
    assert reloaded.floorType_chijo == 11
    assert reloaded.floorType_chika == 0
    assert reloaded.floorType_kai == 6
    reloaded.delete()


# -*- coding: utf-8 -*-
"""
パーサー項目別 Getter メソッドおよび表示バリエーション吸収 TDD 単体テスト (Issue #564)
"""
from decimal import Decimal
from bs4 import BeautifulSoup

from package.parser.baseParser import (
    ParserBase,
    MansionParserBase,
    KodateParserBase,
    TochiParserBase,
    InvestmentParserBase,
)


class DummyParser(ParserBase):
    def getCharset(self):
        return "utf-8"

    def createEntity(self):
        return None

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        return item

    def _parsePrice(self, response: BeautifulSoup, specs=None):
        return super()._parsePrice(response, specs)

    def _parsePriceStr(self, response: BeautifulSoup, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parseAddress(self, response: BeautifulSoup, specs=None):
        return super()._parseAddress(response, specs)

    def _parsePropertyName(self, response: BeautifulSoup, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseTransport1(self, response: BeautifulSoup, specs=None):
        return super()._parseTransport1(response, specs)


class DummyMansionParser(MansionParserBase):
    def getCharset(self):
        return "utf-8"

    def createEntity(self):
        return None

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        return item

    def _parsePrice(self, response: BeautifulSoup, specs=None):
        return super()._parsePrice(response, specs)

    def _parsePriceStr(self, response: BeautifulSoup, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parseAddress(self, response: BeautifulSoup, specs=None):
        return super()._parseAddress(response, specs)

    def _parsePropertyName(self, response: BeautifulSoup, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseTransport1(self, response: BeautifulSoup, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseSenyuMenseki(self, response: BeautifulSoup, specs=None):
        return super()._parseSenyuMenseki(response, specs)

    def _parseMadori(self, response: BeautifulSoup, specs=None):
        return super()._parseMadori(response, specs)

    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response: BeautifulSoup, specs=None):
        return super()._parseKouzou(response, specs)

    def _parseFloor(self, response: BeautifulSoup, specs=None):
        return super()._parseFloor(response, specs)

    def _parseSouKosu(self, response: BeautifulSoup, specs=None):
        return super()._parseSouKosu(response, specs)

    def _parseManagementFee(self, response: BeautifulSoup, specs=None):
        return super()._parseManagementFee(response, specs)

    def _parseReserveFund(self, response: BeautifulSoup, specs=None):
        return super()._parseReserveFund(response, specs)

    def _parseKenpei(self, response: BeautifulSoup, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseYouseki(self, response: BeautifulSoup, specs=None):
        return super()._parseYouseki(response, specs)

    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseGenkyo(self, response: BeautifulSoup, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None):
        return super()._parseCurrentStatus(response, specs)

    def _parseRights(self, response: BeautifulSoup, specs=None):
        return super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None):
        return super()._parseYoutoChiiki(response, specs)


class DummyTochiParser(TochiParserBase):
    def getCharset(self):
        return "utf-8"

    def createEntity(self):
        return None

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        return item

    def _parsePrice(self, response: BeautifulSoup, specs=None):
        return super()._parsePrice(response, specs)

    def _parsePriceStr(self, response: BeautifulSoup, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parseAddress(self, response: BeautifulSoup, specs=None):
        return super()._parseAddress(response, specs)

    def _parsePropertyName(self, response: BeautifulSoup, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseTransport1(self, response: BeautifulSoup, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseKenpei(self, response: BeautifulSoup, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseYouseki(self, response: BeautifulSoup, specs=None):
        return super()._parseYouseki(response, specs)

    def _parseChimoku(self, response: BeautifulSoup, specs=None):
        return super()._parseChimoku(response, specs)

    def _parseSetsudou(self, response: BeautifulSoup, specs=None):
        return super()._parseSetsudou(response, specs)

    def _parseRights(self, response: BeautifulSoup, specs=None):
        return super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseMaguchi(self, response: BeautifulSoup, specs=None):
        return super()._parseMaguchi(response, specs)

    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseGenkyo(self, response: BeautifulSoup, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None):
        return super()._parseCurrentStatus(response, specs)


class DummyKodateParser(KodateParserBase):
    def getCharset(self):
        return "utf-8"

    def createEntity(self):
        return None

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        return item

    def _parsePrice(self, response: BeautifulSoup, specs=None):
        return super()._parsePrice(response, specs)

    def _parsePriceStr(self, response: BeautifulSoup, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parseAddress(self, response: BeautifulSoup, specs=None):
        return super()._parseAddress(response, specs)

    def _parsePropertyName(self, response: BeautifulSoup, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseTransport1(self, response: BeautifulSoup, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseMadori(self, response: BeautifulSoup, specs=None):
        return super()._parseMadori(response, specs)

    def _parseKouzou(self, response: BeautifulSoup, specs=None):
        return super()._parseKouzou(response, specs)

    def _parseKenpei(self, response: BeautifulSoup, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseYouseki(self, response: BeautifulSoup, specs=None):
        return super()._parseYouseki(response, specs)

    def _parseRights(self, response: BeautifulSoup, specs=None):
        return super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseSetsudou(self, response: BeautifulSoup, specs=None):
        return super()._parseSetsudou(response, specs)

    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseGenkyo(self, response: BeautifulSoup, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None):
        return super()._parseCurrentStatus(response, specs)


class DummyInvestmentParser(InvestmentParserBase):
    def getCharset(self):
        return "utf-8"

    def createEntity(self):
        return None

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        return item

    def _parsePrice(self, response: BeautifulSoup, specs=None):
        return super()._parsePrice(response, specs)

    def _parsePriceStr(self, response: BeautifulSoup, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parseAddress(self, response: BeautifulSoup, specs=None):
        return super()._parseAddress(response, specs)

    def _parsePropertyName(self, response: BeautifulSoup, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseTransport1(self, response: BeautifulSoup, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGrossYield(self, response: BeautifulSoup, specs=None):
        return super()._parseGrossYield(response, specs)

    def _parseAnnualRent(self, response: BeautifulSoup, specs=None):
        return super()._parseAnnualRent(response, specs)

    def _parseMonthlyRent(self, response: BeautifulSoup, specs=None):
        return super()._parseMonthlyRent(response, specs)

    def _parseGenkyo(self, response: BeautifulSoup, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None):
        return super()._parseCurrentStatus(response, specs)

    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response: BeautifulSoup, specs=None):
        return super()._parseKouzou(response, specs)

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseSetsudou(self, response: BeautifulSoup, specs=None):
        return super()._parseSetsudou(response, specs)

    def _parseChimoku(self, response: BeautifulSoup, specs=None):
        return super()._parseChimoku(response, specs)

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseRights(self, response: BeautifulSoup, specs=None):
        return super()._parseRights(response, specs)


class TestParserGettersBase:
    """ParserBase の汎用 Getter 群のテスト"""

    def test_get_price_from_specs_and_fallback(self):
        parser = DummyParser()
        html = """
        <html>
            <body>
                <table>
                    <tr><th>物件価格</th><td>3,580万円</td></tr>
                    <tr><th>所在地</th><td>東京都世田谷区桜丘1丁目</td></tr>
                </table>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert parser.get_price(soup) == 35800000
        assert parser.get_price_str(soup) == "3,580万円"
        assert parser.get_address(soup) == "東京都世田谷区桜丘1丁目"

    def test_get_price_str_rejects_label_text_761(self):
        parser = DummyParser()
        soup = BeautifulSoup('<html><body><span class="price">価格</span></body></html>', "html.parser")
        assert parser.get_price_str(soup) == ""
        assert not parser.get_price(soup)

    def test_get_setsudou_and_douro_breakdown(self):
        parser = DummyParser()
        html = """
        <html>
            <body>
                <table>
                    <tr><th>接道状況</th><td>北東側 6.0m 公道 接面 12.5m</td></tr>
                </table>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert parser.get_setsudou(soup) == "北東側 6.0m 公道 接面 12.5m"
        assert parser.get_douro_muki(soup) == "北東"
        assert parser.get_douro_kubun(soup) == "公道"
        assert parser.get_douro_haba(soup) == "6.0"

    def test_get_douro_direct_specs(self):
        parser = DummyParser()
        html = """
        <html>
            <body>
                <table>
                    <tr><th>道路の向き</th><td>南東</td></tr>
                    <tr><th>道路区分</th><td>私道</td></tr>
                    <tr><th>道路幅員</th><td>4.5m</td></tr>
                </table>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert parser.get_douro_muki(soup) == "南東"
        assert parser.get_douro_kubun(soup) == "私道"
        assert parser.get_douro_haba(soup) == "4.5"


class TestMansionParserGetters:
    """MansionParserBase の Getter テスト"""

    def test_mansion_getters(self):
        parser = DummyMansionParser()
        html = """
        <html>
            <body>
                <table>
                    <tr><th>専有面積</th><td>72.50㎡</td></tr>
                    <tr><th>間取り</th><td>3LDK</td></tr>
                    <tr><th>築年月</th><td>2018年3月</td></tr>
                    <tr><th>所在階</th><td>8階</td></tr>
                    <tr><th>総戸数</th><td>150戸</td></tr>
                    <tr><th>管理費</th><td>15,000円</td></tr>
                    <tr><th>修繕積立金</th><td>12,000円</td></tr>
                    <tr><th>バルコニー面積</th><td>10.2㎡</td></tr>
                </table>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert parser.get_senyu_menseki(soup) == Decimal("72.50")
        assert parser.get_madori(soup) == "3LDK"
        assert parser.get_floor(soup) == 8
        assert parser.get_kaisu_str(soup) == "8階"
        assert parser.get_soukosu(soup) == 150
        assert parser.get_management_fee(soup) == 15000
        assert parser.get_reserve_fund(soup) == 12000
        assert parser.get_balcony_menseki_str(soup) == "10.2㎡"


class TestTochiParserGetters:
    """TochiParserBase の Getter テスト"""

    def test_tochi_getters(self):
        parser = DummyTochiParser()
        html = """
        <html>
            <body>
                <table>
                    <tr><th>土地面積</th><td>120.45㎡</td></tr>
                    <tr><th>建ぺい率</th><td>60%</td></tr>
                    <tr><th>容積率</th><td>200%</td></tr>
                    <tr><th>地目</th><td>宅地</td></tr>
                    <tr><th>用途地域</th><td>第一種低層住居専用地域</td></tr>
                    <tr><th>間口</th><td>約8.5m</td></tr>
                </table>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert parser.get_tochi_menseki(soup) == Decimal("120.45")
        assert parser.get_kenpei(soup) == 60
        assert parser.get_youseki(soup) == 200
        assert parser.get_chimoku(soup) == "宅地"
        assert parser.get_youto_chiiki(soup) == "第一種低層住居専用地域"
        assert parser.get_maguchi(soup) == Decimal("8.5")


class TestKodateParserGetters:
    """KodateParserBase の Getter テスト"""

    def test_kodate_getters(self):
        parser = DummyKodateParser()
        html = """
        <html>
            <body>
                <table>
                    <tr><th>土地面積</th><td>105.20㎡</td></tr>
                    <tr><th>建物面積</th><td>98.50㎡</td></tr>
                    <tr><th>間取り</th><td>4LDK</td></tr>
                    <tr><th>構造</th><td>木造</td></tr>
                    <tr><th>建ぺい率</th><td>50%</td></tr>
                    <tr><th>容積率</th><td>100%</td></tr>
                    <tr><th>接道状況</th><td>南側 5.0m 公道</td></tr>
                    <tr><th>地目</th><td>宅地</td></tr>
                    <tr><th>用途地域</th><td>第一種低層住居専用地域</td></tr>
                </table>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert parser.get_tochi_menseki(soup) == Decimal("105.20")
        assert parser.get_tatemono_menseki(soup) == Decimal("98.50")
        assert parser.get_madori(soup) == "4LDK"
        assert parser.get_kouzou(soup) == "木造"
        assert parser.get_kenpei(soup) == 50
        assert parser.get_youseki(soup) == 100
        assert parser.get_setsudou(soup) == "南側 5.0m 公道"
        assert parser.get_chimoku(soup) == "宅地"
        assert parser.get_youto_chiiki(soup) == "第一種低層住居専用地域"


class TestInvestmentParserGetters:
    """InvestmentParserBase の Getter テスト"""

    def test_investment_getters(self):
        parser = DummyInvestmentParser()
        html = """
        <html>
            <body>
                <table>
                    <tr><th>表面利回り</th><td>7.5%</td></tr>
                    <tr><th>年間予定収入</th><td>360万円</td></tr>
                    <tr><th>稼働状況</th><td>満室賃貸中</td></tr>
                    <tr><th>構造</th><td>RC</td></tr>
                    <tr><th>建物面積</th><td>250.00㎡</td></tr>
                    <tr><th>土地面積</th><td>180.00㎡</td></tr>
                </table>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert parser.get_gross_yield(soup) == Decimal("7.5")
        assert parser.get_annual_rent(soup) == 3600000
        assert parser.get_genkyo(soup) == "満室賃貸中"
        assert parser.get_kouzou(soup) == "RC"
        assert parser.get_tatemono_menseki(soup) == Decimal("250.00")
        assert parser.get_tochi_menseki(soup) == Decimal("180.00")

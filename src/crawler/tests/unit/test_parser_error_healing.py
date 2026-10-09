import unittest
from bs4 import BeautifulSoup

from package.parser.tokyuParser import TokyuInvestmentApartmentParser
from package.parser.mitsuiParser import MitsuiInvestmentApartmentParser
from package.parser.athomeParser import AthomeTochiParser
from package.parser.baseParser import SkipPropertyException


class TestParserErrorHealing(unittest.TestCase):
    def test_tokyu_investment_without_yield_does_not_fail_strict_extraction(self):
        """Tokyu investment apartment without gross yield or rent should not trigger fatal validation error."""
        parser = TokyuInvestmentApartmentParser()
        html = """
        <html>
            <head><title>東急投資物件</title></head>
            <body>
                <div class="header"><h1>テスト物件</h1></div>
                <div id="propertySummarySection">
                    <dl>
                        <dt>価格</dt><dd>5,000万円</dd>
                        <dt>所在地</dt><dd>東京都渋谷区道玄坂1-1-1</dd>
                        <dt>建物構造</dt><dd>RC造</dd>
                        <dt>築年月</dt><dd>2010年5月</dd>
                    </dl>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        item = parser.createEntity()
        item.pageUrl = "https://www.livable.co.jp/toushi/detail/12345/"
        
        # Parse property detail page
        parsed_item = parser._parsePropertyDetailPage(item, soup)
        self.assertEqual(parsed_item.price, 50000000)
        self.assertEqual(parsed_item.address, "東京都渋谷区道玄坂1-1-1")
        
        # Clean parsed item should not raise exception or log fatal extraction errors
        cleaned = parser.clean_parsed_item(parsed_item)
        self.assertIsNotNone(cleaned)

    def test_mitsui_investment_land_url_skips(self):
        """Mitsui investment parser should raise SkipPropertyException on land (tochi) URLs or land shumoku."""
        parser = MitsuiInvestmentApartmentParser()
        html = """
        <html>
            <head><title>三井のリハウス 土地物件</title></head>
            <body>
                <table>
                    <tr><th>物件種別</th><td>土地</td></tr>
                    <tr><th>価格</th><td>3,000万円</td></tr>
                    <tr><th>所在地</th><td>東京都世田谷区</td></tr>
                </table>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        item = parser.createEntity()
        item.pageUrl = "https://www.rehouse.co.jp/buy/tochi/bkdetail/FQNAAA01/"

        with self.assertRaises(SkipPropertyException):
            parser._parsePropertyDetailPage(item, soup)

    def test_athome_tochi_parser_menseki_fallbacks(self):
        """AthomeTochiParser should support 区画面積 or 敷地面積 as fallback for tochiMenseki."""
        parser = AthomeTochiParser()
        html = """
        <html>
            <head><title>アットホーム 土地物件</title></head>
            <body>
                <table>
                    <tr><th>所在地</th><td>東京都練馬区</td></tr>
                    <tr><th>価格</th><td>4,500万円</td></tr>
                    <tr><th>区画面積</th><td>120.50m²</td></tr>
                    <tr><th>建ぺい率</th><td>60%</td></tr>
                    <tr><th>容積率</th><td>200%</td></tr>
                </table>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        item = parser.createEntity()
        item.pageUrl = "https://www.athome.co.jp/tochi/123456/"

        parsed_item = parser._parsePropertyDetailPage(item, soup)
        self.assertIsNotNone(parsed_item.tochiMenseki)
        self.assertEqual(float(parsed_item.tochiMenseki), 120.50)


if __name__ == "__main__":
    unittest.main()

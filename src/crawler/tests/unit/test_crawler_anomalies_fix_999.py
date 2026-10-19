import pytest
from decimal import Decimal
from bs4 import BeautifulSoup

from package.parser.baseParser import SkipPropertyException, ParserBase
from package.parser.athomeParser import (
    AthomeParser,
    AthomeKodateParser,
    AthomeMansionParser,
    AthomeInvestmentApartmentParser,
    AthomeTochiParser,
)
from package.parser.mitsuiParser import MitsuiParser, MitsuiMansionParser
from package.utils.data_validator import PropertyDataValidator


class TestCrawlerAnomaliesFix999:
    """Issue #999 回帰防止テストスイート"""

    def test_base_parser_rejects_non_property_urls(self):
        """三井のサポートページや一覧URLが即時スキップされること"""
        non_property_urls = [
            "https://www.rehouse.co.jp/support/mikata/",
            "https://www.rehouse.co.jp/support/guide/flow/",
            "https://www.rehouse.co.jp/column/tax-reform/",
            "https://www.athome.co.jp/mansion/chuko/tokyo/komae-city/list/",
            "https://www.rehouse.co.jp/manual/buying/",
        ]
        for url in non_property_urls:
            with pytest.raises(SkipPropertyException):
                ParserBase._reject_non_property_url(url)

    def test_athome_detail_path_rejects_list_urls(self):
        """アットホームで一覧URLが詳細パスと誤認されないこと"""
        parser = AthomeMansionParser()
        list_urls = [
            ("/mansion/chuko/tokyo/komae-city/list/", "https://www.athome.co.jp/mansion/chuko/tokyo/komae-city/list/"),
            ("/kodate/chuko/tokyo/setagaya-city/list", "https://www.athome.co.jp/kodate/chuko/tokyo/setagaya-city/list"),
            ("/buy_other/tokyo/list/", "https://www.athome.co.jp/buy_other/tokyo/list/"),
        ]
        for path, href in list_urls:
            assert parser._is_athome_detail_path(path, href) is False

        # 正常な詳細URLはTrue
        detail_path = "/mansion/chuko/tokyo/1234567890/"
        detail_href = "https://www.athome.co.jp/mansion/chuko/tokyo/1234567890/"
        assert parser._is_athome_detail_path(detail_path, detail_href) is True

    def test_athome_kodate_area_fallbacks(self):
        """アットホーム戸建てで「敷地面積」「延床面積」等の表記揺れを正しくパースできること"""
        parser = AthomeKodateParser()
        html = """
        <html>
        <body>
        <div id="detailTitleArea"><h1>テスト一戸建て</h1></div>
        <table>
            <tr><th>価格</th><td>4,500万円</td></tr>
            <tr><th>所在地</th><td>東京都世田谷区桜新町1丁目</td></tr>
            <tr><th>敷地面積</th><td>120.50㎡</td></tr>
            <tr><th>延床面積</th><td>95.30㎡</td></tr>
            <tr><th>間取り</th><td>3LDK</td></tr>
            <tr><th>築年月</th><td>2018年3月</td></tr>
            <tr><th>建物構造</th><td>木造</td></tr>
        </table>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        item = parser.createEntity()
        item.pageUrl = "https://www.athome.co.jp/kodate/chuko/tokyo/1234567890/"
        item = parser._parsePropertyDetailPage(item, soup)
        assert item.tochiMenseki == Decimal("120.50")
        assert item.tatemonoMenseki == Decimal("95.30")

    def test_athome_invest_apartment_area_fallbacks(self):
        """アットホーム一棟アパートで土地面積・延床面積から正しく抽出できること"""
        parser = AthomeInvestmentApartmentParser()
        html = """
        <html>
        <body>
        <div id="detailTitleArea"><h1>テスト一棟アパート</h1></div>
        <table>
            <tr><th>価格</th><td>8,000万円</td></tr>
            <tr><th>所在地</th><td>東京都中野区中央1丁目</td></tr>
            <tr><th>敷地面積</th><td>150.00㎡</td></tr>
            <tr><th>延床面積</th><td>220.00㎡</td></tr>
            <tr><th>利回り</th><td>6.5%</td></tr>
            <tr><th>想定年収</th><td>520万円</td></tr>
            <tr><th>建物構造</th><td>木造</td></tr>
        </table>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        item = parser.createEntity()
        item.pageUrl = "https://www.athome.co.jp/buy_other/1234567890/"
        item = parser._parsePropertyDetailPage(item, soup)
        assert item.tochiMenseki == Decimal("150.00")
        assert item.tatemonoMenseki == Decimal("220.00")

    def test_mitsui_traffic_line_splitting(self):
        """三井のリハウスで改行なしで連結された複数路線が分割されること"""
        parser = MitsuiMansionParser()
        raw_traffic = "JR山手線 新宿駅 徒歩5分 東京メトロ丸ノ内線 新宿三丁目駅 徒歩3分"
        lines = parser._split_single_transit_line(raw_traffic)
        assert len(lines) == 2
        assert "新宿駅" in lines[0]
        assert "新宿三丁目駅" in lines[1]

    def test_data_validator_area_selection_for_investment(self):
        """一棟アパートで専有面積が0または欠損でも建物面積/土地面積から妥当に判定されること"""
        class DummyApartment:
            propertyName = "テスト一棟アパート"
            address = "東京都新宿区"
            traffic = "新宿駅 徒歩5分"
            price = 60000000
            grossYield = 7.0
            annualRent = 4200000
            senyuMenseki = Decimal("0.0")  # 専有面積は0
            tatemonoMenseki = Decimal("180.0")  # 建物面積は正常
            tochiMenseki = Decimal("200.0")
            chikunengetsuStr = "2015年5月"

        is_valid, reasons = PropertyDataValidator.validate_property(DummyApartment(), "investment_apartment")
        # 面積異常（0.0㎡ / 5㎡以下）と判定されないこと
        area_errors = [r for r in reasons if "面積異常" in r]
        assert len(area_errors) == 0
        assert is_valid is True

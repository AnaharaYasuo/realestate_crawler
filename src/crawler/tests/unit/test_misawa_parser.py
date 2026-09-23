# -*- coding: utf-8 -*-
"""
ミサワホーム不動産 パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.misawaParser import (
    MisawaMansionParser,
    MisawaKodateParser,
    MisawaTochiParser,
    MisawaInvestmentKodateParser,
    MisawaInvestmentApartmentParser,
)
from package.models.misawa import (
    MisawaMansion,
    MisawaKodate,
    MisawaTochi,
    MisawaInvestmentKodate,
    MisawaInvestmentApartment,
)

class TestMisawaParser:

    def test_create_entity(self):
        parser = MisawaMansionParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MisawaMansion)

    def test_create_entity_kodate(self):
        parser = MisawaKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MisawaKodate)

    def test_create_entity_tochi(self):
        parser = MisawaTochiParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MisawaTochi)

    def test_create_entity_investment_apartment(self):
        parser = MisawaInvestmentApartmentParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MisawaInvestmentApartment)

    def test_create_entity_investment_kodate(self):
        parser = MisawaInvestmentKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MisawaInvestmentKodate)

    def test_parser_configuration(self):
        parser = MisawaMansionParser(None)
        assert parser.__class__.__name__ == "MisawaMansionParser"

    def test_investment_apartment_accepts_bukken_shubetsu(self):
        """Live pages label type as 物件種別 (not 物件種目); h1 is site branding."""
        from bs4 import BeautifulSoup
        from package.parser.baseParser import SkipPropertyException

        html = """
        <html><body>
          <h1>ミサワホーム不動産の不動産検索</h1>
          <h2 class="title">【アパート】テスト物件A</h2>
          <dl class="price"><dd>1,000万円</dd></dl>
          <div class="data"><dl><dt>所在地</dt><dd>東京都豊島区南長崎５丁目</dd>
          <dl><dt>dummy</dt><dd>x</dd></dl></div>
          <table class="outline">
            <tr><th>物件種別</th><td>アパート</td></tr>
            <tr><th>所在地</th><td>東京都豊島区南長崎５丁目</td></tr>
          </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        parser = MisawaInvestmentApartmentParser()
        item = parser.createEntity()
        item.pageUrl = "https://realestate.misawa.co.jp/search/sale/detail/1/"
        try:
            out = parser._parsePropertyDetailPage(item, soup)
        except SkipPropertyException as exc:
            raise AssertionError("apartment should accept 物件種別=アパート") from exc
        assert "テスト物件A" in (out.propertyName or "")
        assert "不動産検索" not in (out.propertyName or "")

    def test_investment_kodate_start_uses_kodate_parser(self):
        from package.api.misawa_investment import ParseMisawaInvestmentKodateStartAsync

        parser = ParseMisawaInvestmentKodateStartAsync()._generateParser()
        assert parser.__class__.__name__ == "MisawaInvestmentKodateParser"

# -*- coding: utf-8 -*-
import pytest
import bs4
from package.parser.mizuhoParser import (
    MizuhoMansionParser,
    MizuhoKodateParser,
    MizuhoTochiParser,
    MizuhoInvestmentParser,
)

class TestMizuhoListPriceExtraction:
    @pytest.fixture
    def mansion_parser(self):
        return MizuhoMansionParser()

    @pytest.fixture
    def kodate_parser(self):
        return MizuhoKodateParser()

    @pytest.fixture
    def tochi_parser(self):
        return MizuhoTochiParser()

    @pytest.fixture
    def investment_parser(self):
        return MizuhoInvestmentParser()

    def test_mizuho_mansion_distinct_prices(self, mansion_parser):
        html = '''
        <div class="propertyList">
            <div class="propertyCard">
                <a href="/buyers/property/1001/" class="title">物件A</a>
                <span class="price">5,000万円</span>
            </div>
            <div class="propertyCard">
                <a href="/buyers/property/1002/" class="title">物件B</a>
                <span class="price">7,500万円</span>
            </div>
        </div>
        '''
        soup = bs4.BeautifulSoup(html, "html.parser")
        items = mansion_parser._extract_static_detail_links(soup)
        assert len(items) == 2
        assert items[0].price == 50000000
        assert items[1].price == 75000000

    def test_mizuho_shared_container_does_not_leak_same_price(self, mansion_parser):
        # 共通コンテナ内に複数リンクが存在し、片方のみ価格がある場合や個別価格がない場合に全件同一価格にならないこと
        html = '''
        <div class="search-result-wrapper">
            <div class="filter-summary">検索条件: 6,000万円〜</div>
            <div class="card-item">
                <a href="/buyers/property/2001/">物件1</a>
                <div class="card-price">3,000万円</div>
            </div>
            <div class="card-item">
                <a href="/buyers/property/2002/">物件2</a>
                <!-- 個別価格なし -->
            </div>
        </div>
        '''
        soup = bs4.BeautifulSoup(html, "html.parser")
        items = mansion_parser._extract_static_detail_links(soup)
        assert len(items) == 2
        assert items[0].price == 30000000
        # フィルタサマリーの6,000万円が物件2に誤適用されないこと
        assert items[1].price is None

    def test_mizuho_all_types_support_isolated_card_price(
        self, mansion_parser, kodate_parser, tochi_parser, investment_parser
    ):
        for parser in [mansion_parser, kodate_parser, tochi_parser, investment_parser]:
            html = '''
            <div class="unit">
                <a href="/buyers/property/3001/">サンプル</a>
                <span class="price">4,200万円</span>
            </div>
            '''
            soup = bs4.BeautifulSoup(html, "html.parser")
            items = parser._extract_static_detail_links(soup)
            assert len(items) == 1
            assert items[0].price == 42000000
import asyncio
from decimal import Decimal
from bs4 import BeautifulSoup

from package.parser.smtrcParser import SmtrcInvestmentParser
from package.parser.totateParser import TotateMansionParser
from package.utils import converter


def test_parse_yen_with_date_and_notes():
    # 通常の円表記
    assert converter.parse_yen("15,760円") == 15760
    assert converter.parse_yen("15,760") == 15760

    # 日付注記つき年収
    assert converter.parse_yen("12,270,000円（2026年8月18日確認）") == 12270000
    assert converter.parse_yen("18,511,800円（2026年3月27日確認）") == 18511800
    assert converter.parse_rent("12,270,000円（2026年8月18日確認）") == 12270000
    assert converter.parse_rent("18,511,800円（2026年3月27日確認）") == 18511800


def test_smtrc_investment_parser_current_yield_and_rent():
    parser = SmtrcInvestmentParser()
    item = parser.createEntity()

    specs = {
        "現行利回り": "3.50%",
        "現行年間収入": "12,270,000円（2026年8月18日確認）",
    }
    parser._apply_invest_yield_and_rent(item, specs)

    assert item.grossYield == Decimal("3.50")
    assert item.annualRent == 12270000
    assert item.monthlyRent == 12270000 // 12


def test_totate_parse_next_page_data_href():
    parser = TotateMansionParser()
    html = """
    <div class="paging">
        <a data-href="P3BhZ2U9MiZzb3J0PW5ld19hcnJpdmFsJmxpbWl0PTIw" href="javascript:;">次の20件</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    next_url = asyncio.run(parser.parseNextPage(soup))
    assert next_url == "https://sumikae.ttfuhan.co.jp/buy/search/result/detail_search/mansion/kanto/?page=2&sort=new_arrival&limit=20"

import pytest
from bs4 import BeautifulSoup
from decimal import Decimal
from package.parser.tohoParser import TohoMansionParser, TohoKodateParser, TohoTochiParser

@pytest.mark.asyncio
async def test_toho_property_list_page_and_next_page():
    html = """
    <html>
      <body>
        <div class="property__item">
          <a href="/estate_list_fujisawa/estate_detail_61598_1475.html" class="c-property__link">
            <span class="price">5,499万円</span>
          </a>
        </div>
        <div class="property__pager">
          <div class="propertyPager__next">
            <a class="propertyPager__nextLink" href="/estates?div=1&page=2">次へ</a>
          </div>
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = TohoMansionParser()
    
    # 1. Test parsePropertyListPage
    items = [item async for item in parser.parsePropertyListPage(soup)]
    assert len(items) == 1
    assert items[0].url == "https://th-yokohama.com/estate_list_fujisawa/estate_detail_61598_1475.html"
    assert items[0].price == 54990000

    # 2. Test parseNextPage
    next_url = await parser.parseNextPage(soup)
    assert next_url == "https://th-yokohama.com/estates?div=1&page=2"

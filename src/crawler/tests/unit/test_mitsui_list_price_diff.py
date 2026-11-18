import pytest
from bs4 import BeautifulSoup
from package.api.differential import ListItem
from package.parser.mitsuiParser import MitsuiMansionParser


@pytest.mark.asyncio
async def test_mitsui_parse_property_list_extracts_price_into_list_item():
    html = """
    <html>
      <body>
        <div class="property-index-card">
          <a href="/buy/mansion/bkdetail/12345/">パークホームズ東京</a>
          <div class="price">5,980万円</div>
        </div>
        <div class="property-index-card">
          <a href="/buy/mansion/bkdetail/67890/">ザ・レジデンス新宿</a>
          <div class="price">1億2,500万円</div>
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiMansionParser()
    items = []
    async for item in parser.parsePropertyListPage(soup):
        items.append(item)

    assert len(items) == 2
    assert isinstance(items[0], ListItem)
    assert items[0].url.endswith("/buy/mansion/bkdetail/12345/")
    assert items[0].price == 59800000
    assert isinstance(items[1], ListItem)
    assert items[1].url.endswith("/buy/mansion/bkdetail/67890/")
    assert items[1].price == 125000000

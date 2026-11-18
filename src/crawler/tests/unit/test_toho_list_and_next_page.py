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


@pytest.mark.asyncio
async def test_toho_mansion_detail_floor_parsing():
    detail_html = """
    <html>
      <body>
        <h1>クリオ片瀬江ノ島</h1>
        <dl>
          <dt>物件種別</dt><dd>マンション</dd>
          <dt>交通</dt><dd>小田急江ノ島線 / 片瀬江ノ島駅 徒歩6分</dd>
          <dt>価格</dt><dd>3,480万円(税込)</dd>
          <dt>所在地</dt><dd>藤沢市片瀬海岸２丁目</dd>
          <dt>専有面積</dt><dd>34.24m²</dd>
          <dt>間取り</dt><dd>1DK</dd>
          <dt>所在階数</dt><dd>5階</dd>
          <dt>総階数</dt><dd>地上6階</dd>
          <dt>構造</dt><dd>RC造</dd>
          <dt>管理費</dt><dd>10,200円/月</dd>
          <dt>修繕積立金</dt><dd>9,450円/月</dd>
          <dt>築年月</dt><dd>令和 1年 11月</dd>
        </dl>
      </body>
    </html>
    """
    soup = BeautifulSoup(detail_html, "html.parser")
    parser = TohoMansionParser()
    entity = parser.createEntity()
    entity = parser._parsePropertyDetailPage(entity, soup)

    assert entity.propertyName == "クリオ片瀬江ノ島"
    assert entity.kaisu == "5階"
    assert entity.kouzou == "RC造"
    assert entity.price == 34800000
    assert entity.address == "藤沢市片瀬海岸２丁目"


@pytest.mark.asyncio
async def test_toho_mansion_unspecified_price_raises_listing_ended():
    from package.parser.baseParser import ListingEndedException
    sold_html = """
    <html>
      <body>
        <h1>最上階×南向き×フルリノベ</h1>
        <p class="estatesDtl__headingPrice">----万円2SLDK</p>
        <dl>
          <dt>価格</dt><dd>----</dd>
        </dl>
      </body>
    </html>
    """
    soup = BeautifulSoup(sold_html, "html.parser")
    parser = TohoMansionParser()
    entity = parser.createEntity()
    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(entity, soup)


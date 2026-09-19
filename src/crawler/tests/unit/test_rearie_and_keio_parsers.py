# -*- coding: utf-8 -*-
"""
Panasonic Homes (Rearie) & Keio Fudosan (Keio) パーサー仕様検証テスト (TDD)
"""
from decimal import Decimal
from bs4 import BeautifulSoup

from package.parser.rearieParser import RearieMansionParser
from package.parser.keioParser import KeioMansionParser


# --- Keio Tests ---
def test_keio_parse_root_page_with_api_html():
    html = """
    <div class="es_result_items">
      <div class="es_result_item">
        <a href="https://chukai.keiofudosan.co.jp/sale/2127977638870000006531/" class="abs_link">詳細</a>
      </div>
      <div class="es_result_item">
        <a href="/sale/2127977638870000006360/" class="abs_link">詳細</a>
      </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = KeioMansionParser()
    
    import asyncio
    async def collect():
        results = []
        async for link in parser.parseRootPage(soup):
            results.append(link)
        return results
        
    links = asyncio.run(collect())
    assert len(links) == 2
    assert "https://chukai.keiofudosan.co.jp/sale/2127977638870000006531" in links[0]
    assert "https://chukai.keiofudosan.co.jp/sale/2127977638870000006360" in links[1]


def test_keio_parse_next_page_with_pager():
    html = """
    <div class="block_pager">
      <a class="pager current" data-page="1" href="">1</a>
      <a class="pager" data-page="2" href="">2</a>
      <a class="pager" data-page="3" href="">3</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = KeioMansionParser()
    parser.current_page_num = 1
    parser.current_base_url = "https://chukai.keiofudosan.co.jp/wp-json/wp/v2/get_search_result_sale?rent_or_sale=sale&area_or_line=area&item_per_page=30&page_num=1&pref=13&boshu_kind_summary_code[]=1"
    
    import asyncio
    next_url = asyncio.run(parser.parseNextPage(soup))
    assert "page_num=2" in next_url


# --- Rearie Tests ---
def test_rearie_mansion_parse_from_json_dict():
    sample_data = {
        "id": 33753,
        "propName": "ザ・タワー・グランディア",
        "price": 18800,
        "address": "東京都豊島区西池袋５丁目5-21",
        "madori": "2LDK+WIC",
        "tateMenseki": "75.64㎡ (壁芯)",
        "baruMenseki": "22.50㎡",
        "tochiKenri": "所有権",
        "genkyou": "空家",
        "torihiki": "売主",
        "hikiwata": "相談",
        "kouzou": "RC造",
        "chiku": "2004年3月(築22年6ヶ月)",
        "kai": "10",
        "kaidate": 38,
        "kosuu": 358,
        "kanrihi": "19,390円/月",
        "tumikin": "21,370円/月",
        "moyori": ["山手線「池袋」駅 徒歩6分"],
    }
    parser = RearieMansionParser()
    entity = parser.createEntity()
    
    parsed = parser._parsePropertyDetailJson(entity, sample_data)
    cleaned = parser.clean_parsed_item(parsed)
    
    assert cleaned.propertyName == "ザ・タワー・グランディア"
    assert cleaned.price == 188000000
    assert cleaned.priceStr == "18,800万円"
    assert cleaned.address == "東京都豊島区西池袋５丁目5-21"
    assert cleaned.senyuMenseki == Decimal("75.64")
    assert cleaned.balconyMenseki == Decimal("22.50")
    assert cleaned.tochikenri == "所有権"
    assert cleaned.genkyo == "空家"
    assert cleaned.torihiki == "売主"
    assert cleaned.floorType_kai == 10
    assert cleaned.floorType_chijo == 38
    assert cleaned.soukosu == 358
    assert cleaned.railway1 == "山手線"
    assert cleaned.station1 == "池袋"
    assert cleaned.railwayWalkMinute1 == 6


def test_rearie_root_page_with_json_dict():
    sample_list_data = {
        "list": [
            {"id": 33753},
            {"id": 33531},
        ],
        "page": 1,
        "maxPage": 10,
    }
    parser = RearieMansionParser()
    
    import asyncio
    async def collect():
        results = []
        async for link in parser.parseRootPageJson(sample_list_data):
            results.append(link)
        return results
        
    links = asyncio.run(collect())
    assert len(links) == 2
    assert "id=33753" in links[0]
    assert "id=33531" in links[1]


def test_rearie_next_page_with_json_dict():
    sample_list_data = {
        "page": 1,
        "maxPage": 10,
    }
    parser = RearieMansionParser()
    
    import asyncio
    next_url = asyncio.run(parser.parseNextPageJson(sample_list_data))
    assert "page=2" in next_url

import base64
from unittest.mock import patch
import pytest
from bs4 import BeautifulSoup

import setup_env  # noqa: F401
from package.parser.keiseiParser import KeiseiMansionParser
from package.parser.totateParser import TotateMansionParser, TotateKodateParser
from package.parser.sumirinParser import SumirinMansionParser, SumirinKodateParser, SumirinTochiParser
from routes import keisei_routes, totate_routes, sumirin_routes


@pytest.mark.asyncio
async def test_keisei_parse_next_page_form_submit():
    parser = KeiseiMansionParser()
    html = '''
    <html>
    <body>
        <span class="list_next_button"><input type="button" value="前10件" onClick="form1_submit('1')"></span>
        <select name="offset" id="offset">
            <option value="1">1</option>
            <option value="2" selected>2</option>
            <option value="3">3</option>
        </select>
        <span class="list_next_button"><input type="button" value="次10件" onClick="form1_submit('3')"></span>
    </body>
    </html>
    '''
    soup = BeautifulSoup(html, "html.parser")
    current_url = "https://www.keisei-land.co.jp/contents/code/search_result?mode=list&all_pref=1&r_type=3&by=area&offset=2"
    next_url = await parser.parseNextPage(soup, current_url=current_url)
    assert "offset=3" in next_url
    assert "offset=1" not in next_url


@pytest.mark.asyncio
async def test_keisei_parse_next_page_select_fallback():
    parser = KeiseiMansionParser()
    html = '''
    <html>
    <body>
        <select name="offset" id="offset">
            <option value="1">1</option>
            <option value="2" selected>2</option>
            <option value="3">3</option>
        </select>
    </body>
    </html>
    '''
    soup = BeautifulSoup(html, "html.parser")
    current_url = "https://www.keisei-land.co.jp/contents/code/search_result?mode=list&all_pref=1&r_type=3&by=area&offset=2"
    next_url = await parser.parseNextPage(soup, current_url=current_url)
    assert "offset=3" in next_url


@pytest.mark.asyncio
async def test_keisei_parse_next_page_last_page():
    parser = KeiseiMansionParser()
    html = '''
    <html>
    <body>
        <span class="list_next_button"><input type="button" value="前10件" onClick="form1_submit('2')"></span>
        <select name="offset" id="offset">
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3" selected>3</option>
        </select>
    </body>
    </html>
    '''
    soup = BeautifulSoup(html, "html.parser")
    current_url = "https://www.keisei-land.co.jp/contents/code/search_result?mode=list&all_pref=1&r_type=3&by=area&offset=3"
    next_url = await parser.parseNextPage(soup, current_url=current_url)
    assert next_url == ""


def test_keisei_routes_all_pref_start_urls():
    with patch.object(keisei_routes.ParseKeiseiMansionStartAsync, "main", return_value="ok") as m_main, \
         patch.object(keisei_routes.ParseKeiseiKodateStartAsync, "main", return_value="ok") as k_main, \
         patch.object(keisei_routes.ParseKeiseiTochiStartAsync, "main", return_value="ok") as t_main:
        keisei_routes.keisei_mansion_start()
        keisei_routes.keisei_kodate_start()
        keisei_routes.keisei_tochi_start()

        assert m_main.call_args[0][0] == "https://www.keisei-land.co.jp/contents/code/search_result?mode=list&all_pref=1&r_type=3&by=area"
        assert k_main.call_args[0][0] == "https://www.keisei-land.co.jp/contents/code/search_result?mode=list&all_pref=1&r_type=2&by=area"
        assert t_main.call_args[0][0] == "https://www.keisei-land.co.jp/contents/code/search_result?mode=list&all_pref=1&r_type=1&by=area"
        assert "pl_13" not in k_main.call_args[0][0]
        assert "pl_13" not in t_main.call_args[0][0]


@pytest.mark.asyncio
async def test_totate_nationwide_start_url_and_next_page():
    for ptype in ("mansion", "kodate", "tochi"):
        start_url = totate_routes.get_start_url(ptype)
        assert f"/buy/search/result/detail_search/{ptype}/kanto/?limit=100" in start_url
        assert "city[]" not in start_url

    parser = TotateKodateParser()
    qs_b64 = base64.b64encode(b"?page=2&sort=new_arrival&limit=100").decode("ascii")
    html = f'''
    <html><body>
        <div class="paging">
            <a href="javascript:;" data-href="{qs_b64}">次の100件</a>
        </div>
    </body></html>
    '''
    soup = BeautifulSoup(html, "html.parser")
    next_url = await parser.parseNextPage(
        soup,
        current_url="https://sumikae.ttfuhan.co.jp/buy/search/result/detail_search/kodate/kanto/?limit=100",
    )
    assert next_url == "https://sumikae.ttfuhan.co.jp/buy/search/result/detail_search/kodate/kanto/?page=2&sort=new_arrival&limit=100"


@pytest.mark.asyncio
async def test_sumirin_nationwide_searchlist_routes_and_pagination():
    with patch.object(sumirin_routes.ParseSumirinMansionStartAsync, "main", return_value="ok") as m_main, \
         patch.object(sumirin_routes.ParseSumirinKodateStartAsync, "main", return_value="ok") as k_main, \
         patch.object(sumirin_routes.ParseSumirinTochiStartAsync, "main", return_value="ok") as t_main:
        sumirin_routes.sumirin_mansion_start()
        sumirin_routes.sumirin_kodate_start()
        sumirin_routes.sumirin_tochi_start()

        assert m_main.call_args[0][0] == "https://www.suminavi.com/buy/estate/searchList?r_seq=9&ec_cd=1&ed_cd=01&s_mode=3&f_word=&p_num=100"
        assert k_main.call_args[0][0] == "https://www.suminavi.com/buy/estate/searchList?r_seq=9&ec_cd=1&ed_cd=02&s_mode=3&f_word=&p_num=100"
        assert t_main.call_args[0][0] == "https://www.suminavi.com/buy/estate/searchList?r_seq=9&ec_cd=1&ed_cd=03&s_mode=3&f_word=&p_num=100"

    parser = SumirinKodateParser()
    html = '''
    <html><body>
        <a href="/buy/estate/estateInfo/house/shutoken/631287/?rs_flg=1">House 1</a>
        <a href="/buy/estate/estateInfo/house/kansai/635615/?rs_flg=1">House 2</a>
        <ul class="pager">
            <li class="next"><a href="https://www.suminavi.com/buy/estate/searchList?r_seq=9&ec_cd=1&ed_cd=02&s_mode=3&f_word=&p_num=100&s=21&p=2">＞</a></li>
        </ul>
    </body></html>
    '''
    soup = BeautifulSoup(html, "html.parser")
    items = [it async for it in parser.parseRootPage(soup)]
    assert len(items) == 2
    assert items[0].url == "https://www.suminavi.com/buy/estate/estateInfo/house/shutoken/631287/"
    next_url = await parser.parseNextPage(soup)
    assert next_url == "https://www.suminavi.com/buy/estate/searchList?r_seq=9&ec_cd=1&ed_cd=02&s_mode=3&f_word=&p_num=100&s=21&p=2"

# -*- coding: utf-8 -*-
"""Issue #317: クローリング0件取得失敗修復の回帰テスト"""
from bs4 import BeautifulSoup

from package.utils.url_matcher import UrlMatcher
from package.utils.url_router import UrlRouter
from package.api.nomura_investment import ParseNomuraInvestKodateListFuncAsync
from package.api.tokyu_investment import ParseTokyuInvestKodateListFuncAsync
from package.api.tokyu import (
    ParseTokyuKodateStartAsync,
    ParseTokyuKodateAreaFuncAsync,
    ParseTokyuKodateListFuncAsync,
    ParseTokyuTochiStartAsync,
    ParseTokyuTochiAreaFuncAsync,
    ParseTokyuTochiListFuncAsync,
)
from package.parser.odakyuParser import OdakyuInvestmentParser
from package.parser.daikyoParser import DaikyoMansionParser


def test_rearie_url_matcher_preserves_id():
    """Rearieの ?id= パラメータがUrlMatcher.normalizeで保持され、異なる物件でURLが衝突しないことを検証"""
    url1 = "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=1001&utm_source=line#tab1"
    url2 = "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=1002&utm_source=twitter"

    norm1 = UrlMatcher.normalize(url1)
    norm2 = UrlMatcher.normalize(url2)

    assert norm1 == "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=1001"
    assert norm2 == "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=1002"
    assert norm1 != norm2
    assert UrlMatcher.is_same_url(norm1, norm2) is False


def test_nomura_and_tokyu_investment_parallel_limit_defined():
    """nomuraとtokyuの投資用APIクラスでDEFAULT_PARARELL_LIMIT NameErrorが発生しないことを検証"""
    nomura_obj = ParseNomuraInvestKodateListFuncAsync()
    assert nomura_obj._getCloudPararellLimit() >= 1

    tokyu_obj = ParseTokyuInvestKodateListFuncAsync()
    assert tokyu_obj._getCloudPararellLimit() >= 1


def test_tokyu_api_keys_and_bs_flag():
    """tokyu kodate/tochi の各ステージAPIキーと _isBsMiddlePage フラグを検証"""
    k_start = ParseTokyuKodateStartAsync()
    assert k_start._isBsMiddlePage() is False
    assert "/api/tokyu/kodate/area" in k_start._getApiKey()

    k_area = ParseTokyuKodateAreaFuncAsync()
    assert k_area._isBsMiddlePage() is False
    assert "/api/tokyu/kodate/list" in k_area._getApiKey()

    k_list = ParseTokyuKodateListFuncAsync()
    assert k_list._isBsMiddlePage() is False
    assert "/api/tokyu/kodate/detail" in k_list._getApiKey()

    t_start = ParseTokyuTochiStartAsync()
    assert t_start._isBsMiddlePage() is False
    assert "/api/tokyu/tochi/area" in t_start._getApiKey()

    t_area = ParseTokyuTochiAreaFuncAsync()
    assert t_area._isBsMiddlePage() is False
    assert "/api/tokyu/tochi/list" in t_area._getApiKey()

    t_list = ParseTokyuTochiListFuncAsync()
    assert t_list._isBsMiddlePage() is False
    assert "/api/tokyu/tochi/detail" in t_list._getApiKey()


def test_odakyu_investment_url_normalization():
    """odakyu investment の _normalize_detail_url が404の旧URLではなく物件種別パスを正しく保持することを検証"""
    parser = OdakyuInvestmentParser()
    mansion_href = "https://www.odakyu-chukai.com/mansion/detail/B01419-001363/"
    normalized = parser._normalize_detail_url(mansion_href)
    assert normalized == "https://www.odakyu-chukai.com/mansion/detail/B01419-001363/"
    assert "/mansion/detail/" in normalized


def test_daikyo_parser_extract_pref_urls():
    """daikyo parser が都道府県別一覧ページURLを正しく抽出することを検証"""
    parser = DaikyoMansionParser()
    html = """
    <html>
      <body>
        <a href="/buy/mansion/p13/">東京都</a>
        <a href="/buy/mansion/p14/">神奈川県</a>
        <a href="/buy/detail/MHF93062/">新着物件</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    pref_urls = parser._extract_pref_urls(soup)
    assert "https://www.daikyo-anabuki.co.jp/buy/mansion/p13/" in pref_urls
    assert "https://www.daikyo-anabuki.co.jp/buy/mansion/p14/" in pref_urls

    detail_links = set()
    found = list(parser._extract_detail_links(soup, detail_links))
    assert len(found) == 1
    assert "https://www.daikyo-anabuki.co.jp/buy/detail/MHF93062/" in found[0]


def test_url_router_resolves_rearie_and_nomura_pro():
    """UrlRouter が rearie 各種別および nomura pro を正しく解決することを検証"""
    rearie_tochi_url = "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=12345"
    route_rearie = UrlRouter.resolve(rearie_tochi_url)
    assert route_rearie is not None
    assert route_rearie["site"] == "rearie"
    assert route_rearie["property_type"] == "tochi"

    nomura_pro_url = "https://www.nomu.com/pro/detail/A1234567/"
    route_nomura = UrlRouter.resolve(nomura_pro_url)
    assert route_nomura is not None
    assert route_nomura["site"] == "nomura"
    assert route_nomura["property_type"] == "apartment"

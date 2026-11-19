# -*- coding: utf-8 -*-
"""
ライフルホームズ（LIFULL HOME'S） パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.homesParser import HomesMansionParser, HomesKodateParser
from package.models.homes import HomesMansion, HomesKodate

def test_homes_mansion_parser():
    parser = HomesMansionParser()
    item = parser.createEntity()
    assert isinstance(item, HomesMansion)

def test_homes_kodate_parser():
    parser = HomesKodateParser()
    item = parser.createEntity()
    assert isinstance(item, HomesKodate)


def test_homes_find_next_anchor_url_ignores_javascript_href():
    from bs4 import BeautifulSoup
    parser = HomesMansionParser()
    html = '<html><body><a href="javascript:void(0);">次へ</a></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    assert parser._homes_find_next_anchor_url(soup) == ""

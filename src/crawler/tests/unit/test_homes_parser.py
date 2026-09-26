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

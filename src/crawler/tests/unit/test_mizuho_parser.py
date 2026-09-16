# -*- coding: utf-8 -*-
"""
みずほ不動産販売 パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.mizuhoParser import MizuhoMansionParser, MizuhoKodateParser
from package.models.mizuho import MizuhoMansion, MizuhoKodate

def test_mizuho_mansion_parser():
    parser = MizuhoMansionParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoMansion)

def test_mizuho_kodate_parser():
    parser = MizuhoKodateParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoKodate)

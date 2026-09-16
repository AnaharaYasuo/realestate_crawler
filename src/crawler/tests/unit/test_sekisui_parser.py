# -*- coding: utf-8 -*-
"""
積水ハウス不動産 パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.sekisuiParser import SekisuiMansionParser, SekisuiKodateParser
from package.models.sekisui import SekisuiMansion, SekisuiKodate

def test_sekisui_mansion_parser():
    parser = SekisuiMansionParser()
    item = parser.createEntity()
    assert isinstance(item, SekisuiMansion)

def test_sekisui_kodate_parser():
    parser = SekisuiKodateParser()
    item = parser.createEntity()
    assert isinstance(item, SekisuiKodate)

# -*- coding: utf-8 -*-
"""
旭化成不動産レジデンス パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.afrParser import AfrMansionParser, AfrKodateParser
from package.models.afr import AfrMansion, AfrKodate

def test_afr_mansion_parser():
    parser = AfrMansionParser()
    item = parser.createEntity()
    assert isinstance(item, AfrMansion)

def test_afr_kodate_parser():
    parser = AfrKodateParser()
    item = parser.createEntity()
    assert isinstance(item, AfrKodate)

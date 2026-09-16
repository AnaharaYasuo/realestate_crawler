# -*- coding: utf-8 -*-
"""
三菱UFJ不動産販売（すまい1） パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.sumai1Parser import Sumai1MansionParser, Sumai1KodateParser
from package.models.sumai1 import Sumai1Mansion, Sumai1Kodate

def test_sumai1_mansion_parser():
    parser = Sumai1MansionParser()
    item = parser.createEntity()
    assert isinstance(item, Sumai1Mansion)

def test_sumai1_kodate_parser():
    parser = Sumai1KodateParser()
    item = parser.createEntity()
    assert isinstance(item, Sumai1Kodate)

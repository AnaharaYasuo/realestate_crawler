# -*- coding: utf-8 -*-
"""
アットホーム 土地パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.athomeParser import AthomeTochiParser
from package.models.athome import AthomeTochi

def test_athome_tochi_parser():
    parser = AthomeTochiParser()
    item = parser.createEntity()
    assert isinstance(item, AthomeTochi)

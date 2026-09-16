# -*- coding: utf-8 -*-
"""
ライフルホームズ 土地パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.homesParser import HomesTochiParser
from package.models.homes import HomesTochi

def test_homes_tochi_parser():
    parser = HomesTochiParser()
    item = parser.createEntity()
    assert isinstance(item, HomesTochi)

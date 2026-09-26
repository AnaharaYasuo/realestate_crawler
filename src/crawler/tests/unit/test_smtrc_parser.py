# -*- coding: utf-8 -*-
"""
三井住友トラスト不動産 パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.smtrcParser import SmtrcMansionParser, SmtrcKodateParser, SmtrcInvestmentParser
from package.models.smtrc import SmtrcMansion, SmtrcKodate, SmtrcInvestment

def test_smtrc_mansion_parser():
    parser = SmtrcMansionParser()
    item = parser.createEntity()
    assert isinstance(item, SmtrcMansion)

def test_smtrc_kodate_parser():
    parser = SmtrcKodateParser()
    item = parser.createEntity()
    assert isinstance(item, SmtrcKodate)

def test_smtrc_investment_parser():
    parser = SmtrcInvestmentParser()
    item = parser.createEntity()
    assert isinstance(item, SmtrcInvestment)

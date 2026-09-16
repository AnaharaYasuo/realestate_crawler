# -*- coding: utf-8 -*-
"""
一括・追加電鉄/ハウスメーカー系列 パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.odakyuParser import OdakyuMansionParser, OdakyuInvestmentParser
from package.parser.totateParser import TotateMansionParser
from package.parser.daiwaParser import DaiwaMansionParser
from package.parser.smtrcParser import SmtrcInvestmentParser
from package.parser.sumai1Parser import Sumai1InvestmentParser
from package.parser.mizuhoParser import MizuhoInvestmentParser
from package.models.odakyu import OdakyuMansion, OdakyuInvestment
from package.models.totate import TotateMansion
from package.models.daiwa import DaiwaMansion
from package.models.smtrc import SmtrcInvestment
from package.models.sumai1 import Sumai1Investment
from package.models.mizuho import MizuhoInvestment

def test_odakyu_mansion_parser():
    parser = OdakyuMansionParser()
    item = parser.createEntity()
    assert isinstance(item, OdakyuMansion)

def test_totate_mansion_parser():
    parser = TotateMansionParser()
    item = parser.createEntity()
    assert isinstance(item, TotateMansion)

def test_daiwa_mansion_parser():
    parser = DaiwaMansionParser()
    item = parser.createEntity()
    assert isinstance(item, DaiwaMansion)

def test_smtrc_investment_parser():
    parser = SmtrcInvestmentParser()
    item = parser.createEntity()
    assert isinstance(item, SmtrcInvestment)

def test_sumai1_investment_parser():
    parser = Sumai1InvestmentParser()
    item = parser.createEntity()
    assert isinstance(item, Sumai1Investment)

def test_mizuho_investment_parser():
    parser = MizuhoInvestmentParser()
    item = parser.createEntity()
    assert isinstance(item, MizuhoInvestment)

def test_odakyu_investment_parser():
    parser = OdakyuInvestmentParser()
    item = parser.createEntity()
    assert isinstance(item, OdakyuInvestment)

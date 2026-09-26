# -*- coding: utf-8 -*-
"""
三井住友トラスト不動産 パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.smtrcParser import SmtrcMansionParser, SmtrcKodateParser, SmtrcInvestmentParser
from package.models.smtrc import SmtrcMansion, SmtrcKodate, SmtrcInvestment
from package.parser.baseParser import SkipPropertyException
from bs4 import BeautifulSoup
import pytest

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

def test_smtrc_investment_skip_when_missing_yield_and_rent():
    parser = SmtrcInvestmentParser()
    item = parser.createEntity()
    soup = BeautifulSoup("<html><body><h1>テスト物件</h1><table><tr><th>所在地</th><td>東京都港区</td></tr></table></body></html>", "html.parser")
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, soup)

def test_smtrc_investment_success_with_yield():
    parser = SmtrcInvestmentParser()
    item = parser.createEntity()
    soup = BeautifulSoup("<html><body><h1>テスト収益物件</h1><table><tr><th>所在地</th><td>東京都港区</td></tr><tr><th>利回り</th><td>5.5%</td></tr><tr><th>現行年間収入</th><td>240万円</td></tr></table></body></html>", "html.parser")
    res = parser._parsePropertyDetailPage(item, soup)
    assert res.grossYield == 5.5
    assert res.annualRent == 2400000

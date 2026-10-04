# -*- coding: utf-8 -*-
"""
Issue #635: baseParser._extract_card_price の誤抽出バグ解消テスト。
「1分」「2階」「築10年」等の単位が誤って価格と判定されないこと、
100万円未満のノイズが除外されること、
「1,330 万円」のように数字と「万」の間に空白があっても正常に取得できることを検証する。
"""
from bs4 import BeautifulSoup

from package.parser.baseParser import ParserBase


def test_extract_card_price_ignores_minutes_floors_years():
    html = """
    <div class="property-card">
        <a href="/mansion/detail_123">テスト物件</a>
        <div class="info">
            <span class="walk">駅徒歩1分</span>
            <span class="floor">2階建</span>
            <span class="age">築10年</span>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a")
    price = ParserBase._extract_card_price(link)
    assert price is None


def test_extract_card_price_ignores_under_one_million():
    html = """
    <div class="property-card">
        <a href="/mansion/detail_123">テスト物件</a>
        <div class="info">
            <span class="price">80万円</span>
            <span class="rent">賃料 8.5万円</span>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a")
    price = ParserBase._extract_card_price(link)
    assert price is None


def test_extract_card_price_matches_spaced_man():
    html = """
    <div class="property-card">
        <a href="/mansion/detail_123">テスト物件</a>
        <div class="info">
            <span class="price">1,330 万円</span>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a")
    price = ParserBase._extract_card_price(link)
    assert price == 13300000


def test_extract_card_price_matches_oku_and_man():
    html = """
    <div class="property-card">
        <a href="/mansion/detail_123">テスト物件</a>
        <div class="info">
            <span class="price">1億2,500万円</span>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a")
    price = ParserBase._extract_card_price(link)
    assert price == 125000000

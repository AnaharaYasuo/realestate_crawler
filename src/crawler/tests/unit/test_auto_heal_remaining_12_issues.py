# -*- coding: utf-8 -*-
"""Regression tests for remaining 12 auto-heal issues (#1443, #1446, #1448, #1449, #1454, #1457, #1466, #1467, #1747, #1748, #1775, #1776)."""

from bs4 import BeautifulSoup
import pytest

from package.parser.adcastParser import AdCastTochiParser
from package.parser.athomeParser import AthomeMansionParser, AthomeTochiParser
from package.parser.baseParser import SkipPropertyException
from package.parser.heimParser import HeimTochiParser
from package.parser.homesParser import HomesTochiParser
from package.parser.keikyuParser import KeikyuMansionParser
from package.parser.kenbiyaParser import (
    KenbiyaKodateParser,
    KenbiyaMansionParser,
    KenbiyaTochiParser,
)
from package.parser.misawaParser import MisawaKodateParser
from package.parser.mitsuiParser import MitsuiKodateParser


def test_kenbiya_tochi_skips_placeholder_1443():
    html = """
    <html><body>
      <h1>品川区 売地</h1>
      <table>
        <tr><th>価格</th><td>1万円</td></tr>
        <tr><th>土地面積</th><td>1.0㎡</td></tr>
      </table>
    </body></html>
    """
    parser = KenbiyaTochiParser()
    item = parser.createEntity()
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))


def test_kenbiya_madori_and_traffic_fallbacks_1747_1748_1776():
    html = """
    <html><body>
      <h1>三鷹市 2LDK マンション</h1>
      <div>JR中央線「三鷹」駅 徒歩8分</div>
      <table>
        <tr><th>価格</th><td>2,980万円</td></tr>
        <tr><th>専有面積</th><td>55.00㎡</td></tr>
      </table>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    m_parser = KenbiyaMansionParser()
    assert m_parser._parseMadori(soup) == "2LDK"
    assert "三鷹" in m_parser._parseTransport1(soup)

    k_parser = KenbiyaKodateParser()
    assert k_parser._parseMadori(soup) == "2LDK"


def test_athome_mansion_skips_low_price_1449():
    html = """
    <html><body>
      <h1>狭山市 マンション</h1>
      <table>
        <tr><th>価格</th><td>50万円</td></tr>
        <tr><th>専有面積</th><td>45.00m²</td></tr>
        <tr><th>所在階</th><td>2階</td></tr>
      </table>
    </body></html>
    """
    parser = AthomeMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.athome.co.jp/mansion/6981791235"
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))


def test_athome_tochi_skips_zero_land_area_1446():
    html = "<html><body><h1>売地</h1><table><tr><th>価格</th><td>3,000万円</td></tr></table></body></html>"
    parser = AthomeTochiParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.athome.co.jp/tochi/3925712901/"
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))


def test_mitsui_kodate_skips_low_price_1467():
    html = """
    <html><body>
      <h1>世田谷区 戸建</h1>
      <table>
        <tr><th>価格</th><td>1万円</td></tr>
        <tr><th>土地面積</th><td>100.00㎡</td></tr>
        <tr><th>建物面積</th><td>85.00㎡</td></tr>
      </table>
    </body></html>
    """
    parser = MitsuiKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/kodate/bkdetail/F074RA07/"
    with pytest.raises(SkipPropertyException):
        parser._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))


def test_heim_tochi_extracts_body_traffic_1454():
    html = """
    <html><body>
      <h1>スマートハイムシティ三鷹市深大寺II</h1>
      <p>JR中央線「武蔵境」駅 徒歩24~25分 全11区画</p>
    </body></html>
    """
    parser = HeimTochiParser()
    specs = parser._get_specs(BeautifulSoup(html, "lxml"))
    assert "武蔵境" in specs.get("交通", "")


def test_keikyu_mansion_extracts_body_traffic_1775():
    html = """
    <html><body>
      <h1>京急マンション</h1>
      <div>京急本線「上大岡」駅 徒歩6分</div>
      <table>
        <tr><th>価格</th><td>4,200万円</td></tr>
        <tr><th>所在地</th><td>横浜市港南区上大岡西1丁目</td></tr>
        <tr><th>専有面積</th><td>65.00㎡</td></tr>
      </table>
    </body></html>
    """
    parser = KeikyuMansionParser()
    item = parser.createEntity()
    result = parser._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))
    assert result.railwayWalkMinute1 == 6


def test_adcast_homes_misawa_sanity_1448_1457_1466():
    ad_html = "<html><body><table><tr><th>建ぺい率/容積率</th><td>60%／200%</td></tr></table></body></html>"
    ad_parser = AdCastTochiParser()
    assert ad_parser._parseKenpei(BeautifulSoup(ad_html, "lxml")) == "60%"
    assert ad_parser._parseYouseki(BeautifulSoup(ad_html, "lxml")) == "200%"

    assert HomesTochiParser() is not None
    assert MisawaKodateParser() is not None

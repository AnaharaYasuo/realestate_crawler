# -*- coding: utf-8 -*-
"""
野村戸建て間取りスマートフォールバック抽出の単体テスト (Issue #917)
"""
from bs4 import BeautifulSoup
from package.parser.nomuraParser import NomuraKodateParser


def test_nomura_kodate_madori_fallback_from_property_name():
    """スペック表に間取りがない場合、物件名から間取りを抽出できること"""
    parser = NomuraKodateParser()

    html = """
    <html>
      <body>
        <h1 class="mod-detailHead__ttl">三鷹市野崎2丁目 中古一戸建てNEW 2/10 3SLDK</h1>
        <div class="mod-detailPrice">6,490万円</div>
        <table class="mod-detailSpecTable">
          <tr><th>所在地</th><td>東京都三鷹市野崎2丁目</td></tr>
          <tr><th>土地面積</th><td>120.5㎡</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    madori = parser._parseMadori(soup)
    assert madori == "3SLDK"


def test_nomura_kodate_madori_fallback_from_biko():
    """スペック表・物件名に間取りがない場合、備考から間取りを抽出できること"""
    parser = NomuraKodateParser()

    html = """
    <html>
      <body>
        <h1 class="mod-detailHead__ttl">町田市つくし野2丁目 新価格</h1>
        <div class="mod-detailPrice">7,200万円</div>
        <table class="mod-detailSpecTable">
          <tr><th>所在地</th><td>東京都町田市つくし野2丁目</td></tr>
          <tr><th>備考</th><td>南向きのゆとりある4LDK+Sの邸宅です。</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    madori = parser._parseMadori(soup)
    assert madori == "4LDK+S"


def test_nomura_kodate_madori_normal_spec_priority():
    """スペック表に間取りがある場合はスペック表の値を最優先すること"""
    parser = NomuraKodateParser()

    html = """
    <html>
      <body>
        <h1 class="mod-detailHead__ttl">世田谷区中古一戸建て 3LDK</h1>
        <div class="mod-detailPrice">8,000万円</div>
        <table class="mod-detailSpecTable">
          <tr><th>間取り</th><td>4LDK</td></tr>
          <tr><th>所在地</th><td>東京都世田谷区</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    madori = parser._parseMadori(soup)
    assert madori == "4LDK"

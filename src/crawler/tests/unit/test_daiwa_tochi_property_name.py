# -*- coding: utf-8 -*-
"""Unit: Daiwa land pages use empty h1 — name must fall back to og/title/address."""
from bs4 import BeautifulSoup

from package.parser.daiwaParser import DaiwaTochiParser


def test_daiwa_tochi_property_name_falls_back_when_h1_empty():
    html = """
    <html><head>
      <title>東京都八王子市長房町｜土地購入｜Livness</title>
      <meta property="og:title" content="東京都八王子市長房町｜土地購入｜Livness" />
    </head><body>
      <h1></h1>
      <table><tr><th>所在地</th><td>東京都八王子市長房町</td></tr>
      <tr><th>価格</th><td>2,580万円</td></tr></table>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    name = DaiwaTochiParser()._parsePropertyName(soup)
    assert name == "東京都八王子市長房町"

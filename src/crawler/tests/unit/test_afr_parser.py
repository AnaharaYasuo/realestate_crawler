# -*- coding: utf-8 -*-
"""
旭化成不動産レジデンス パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from package.parser.afrParser import AfrMansionParser, AfrKodateParser
from package.models.afr import AfrMansion, AfrKodate

def test_afr_mansion_parser():
    parser = AfrMansionParser()
    item = parser.createEntity()
    assert isinstance(item, AfrMansion)

def test_afr_kodate_parser():
    parser = AfrKodateParser()
    item = parser.createEntity()
    assert isinstance(item, AfrKodate)


def test_afr_mansion_accepts_senyu_minmax_labels():
    """一棟売マンションは『専有面積（最小）』表記 — SkipProperty しないこと."""
    from bs4 import BeautifulSoup

    html = """
    <html><body>
      <h1>テスト一棟売マンション</h1>
      <table>
        <tr><th>価格</th><td>20780万円</td></tr>
        <tr><th>所在地</th><td>吹田市千里山西１丁目</td></tr>
        <tr><th>専有面積（最小）</th><td>84.77m²（25.64坪）</td></tr>
        <tr><th>専有面積（最大）</th><td>340.48m²（102.99坪）</td></tr>
      </table>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AfrMansionParser()
    item = parser.createEntity()
    parsed = parser._parsePropertyDetailPage(item, soup)
    assert parsed.senyuMensekiStr
    assert "84.77" in parsed.senyuMensekiStr


def test_afr_mansion_list_prefers_mansion_bukken_name():
    from bs4 import BeautifulSoup
    import asyncio

    html = """
    <html><body><script>
    var list = [
      {'number': 'BMS00001', 'bukkenName': '川崎市の家&nbsp;', 'landArea': '100m2'},
      {'number': 'BMS09936', 'bukkenName': '【一棟売マンション】吹田市&nbsp;', 'landArea': '100m2'},
      {'number': 'BMS00002', 'bukkenName': '横浜の家&nbsp;', 'landArea': '120m2'}
    ];
    </script></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AfrMansionParser()

    async def collect():
        return [u async for u in parser.parseRootPage(soup)]

    urls = asyncio.run(collect())
    assert urls
    assert "bno=BMS09936" in urls[0]


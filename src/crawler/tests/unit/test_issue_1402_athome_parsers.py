import pytest
from bs4 import BeautifulSoup
from package.parser.baseParser import SkipPropertyException
from package.parser.athomeParser import AthomeTochiParser, AthomeMansionParser
from types import SimpleNamespace


def test_athome_tochi_compound_kenpei_youseki():
    """建蔽率/容積率が複合ヘッダーで記載されている場合に正しく抽出されること (Issue #1402)"""
    html = """
    <html>
      <body>
        <table>
          <tr>
            <th>建蔽率/容積率</th>
            <td>-/- 60％・200％</td>
            <th>私道負担</th>
            <td>-</td>
          </tr>
          <tr>
            <th>建ぺい率</th>
            <td>-</td>
            <th>容積率</th>
            <td>-</td>
            <th>地目</th>
            <td>宅地</td>
          </tr>
          <tr>
            <th>土地面積</th>
            <td>120.50㎡</td>
          </tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AthomeTochiParser()
    item = SimpleNamespace(
        pageUrl="https://www.athome.co.jp/tochi/3924714401/",
        tochiMensekiStr="",
        tochiMenseki=120.50,
        kenpeiStr="",
        kenpei=None,
        yousekiStr="",
        youseki=None,
        youtoChiiki="",
        chimoku="",
        setsudou="",
    )
    result = parser._parsePropertyDetailPage(item, soup)
    assert result.kenpei == 60.0
    assert result.youseki == 200.0


def test_athome_mansion_townhouse_skip_with_proper_reason():
    """タウンハウス・テラスハウス等で所在階がない場合、タウンハウス理由でスキップされること (Issue #1402)"""
    html = """
    <html>
      <head><title>狭山市 大字水野 ４ＤＫ</title></head>
      <body>
        <table>
          <tr>
            <th>物件種目</th>
            <td>中古タウンハウス</td>
          </tr>
          <tr>
            <th>階建 / 階</th>
            <td>2階建</td>
          </tr>
          <tr>
            <th>専有面積</th>
            <td>85.0㎡</td>
          </tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AthomeMansionParser()
    item = SimpleNamespace(
        pageUrl="https://www.athome.co.jp/mansion/6981791235/",
        propertyName="狭山市 大字水野 ４ＤＫ",
        kaisuStr="2階建",
        senyuMensekiStr="85.0㎡",
        senyuMenseki=85.0,
    )
    with pytest.raises(SkipPropertyException) as exc_info:
        parser._ensure_mansion_located_floor(item, soup, item.pageUrl, specs={"物件種目": "中古タウンハウス"})
    assert "townhouse" in str(exc_info.value).lower()

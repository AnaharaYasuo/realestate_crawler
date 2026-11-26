import pytest
from bs4 import BeautifulSoup

from package.parser.tokyuParser import TokyuInvestmentKodateParser


@pytest.mark.asyncio
async def test_tokyu_investment_list_falls_back_to_href_selector_when_nextjs_empty():
    """__NEXT_DATA__ が空リストを返し CSS Modules クラス名が変更されても詳細URLを重複排除抽出できること。"""
    html = """
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">
          {"props": {"pageProps": {"propertyList": []}}}
        </script>
      </head>
      <body>
        <div class="hashed_card">
          <a href="/fudosan-toushi/C4826XP16/">
            <h3 class="kSUQRq_globalHeading">テスト投資物件A</h3>
          </a>
          <a href="/fudosan-toushi/C4826XP16/">詳細を見る</a>
        </div>
        <div class="hashed_card">
          <a href="/fudosan-toushi/C9999AB01/">
            <h3 class="kSUQRq_globalHeading">テスト投資物件B</h3>
          </a>
        </div>
      </body>
    </html>
    """
    parser = TokyuInvestmentKodateParser("")
    soup = BeautifulSoup(html, "html.parser")
    items = [item async for item in parser.parsePropertyListPage(soup)]
    urls = [item.url for item in items]
    assert urls == [
        "https://www.livable.co.jp/fudosan-toushi/C4826XP16/",
        "https://www.livable.co.jp/fudosan-toushi/C9999AB01/",
    ]

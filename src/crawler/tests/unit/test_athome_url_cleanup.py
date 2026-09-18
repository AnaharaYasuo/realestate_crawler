# -*- coding: utf-8 -*-
import pytest
from bs4 import BeautifulSoup

from package.parser.athomeParser import AthomeMansionParser
from package.parser.baseParser import ListingEndedException


def test_athome_get_root_dest_url_clean():
    """Athome の getRootDestUrl が二重スラッシュや余分な list プレフィックスを生成しないことを検証"""
    parser = AthomeMansionParser()

    # 1. ルート相対URL
    url1 = parser.getRootDestUrl("/mansion/1085190874/?DOWN=1")
    assert url1 == "https://www.athome.co.jp/mansion/1085190874/?DOWN=1"
    assert "//mansion" not in url1.replace("https://", "")

    # 2. base_domain がリストURLの場合でも正常に結合されること
    url2 = parser.getRootDestUrl("/mansion/1085190874/", base_domain="https://www.athome.co.jp/mansion/chuko/tokyo/shinjuku-city/list/")
    assert url2 == "https://www.athome.co.jp/mansion/1085190874/"
    assert "list//mansion" not in url2

    # 3. 完全修飾URL
    url3 = parser.getRootDestUrl("https://www.athome.co.jp/mansion/1085190874/")
    assert url3 == "https://www.athome.co.jp/mansion/1085190874/"


def test_athome_listing_ended_detection():
    """掲載終了物件のHTMLが与えられた際に ListingEndedException がスローされることを検証"""
    parser = AthomeMansionParser()
    item = parser.createEntity()

    html_ended = """
    <html>
      <head><title>【アットホーム】お探しの物件は見つかりませんでした</title></head>
      <body>
        <div class="mod-message-end">この物件は掲載を終了しました。</div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html_ended, "html.parser")

    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(item, soup)

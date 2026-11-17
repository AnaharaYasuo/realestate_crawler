import pytest
from bs4 import BeautifulSoup

from package.parser.tokyuParser import check_tokyu_listing_ended, ListingEndedException


def test_tokyu_nextjs_is_expired_raises_listing_ended():
    html = """
    <html>
      <head><title>東急リバブル</title></head>
      <body>
        <script id="__NEXT_DATA__" type="application/json">
          {"page": "/templates/bus-002/01", "props": {"pageProps": {"isExpired": true, "summary": {}}}}
        </script>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    with pytest.raises(ListingEndedException) as exc_info:
        check_tokyu_listing_ended(soup, "https://www.livable.co.jp/mansion/C12345678/")
    assert "Tokyu isExpired" in str(exc_info.value) or "Tokyu listing ended" in str(exc_info.value) or "ended" in str(exc_info.value)


def test_tokyu_nextjs_search_redirect_missing_summary_raises_listing_ended():
    html = """
    <html>
      <head><title>平塚市 見附町の新築マンション・中古マンション購入｜東急リバブル</title></head>
      <body>
        <script id="__NEXT_DATA__" type="application/json">
          {"page": "/templates/bui-005/01", "props": {"pageProps": {"propertyList": [], "totalPropertyCount": 100}}}
        </script>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    with pytest.raises(ListingEndedException) as exc_info:
        check_tokyu_listing_ended(soup, "https://www.livable.co.jp/mansion/C14249072/")
    assert "ended" in str(exc_info.value).lower() or "redirect" in str(exc_info.value).lower()


def test_tokyu_nextjs_active_detail_does_not_raise():
    html = """
    <html>
      <head><title>物件詳細｜東急リバブル</title></head>
      <body>
        <h1>チュリス氷川坂</h1>
        <script id="__NEXT_DATA__" type="application/json">
          {"page": "/templates/bus-002/01", "props": {"pageProps": {"isExpired": false, "summary": {"tableItems": []}}}}
        </script>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    # Should not raise
    check_tokyu_listing_ended(soup, "https://www.livable.co.jp/mansion/C4826XY97/")

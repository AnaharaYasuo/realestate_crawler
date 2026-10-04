import pytest
from bs4 import BeautifulSoup
from package.parser.baseParser import (
    ParserBase,
    ListingEndedException,
    ServerBusyException,
)

class DummyParser(ParserBase):
    property_type = 'mansion'
    def createEntity(self):
        return None
    def getCharset(self):
        return 'utf-8'
    def _parsePrice(self, response, specs=None): return None
    def _parsePriceStr(self, response, specs=None): return ""
    def _parseAddress(self, response, specs=None): return ""
    def _parsePropertyName(self, response, specs=None): return ""
    def _parseTransport1(self, response, specs=None): return ""
    def _parseSenyuMenseki(self, response, specs=None): return None
    def _parseMadori(self, response, specs=None): return ""


def test_listing_ended_detection_valid_keyword():
    """正規の掲載終了画面では ListingEndedException が送出されること"""
    html = """
    <html>
        <head><title>お探しの物件は掲載が終了しました</title></head>
        <body>
            <div class="mod-message-end">
                <h1>掲載終了のお知らせ</h1>
                <p>この物件の掲載は終了いたしました。最新の物件情報をお探しください。</p>
            </div>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    with pytest.raises(ListingEndedException):
        DummyParser._raise_if_listing_ended(soup, "https://example.com/property/123")


def test_waf_or_bot_block_does_not_raise_listing_ended():
    """WAFやCloudflare遮断画面では ListingEndedException が送出されず、LoadPropertyPageException または適切な例外となること"""
    html = """
    <html>
        <head><title>Just a moment... (Cloudflare)</title></head>
        <body>
            <div id="cf-wrapper">
                <h2>Checking if the site connection is secure</h2>
                <p>Enable JavaScript and cookies to continue</p>
                <p>Ray ID: 123456789 - Access Denied</p>
            </div>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    # WAF画面は掲載終了と誤認させてはならない
    # 掲載終了キーワードは含まれないため例外は送出されない
    DummyParser._raise_if_listing_ended(soup, "https://example.com/property/123")


def test_server_busy_detection():
    """サーバー混雑画面では ServerBusyException が送出されること"""
    html = """
    <html>
        <head><title>現在サーバーが混み合っています</title></head>
        <body><p>しばらく経ってから再度アクセスしてください。</p></body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    with pytest.raises(ServerBusyException):
        DummyParser._raise_if_listing_ended(soup, "https://example.com/property/123")

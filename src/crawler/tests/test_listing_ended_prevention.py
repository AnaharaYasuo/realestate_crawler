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


def test_athome_auth_intermediate_page_raises_server_busy():
    """アットホームの認証中または物件不在中間画面では ServerBusyException (待避) が送出されること (Issue #752)"""
    html = """
    <html>
        <head><title>【アットホーム】認証中</title><style>body { display: none !important; }</style></head>
        <body>
            <div class="container">
                <div class="center">認証中</div>
            </div>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    from package.parser.athomeParser import AthomeMansionParser
    from package.models.athome import AthomeMansion
    parser = AthomeMansionParser()
    item = AthomeMansion()
    with pytest.raises(ServerBusyException):
        parser._parsePropertyDetailPage(item, soup)


def test_rearie_redirect_to_top_page_raises_listing_ended():
    """パナソニックホームズ（リアリエ）で明示的に掲載終了・見つからない文言がある場合に ListingEndedException を送出すること"""
    html = """
    <!doctype html>
    <html lang="ja">
      <head>
        <title>お探しの物件は見つかりませんでした - パナソニック ホームズ - Panasonic</title>
      </head>
      <body>
        <header><h1>パナソニック ホームズ</h1></header>
        <div class="not-found">ご指定のページは見つかりませんでした</div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    from package.parser.rearieParser import RearieMansionParser
    from package.models.rearie import RearieMansion
    parser = RearieMansionParser()
    item = RearieMansion()
    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(item, soup)


def test_rearie_empty_shell_with_blank_table_view_raises_listing_ended():
    """掲載終了で画面上に掲載終了文言がある場合は ListingEndedException"""
    html = """
    <!doctype html><html lang="ja"><head><title>掲載終了物件 - パナソニック ホームズ - Panasonic</title></head>
    <body><h1></h1><div class="mod-message-end">お探しの物件は掲載を終了しました</div></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    from package.parser.rearieParser import RearieMansionParser
    from package.models.rearie import RearieMansion
    parser = RearieMansionParser()
    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(RearieMansion(), soup)


def test_rearie_layout_table_brand_only_raises_listing_ended():
    """掲載終了文言を含む画面で ListingEndedException が送出されること"""
    html = """
    <!doctype html><html lang="ja"><head><title>指定された物件は掲載を終了いたしました - パナソニック ホームズ - Panasonic</title></head>
    <body><table><tr><td>掲載終了いたしました</td></tr></table></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    from package.parser.rearieParser import RearieMansionParser
    from package.models.rearie import RearieMansion
    parser = RearieMansionParser()
    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(RearieMansion(), soup)


def test_stepon_non_property_url_rejection():
    """住友不動産ステップの建物調査等の非物件URLが即時スキップされること (Issue #943)"""
    from package.parser.baseParser import SkipPropertyException
    with pytest.raises(SkipPropertyException):
        DummyParser._reject_non_property_url("https://www.stepon.co.jp/step_buildingsurvey/")
    with pytest.raises(SkipPropertyException):
        DummyParser._reject_non_property_url("https://www.stepon.co.jp/step_buildingsurvey/detail")


def test_sumifu_parser_none_safe_parsing():
    """スペック表が存在しない・欠損したHTMLでもSumifuParserがNoneType例外を起こさないこと (Issue #943)"""
    from package.parser.sumifuParser import SumifuMansionParser
    from package.models.sumifu import SumifuMansion
    parser = SumifuMansionParser()
    item = SumifuMansion()
    html = "<html><head><title>テスト案内</title></head><body><p>コンテンツなし</p></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    # 例外を送出せずパースが完了すること
    res_item = parser._parsePropertyDetailPage(item, soup)
    assert res_item.price is None
    assert res_item.propertyName == ""


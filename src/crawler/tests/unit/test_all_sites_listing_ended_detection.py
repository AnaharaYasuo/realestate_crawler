import pytest
from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase, ListingEndedException


class TestAllSitesListingEndedDetection:
    """全サイトの掲載終了画面（404/410/明示的文言）における ListingEndedException 検知の包括テスト"""

    @pytest.mark.parametrize(
        "site_name,html",
        [
            ("athome", "<html><head><title>お探しの物件は見つかりませんでした</title></head></html>"),
            ("homes", "<html><head><title>404 Not Found</title></head><body><h1>お探しのページは見つかりません</h1></body></html>"),
            ("sumifu", '<html><head><title>ご指定のページは見つかりませんでした</title></head><body><div class="error">ご指定のページは見つかりませんでした</div></body></html>'),
            ("mitsui", '<html><head><title>物件詳細</title></head><body><div class="mod-message-end">掲載を終了いたしました</div></body></html>'),
            ("tokyu", "<html><head><title>掲載終了</title></head><body><div>お探しの物件は、掲載が終了いたしました</div></body></html>"),
            ("nomura", "<html><head><title>物件詳細</title></head><body><p>掲載が終了したか、成約済みになった可能性があります</p></body></html>"),
            ("daikyo", "<html><head><title>該当する物件がありません</title></head><body><h1>該当する物件がありません</h1></body></html>"),
            ("smtrc", "<html><head><title>メッセージ│三井住友トラスト</title></head><body><div>ご指定の物件は、掲載終了いたしました。</div></body></html>"),
            ("sumai1", "<html><head><title>該当する物件は存在しません｜三菱UFJ不動産</title></head><body><h1>該当する物件は存在しません</h1><p>お探しの物件は、すでに成約済みとなったか掲載が終了となっております。</p></body></html>"),
            ("odakyu", "<html><head><title>お探しのページは見つかりませんでした</title></head></html>"),
            ("mizuho", "<html><head><title>お探しの物件は見つかりませんでした</title></head></html>"),
            ("kenbiya", "<html><head><title>掲載終了物件</title></head><body><div>掲載終了物件です</div></body></html>"),
            ("ietan", "<html><head><title>物件詳細</title></head><body><div>指定された物件は掲載を終了いたしました</div></body></html>"),
            ("misawa", '<html><head><title>物件詳細</title></head><body><div class="property-ended">掲載を終了しました</div></body></html>'),
            ("afr", "<html><head><title>こちらの物件の掲載は終了致しました</title></head><body><h1>物件詳細</h1></body></html>"),
            ("keio", "<html><head><title>お探しの物件は見つかりませんでした</title></head></html>"),
            ("sumirin", "<html><head><title>掲載終了</title></head><body><div>お探しの物件は掲載終了いたしました</div></body></html>"),
            ("keikyu", "<html><head><title>お探しのページは見つかりません</title></head></html>"),
            ("keisei", "<html><head><title>お探しのページは見つかりません</title></head></html>"),
            ("daiwa", "<html><head><title>マンション購入｜Livness｜大和ハウスリアルエステート</title></head><body><p>物件が見つかりませんでした</p></body></html>"),
            ("toho", "<html><head><title>成約済</title></head><body><p>この物件は掲載を終了いたしました</p></body></html>"),
            ("haseko", "<html><head><title>お探しの物件は見つかりませんでした</title></head></html>"),
            ("rearie", '<html><head><title>お探しの物件は見つかりませんでした - パナソニック ホームズ</title></head><body><div class="not-found">お探しの物件は見つかりませんでした</div></body></html>'),
            ("adcast", "<html><head><title>お探しの物件は見つかりませんでした</title></head></html>"),
            ("totate", "<html><head><title>お探しのページは見つかりませんでした</title></head></html>"),
            ("sotetsu", "<html><head><title>お探しのページは見つかりませんでした</title></head></html>"),
            ("sekisui", "<html><head><title>該当する物件がありません</title></head></html>"),
            ("reguide", "<html><head><title>404 Not Found</title></head><body><h1>お探しのページは見つかりません</h1></body></html>"),
        ],
    )
    def test_all_sites_listing_ended_detection(self, site_name, html):
        soup = BeautifulSoup(html, "html.parser")
        with pytest.raises(ListingEndedException):
            ParserBase._raise_if_listing_ended(soup, f"https://example.com/{site_name}/detail/123")

    @pytest.mark.parametrize("status_code", [404, 410])
    def test_http_404_410_raises_listing_ended(self, status_code):
        with pytest.raises(ListingEndedException):
            ParserBase._validate_http_status(status_code, "https://example.com/property/123")

    def test_active_property_does_not_raise(self):
        active_html = """
        <html>
            <head><title>中古マンション 3LDK 4500万円</title></head>
            <body>
                <h1>テスト物件</h1>
                <div>価格: 4500万円</div>
                <div>所在地: 東京都新宿区</div>
            </body>
        </html>
        """
        soup = BeautifulSoup(active_html, "html.parser")
        # 掲載終了文言がない場合は例外が発生しないこと
        ParserBase._raise_if_listing_ended(soup, "https://example.com/property/active")

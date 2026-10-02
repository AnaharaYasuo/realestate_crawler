# -*- coding: utf-8 -*-
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from bs4 import BeautifulSoup

from package.parser.baseParser import (
    ParserBase,
    ListingEndedException,
    ServerBusyException,
)
from package.parser.mitsuiParser import MitsuiMansionParser


class DummyTestParser(ParserBase):
    property_type = "mansion"

    def _parsePropertyName(self, response: BeautifulSoup):
        return "テストマンション"

    def _parsePriceStr(self, response: BeautifulSoup):
        return "5000万円"

    def _parsePrice(self, response: BeautifulSoup):
        return 50000000

    def _parseAddress(self, response: BeautifulSoup):
        return "東京都千代田区1-1"

    def _parseTransport1(self, response: BeautifulSoup):
        return "山手線 東京駅 徒歩5分"

    def _parseTraffic(self, response: BeautifulSoup, item):
        pass

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item.propertyName = self._parsePropertyName(response)
        return item


def test_base_parser_raise_if_listing_ended_title_keywords():
    """タイトルに掲載終了キーワードが含まれている場合に ListingEndedException を送出"""
    ended_titles = [
        "掲載終了物件｜不動産情報",
        "お探しの物件は、掲載が終了いたしました",
        "【成約御礼】ご成約済み物件",
        "お探しのページは見つかりませんでした",
        "物件情報（掲載終了）",
    ]
    for title in ended_titles:
        html = f"<html><head><title>{title}</title></head><body><div>コンテンツ</div></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        with pytest.raises(ListingEndedException):
            ParserBase._raise_if_listing_ended(soup, "https://example.com/item/1")


def test_base_parser_raise_if_listing_ended_body_keywords():
    """タイトルは通常だが、本文に掲載終了の定型フレーズが含まれている場合に ListingEndedException を送出"""
    ended_bodies = [
        "<div>掲載が終了したか、成約済みになった可能性があります。</div>",
        "<p>お探しの物件は、掲載が終了いたしました。</p>",
        "<div class='not-found'>ご指定の物件は掲載を終了いたしました。</div>",
        "<span>お探しのページは存在しないか、掲載が終了した可能性があります。</span>",
    ]
    for body in ended_bodies:
        html = f"<html><head><title>物件詳細</title></head><body>{body}</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        with pytest.raises(ListingEndedException):
            ParserBase._raise_if_listing_ended(soup, "https://example.com/item/2")


def test_base_parser_raise_if_server_busy():
    """サーバー混雑メッセージで ServerBusyException が送出されること"""
    html = "<html><head><title>サーバーが混み合っています</title></head><body>現在アクセスが集中しています</body></html>"
    soup = BeautifulSoup(html, "html.parser")
    with pytest.raises(ServerBusyException):
        ParserBase._raise_if_listing_ended(soup, "https://example.com/busy")


def test_base_parser_active_page_does_not_raise():
    """通常のアクティブ物件ページでは例外が送出されないこと"""
    html = """
    <html>
      <head><title>パークタワー晴海 3LDK 8500万円</title></head>
      <body>
        <h1>パークタワー晴海</h1>
        <div class="price">8500万円</div>
        <p>※掲載終了時はご了承ください（免責事項のテスト）</p>
        <div class="related-links">
          <a href="/archive">お探しの物件は、掲載が終了した物件一覧はこちら</a>
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    # 例外が起きないこと（リンク内の文言は除外）
    ParserBase._raise_if_listing_ended(soup, "https://example.com/active")


def test_base_parser_multiple_h1_inspection():
    """2番目のh1要素に掲載終了キーワードがある場合でも検知されること"""
    html = """
    <html>
      <head><title>物件詳細</title></head>
      <body>
        <h1>物件トップ</h1>
        <h1>お探しのページは見つかりません</h1>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    with pytest.raises(ListingEndedException):
        ParserBase._raise_if_listing_ended(soup, "https://example.com/multi-h1")



def test_base_parser_related_properties_does_not_trigger_listing_ended():
    """関連物件・おすすめ物件欄 (.related-properties) の文言や h1 は除外され誤検知しないこと"""
    html = """
    <html>
      <head><title>シティタワー品川 2LDK 6800万円</title></head>
      <body>
        <h1>シティタワー品川</h1>
        <div class="price">6800万円</div>
        <div class="related-properties">
          <h1>お探しの物件は見つかりませんでした（関連物件欄）</h1>
          <div>掲載が終了したか、成約済みになった可能性があります</div>
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    # 例外が起きないこと
    ParserBase._raise_if_listing_ended(soup, "https://example.com/related-noise")


@pytest.mark.asyncio
async def test_parse_property_detail_page_raises_listing_ended():
    """parsePropertyDetailPage の実行時に掲載終了ページなら即座に ListingEndedException が送出されること"""
    parser = MitsuiMansionParser()
    ended_html = """
    <html>
      <head><title>三井の物件詳細</title></head>
      <body>
        <div class="message">お探しの物件は、掲載が終了いたしました。</div>
      </body>
    </html>
    """.encode()
    mock_session = MagicMock()
    with patch.object(parser, "_getContent", new_callable=AsyncMock, return_value=ended_html):
        with pytest.raises(ListingEndedException):
            await parser.parsePropertyDetailPage(mock_session, "https://www.rehouse.co.jp/mansion/bkdetail/12345/")

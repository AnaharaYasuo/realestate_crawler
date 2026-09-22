# -*- coding: utf-8 -*-
"""Homes tochi on toushi.homes must stay HomesTochi (Issue #317)."""
import pytest
from unittest.mock import AsyncMock, patch

from package.models.homes import HomesTochi, HomesInvestmentApartment
from package.parser.homesParser import HomesTochiParser
from package.utils.property_type_detector import PropertyTypeDetector
from package.utils.url_router import UrlRouter


def test_detector_prefers_title_baichi_over_toushi_chrome_yield():
    """投資ポータル共通ナビの「利回り」よりタイトルの売地を優先する。"""
    url = "https://toushi.homes.co.jp/bukkendetail/index/4725481/"
    title = "八王子市大和田町一丁目　売地｜LIFULL HOME'S 不動産投資"
    html_chrome = "不動産投資 利回り 検索 収益物件一覧 オーナーチェンジ以外の土地も掲載"
    assert PropertyTypeDetector.detect(url=url, title=title, html_text=html_chrome) == "tochi"


def test_detector_title_with_blank_rimawari_label_stays_tochi():
    """タイトルに空の利回り表記があっても売地なら tochi。"""
    title = "八王子市大和田町一丁目　売地 (利回り: - 価格: 2,380万円)"
    assert PropertyTypeDetector.detect(
        url="https://toushi.homes.co.jp/bukkendetail/index/4725481/",
        title=title,
    ) == "tochi"


def test_detector_live_homes_toushi_land_title_is_tochi():
    """実際のホームズ投資ポータル土地タイトル（利回り未定・収益物件文言あり）は tochi。"""
    title = (
        "【ホームズ】東京都八王子市の投資用土地・事業用土地 (利回り: 未定 価格: 2,380万円) "
        "八王子市大和田町一丁目　売地。不動産投資・収益物件を検索するなら【LIFULL HOME'S 不動産投資】"
    )
    specs = {"種別": "土地", "利回り": "未定", "表面利回り": "未定", "価格": "2,380万円"}
    assert PropertyTypeDetector.detect(
        url="https://toushi.homes.co.jp/bukkendetail/index/4725481/",
        title=title,
        specs=specs,
    ) == "tochi"


def test_detector_empty_yield_row_in_specs_is_not_apartment():
    """スペック表に空の利回り行があっても投資判定しない。"""
    specs = {"種別": "売地", "利回り": "-", "土地面積": "120.5㎡"}
    assert PropertyTypeDetector.detect(specs=specs, title="練馬区 売地") == "tochi"


def test_detector_positive_gross_yield_beats_baichi_title():
    """売地タイトルでも正の grossYield があれば投資アパート扱い。"""
    assert PropertyTypeDetector.detect(
        title="八王子市 売地",
        specs={"grossYield": "5.0%", "種別": "土地"},
    ) == "apartment"


def test_url_router_resolves_toushi_homes_tochi():
    url = "https://toushi.homes.co.jp/bukkendetail/index/4725481/"
    route = UrlRouter.resolve(url, property_type="tochi")
    assert route is not None
    assert route["parser_cls"] == "HomesTochiParser"
    parser = UrlRouter.create_parser(url, property_type="tochi")
    assert isinstance(parser, HomesTochiParser)


@pytest.mark.asyncio
async def test_homes_tochi_parser_does_not_switch_to_investment(caplog):
    """HomesTochiParser が売地詳細で Investment に切り替わらないこと。"""
    url = "https://toushi.homes.co.jp/bukkendetail/index/4725481/"
    html = """
    <html>
    <head><title>八王子市大和田町一丁目　売地</title></head>
    <body>
        <nav>不動産投資 利回り 検索</nav>
        <h1>八王子市大和田町一丁目　売地</h1>
        <td class="prg-priceTableItem">2,380万円</td>
        <td class="prg-nameTableItem">八王子市大和田町一丁目　売地</td>
        <table>
            <tr><th>種別</th><td>売地</td></tr>
            <tr><th>利回り</th><td>-</td></tr>
            <tr><th>土地面積</th><td>120.55㎡</td></tr>
            <tr><th>所在地</th><td>東京都八王子市大和田町</td></tr>
        </table>
    </body>
    </html>
    """.encode("utf-8")

    parser = HomesTochiParser()
    session = AsyncMock()
    with patch.object(parser, "_getContent", return_value=html):
        with caplog.at_level("INFO"):
            item = await parser.parsePropertyDetailPage(session, url)

    assert isinstance(item, HomesTochi)
    assert not isinstance(item, HomesInvestmentApartment)
    assert "[PropertyTypeSwitch]" not in caplog.text

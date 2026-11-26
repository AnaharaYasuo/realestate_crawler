# -*- coding: utf-8 -*-
from decimal import Decimal
import inspect
import pytest

from package.parser.baseParser import InvestmentParserBase, RateLimitedException
from package.utils.url_router import UrlRouter


def test_kenbiya_parser_inherits_investment_base():
    from package.parser.kenbiyaParser import KenbiyaInvestmentApartmentParser

    assert issubclass(KenbiyaInvestmentApartmentParser, InvestmentParserBase)
    # Ensure all abstract methods are implemented
    assert not inspect.isabstract(KenbiyaInvestmentApartmentParser)


def test_url_router_kenbiya_resolution():
    routes = [
        ("https://www.kenbiya.com/pp1/s/tokyo/adachi-ku/re_47223989xb/", "kenbiya", "mansion", "KenbiyaMansionParser", "KenbiyaMansion"),
        ("https://www.kenbiya.com/pp2/s/tokyo/setagaya-ku/re_4721854dw3/", "kenbiya", "apartment", "KenbiyaInvestmentApartmentParser", "KenbiyaInvestmentApartment"),
        ("https://www.kenbiya.com/pp3/s/tokyo/adachi-ku/re_4721852cvo/", "kenbiya", "apartment", "KenbiyaInvestmentBuildingParser", "KenbiyaInvestmentBuilding"),
        ("https://www.kenbiya.com/pp4/s/tokyo/adachi-ku/re_4720631znv/", "kenbiya", "apartment", "KenbiyaInvestmentBuildingParser", "KenbiyaInvestmentBuilding"),
        ("https://www.kenbiya.com/pp8/s/tokyo/adachi-ku/re_4720946geb/", "kenbiya", "kodate", "KenbiyaKodateParser", "KenbiyaKodate"),
        ("https://www.kenbiya.com/pp5/s/tokyo/adachi-ku/re_4718878jfv/", "kenbiya", "tochi", "KenbiyaTochiParser", "KenbiyaTochi"),
    ]
    for url, site, ptype, parser_name, model_name in routes:
        route = UrlRouter.resolve(url)
        assert route is not None, f"Failed to route {url}"
        assert route["site"] == site
        assert route["property_type"] == ptype
        assert route["parser_cls"] == parser_name
        assert route["model_cls"] == model_name


def test_kenbiya_parser_edge_cases():
    from package.parser.kenbiyaParser import KenbiyaMansionParser, KenbiyaTochiParser

    m_parser = KenbiyaMansionParser()
    # Test _parseMadori variations
    assert m_parser._parseMadori(None, {"間取り": ""}) == ""
    assert m_parser._parseMadori(None, {"間取り": "ワンルーム 南向き"}) == "ワンルーム"
    assert m_parser._parseMadori(None, {"間取り": "3LDK 南向き"}) == "3LDK"
    assert m_parser._parseMadori(None, {"間取り": "その他詳細 2DK"}) == "2DK"
    assert m_parser._parseMadori(None, {"間取り": "不明フォーマット"}) == "不明フォーマット"

    # Test _parseFloor and _parseTotalFloor variations
    assert m_parser._parseFloor(None, {"階数": "所在階 4階"}) == 4
    assert m_parser._parseFloor(None, {}) is None
    assert m_parser._parseTotalFloor(None, {"総階数": "地上10階"}) == 10
    assert m_parser._parseTotalFloor(None, {}) is None

    # Test _parseSenyuMenseki and _parseBalconyMenseki variations
    assert m_parser._parseSenyuMenseki(None, {"専有面積": ""}) is None
    assert m_parser._parseSenyuMenseki(None, {"専有面積": "55.4㎡"}) == Decimal("55.4")
    assert m_parser._parseBalconyMenseki(None, {"専有面積": "55.4㎡"}) is None

    # Test _parseMaguchi variations
    t_parser = KenbiyaTochiParser()
    assert t_parser._parseMaguchi(None, {"接道状況": "間口 8.5m 公道"}) == Decimal("8.5")
    assert t_parser._parseMaguchi(None, {}) is None


@pytest.mark.asyncio
async def test_kenbiya_get_content_429_rate_limited():
    """HTTP 429が連続した場合、RateLimitedException が送出されること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from package.parser.baseParser import RateLimitedException
    from unittest.mock import AsyncMock, MagicMock

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    parser.MAX_CONSECUTIVE_TIMEOUTS = 2

    mock_resp = MagicMock()
    mock_resp.status = 429

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock()

    with pytest.raises(RateLimitedException) as excinfo:
        await parser._getContent(mock_session, "https://www.kenbiya.com/test")

    assert "rate limited (429)" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_kenbiya_user_agent_rotation():
    """リトライ毎に異なる最新ブラウザの User-Agent が適用されること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from unittest.mock import AsyncMock, MagicMock

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    parser.MAX_CONSECUTIVE_TIMEOUTS = 3

    recorded_uas = []

    def mock_get(url, headers=None, timeout=None):
        recorded_uas.append(headers.get("User-Agent"))
        mock_resp = MagicMock()
        mock_resp.status = 429
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock()
        return cm

    mock_session = MagicMock()
    mock_session.get = mock_get

    try:
        await parser._getContent(mock_session, "https://www.kenbiya.com/test")
    except RateLimitedException:
        pass

    assert len(recorded_uas) == 3
    assert len(set(recorded_uas)) > 1
    assert any("Chrome/13" in ua for ua in recorded_uas)


@pytest.mark.asyncio
async def test_kenbiya_user_agent_rotation_across_calls():
    """複数回の独立した _getContent 呼び出しにおいても User-Agent が切り替わること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from unittest.mock import AsyncMock, MagicMock

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    recorded_uas = []

    def mock_get(url, headers=None, timeout=None):
        recorded_uas.append(headers.get("User-Agent"))
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"<html></html>")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock()
        return cm

    mock_session = MagicMock()
    mock_session.get = mock_get

    for _ in range(3):
        await parser._getContent(mock_session, "https://www.kenbiya.com/test")

    assert len(recorded_uas) == 3
    # 呼び出しを跨いでも3回すべて異なるUAが選択されること
    assert len(set(recorded_uas)) == 3


@pytest.mark.asyncio
async def test_kenbiya_get_content_404_listing_ended():
    """404 / 410 応答時に ListingEndedException が送出されること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from package.parser.baseParser import ListingEndedException
    from unittest.mock import AsyncMock, MagicMock

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    mock_resp = MagicMock()
    mock_resp.status = 404
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with pytest.raises(ListingEndedException):
        await parser._getContent(mock_session, "https://www.kenbiya.com/test_404")


@pytest.mark.asyncio
async def test_kenbiya_get_content_500_server_busy():
    """500 / 503 応答時に ServerBusyException が送出されること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from package.parser.baseParser import ServerBusyException
    from unittest.mock import AsyncMock, MagicMock

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    mock_resp = MagicMock()
    mock_resp.status = 503
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with pytest.raises(ServerBusyException):
        await parser._getContent(mock_session, "https://www.kenbiya.com/test_503")


@pytest.mark.asyncio
async def test_kenbiya_get_content_generic_error():
    """403 (WAFブロック) 時に ServerBusyException が送出されて即座に次ジョブへ移ること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from package.parser.baseParser import ServerBusyException
    from unittest.mock import AsyncMock, MagicMock, patch

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    parser = ConcreteKenbiyaParser()
    mock_resp = MagicMock()
    mock_resp.status = 403
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch.object(parser, "_try_playwright_on_403", AsyncMock(return_value=None)):
        with pytest.raises(ServerBusyException):
            await parser._getContent(mock_session, "https://www.kenbiya.com/test_403")


@pytest.mark.asyncio
async def test_kenbiya_user_agent_rotation_across_subclasses():
    """異なる具象パーサーサブクラス間でも共有カウンターで User-Agent がローテーションすること"""
    from package.parser.kenbiyaParser import KenbiyaInvestmentApartmentParser, KenbiyaMansionParser
    from unittest.mock import AsyncMock, MagicMock

    parser1 = KenbiyaInvestmentApartmentParser()
    parser2 = KenbiyaMansionParser()

    recorded_uas = []

    def mock_get(url, headers=None, timeout=None):
        recorded_uas.append(headers.get("User-Agent"))
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"<html></html>")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    mock_session = MagicMock()
    mock_session.get = mock_get

    # 1つ目のパーサーで実行
    await parser1._getContent(mock_session, "https://www.kenbiya.com/test_p1")
    # 2つ目の異なるパーサーで実行
    await parser2._getContent(mock_session, "https://www.kenbiya.com/test_p2")

    assert len(recorded_uas) == 2
    # サブクラスが異なっても直前のUAを引き継がず次の異なるUAが選択されること
    assert recorded_uas[0] != recorded_uas[1]


def test_kenbiya_specs_not_overwritten_by_glossary():
    import datetime
    from bs4 import BeautifulSoup
    from package.parser.kenbiyaParser import KenbiyaInvestmentApartmentParser
    from package.models.kenbiya import KenbiyaInvestmentApartment

    html = """
    <html>
      <body>
        <div class="property">
          <dl>
            <dt>物件名</dt><dd>サンマイト谷原</dd>
            <dt>価格</dt><dd>2,900万円</dd>
            <dt>築年月</dt><dd>1991年7月（築35年）</dd>
            <dt>建物構造/階数</dt><dd>木造2階建</dd>
          </dl>
        </div>
        <div class="box_outline">
          <dl>
            <dt>築年月</dt><dd>建物が完成した年月を表示。新築の場合は新築マークを表示。</dd>
            <dt>建物構造/階数</dt><dd>建物の主となる構造、階建、総戸数を表示。区分所有物件は該当する階まで。</dd>
          </dl>
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = KenbiyaInvestmentApartmentParser()
    specs = parser._get_specs(soup)

    # 1. specs["築年月"] が用語解説で上書きされていないこと
    assert "築年月" in specs
    assert "建物が完成した年月" not in specs["築年月"]
    assert "1991年7月" in specs["築年月"]

    # 2. モデルの chikunengetsu が 1991-07-01 にパースされること
    item = KenbiyaInvestmentApartment()
    item.pageUrl = "https://www.kenbiya.com/pp2/s/saitama/kasukabe-shi/re_4723873c7j/"
    item = parser._parsePropertyDetailPage(item, soup)
    assert item.chikunengetsu == datetime.date(1991, 7, 1)


def test_kenbiya_price_fallback_selector():
    from bs4 import BeautifulSoup
    from package.parser.kenbiyaParser import KenbiyaMansionParser

    html = """
    <html>
      <body>
        <div class="aside-unrelated">
          <span class="price">9,999万円</span>
        </div>
        <div class="property">
          <span class="price">4,580万円</span>
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = KenbiyaMansionParser()
    assert parser._parsePrice(soup) == 45800000
    assert parser._parsePriceStr(soup) == "4,580万円"



def test_kenbiya_impersonate_profiles_and_accept_languages():
    import importlib.util
    from package.parser.kenbiyaParser import KenbiyaMansionParser
    assert "safari15_5" in KenbiyaMansionParser._IMPERSONATE_PROFILES
    assert "edge101" in KenbiyaMansionParser._IMPERSONATE_PROFILES
    assert len(KenbiyaMansionParser._IMPERSONATE_PROFILES) >= 20
    assert len(KenbiyaMansionParser._ACCEPT_LANGUAGES) >= 2
    if importlib.util.find_spec("curl_cffi") is not None:
        from curl_cffi.requests import AsyncSession
        for profile in KenbiyaMansionParser._IMPERSONATE_PROFILES:
            session = AsyncSession(impersonate=profile)
            assert session is not None


def test_kenbiya_madori_fallback_key():
    """スペック表キーが「間取」の場合でも間取りが抽出されることを検証 (Issue #1718, #1721)"""
    from bs4 import BeautifulSoup
    from package.parser.kenbiyaParser import KenbiyaMansionParser, KenbiyaKodateParser

    html = "<html><body><table><tr><th>間取</th><td>3LDK</td></tr></table></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert KenbiyaMansionParser()._parseMadori(soup) == "3LDK"
    assert KenbiyaKodateParser()._parseMadori(soup) == "3LDK"


@pytest.mark.asyncio
async def test_kenbiya_429_triggers_playwright_fallback(monkeypatch):
    """429応答時にPlaywrightフォールバックが呼ばれることを検証"""
    from unittest.mock import AsyncMock, MagicMock
    import aiohttp
    from package.parser.kenbiyaParser import KenbiyaMansionParser

    parser = KenbiyaMansionParser()
    fake_session = MagicMock(spec=aiohttp.ClientSession)
    fake_resp = MagicMock(spec=aiohttp.ClientResponse)
    fake_resp.status = 429

    monkeypatch.setattr(parser, "_fetch_with_playwright", AsyncMock(return_value=b"<html><body>OK</body></html>"))
    res = await parser._handle_response_or_403(fake_session, fake_resp, "https://www.kenbiya.com/pp1/s/tokyo/re_1/", 0, 3)
    assert res == b"<html><body>OK</body></html>"


@pytest.mark.asyncio
async def test_kenbiya_fetch_with_playwright_visits_home_first(monkeypatch):
    """_fetch_with_playwrightが対象URL遷移前に健美家トップへアクセスしてCookieを生成することを検証"""
    from unittest.mock import AsyncMock, MagicMock
    from package.parser.kenbiyaParser import KenbiyaMansionParser

    visited = []
    fake_page = MagicMock()

    async def fake_goto(url, **kwargs):
        visited.append(url)

    fake_page.goto = AsyncMock(side_effect=fake_goto)
    fake_page.route = AsyncMock()
    fake_page.wait_for_timeout = AsyncMock()
    fake_page.content = AsyncMock(return_value="<html><body>OK</body></html>")
    fake_page.close = AsyncMock()

    fake_context = MagicMock()
    fake_context.add_init_script = AsyncMock()
    fake_context.new_page = AsyncMock(return_value=fake_page)
    fake_context.close = AsyncMock()

    fake_browser = MagicMock()
    fake_browser.new_context = AsyncMock(return_value=fake_context)
    fake_browser.close = AsyncMock()

    fake_pw = MagicMock()
    fake_pw.chromium.launch = AsyncMock(return_value=fake_browser)

    class FakeAsyncPlaywright:
        async def __aenter__(self):
            return fake_pw

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("playwright.async_api.async_playwright", lambda: FakeAsyncPlaywright())
    res = await KenbiyaMansionParser()._fetch_with_playwright("https://www.kenbiya.com/pp1/s/tokyo/re_1/")
    assert res == b"<html><body>OK</body></html>"
    assert visited == ["https://www.kenbiya.com/", "https://www.kenbiya.com/pp1/s/tokyo/re_1/"]


def test_kenbiya_traffic_fallback_and_invest_kodate_validation():
    """交通フォールバック（アクセス/最寄駅）と投資用戸建・区分マンションの間取り・交通許容テスト"""
    from bs4 import BeautifulSoup
    from decimal import Decimal
    from package.parser.kenbiyaParser import KenbiyaMansionParser
    from package.models.kenbiya import KenbiyaMansion, KenbiyaKodate
    from package.utils.data_validator import PropertyDataValidator, ERR_MISSING_MADORI, ERR_MISSING_TRAFFIC

    html = """
    <html><body><div class="property"><dl>
      <dt>物件名</dt><dd>テスト区分マンション</dd>
      <dt>価格</dt><dd>1,500万円</dd>
      <dt>アクセス</dt><dd>JR中央線 三鷹駅 徒歩5分</dd>
      <dt>築年月</dt><dd>1995年3月</dd>
      <dt>専有面積</dt><dd>20.5㎡</dd>
    </dl></div></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = KenbiyaMansionParser()
    item = KenbiyaMansion()
    parser._parsePropertyDetailPage(item, soup)
    assert item.station1 == "三鷹"
    assert item.walkMinutes1 == 5

    kodate = KenbiyaKodate()
    kodate.price = 2000
    kodate.address = "神奈川県平塚市"
    kodate.grossYield = Decimal("8.5")
    kodate.tochiMenseki = Decimal("100.0")
    kodate.tatemonoMenseki = Decimal("80.0")
    kodate.chikunengetsu = "2000-01-01"
    reasons = []
    PropertyDataValidator._check_common_required(kodate, "kodate", reasons)
    PropertyDataValidator._check_madori_and_age(kodate, reasons)
    assert ERR_MISSING_MADORI not in reasons
    assert ERR_MISSING_TRAFFIC in reasons


@pytest.mark.asyncio
async def test_kenbiya_cross_process_throttle_shares_state(tmp_path, monkeypatch):
    """プロセス間共有ファイルロックで送信間隔が共有状態ファイルに記録・適用されること"""
    from unittest.mock import AsyncMock, patch
    from package.parser.kenbiyaParser import KenbiyaParserBase

    state_file = tmp_path / "kenbiya_rate_limit.json"
    monkeypatch.setenv("KENBIYA_THROTTLE_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_CROSS_PROCESS_LOCK_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_MIN_INTERVAL", "1.0")
    monkeypatch.setenv("KENBIYA_RATE_LIMIT_STATE_FILE", str(state_file))

    sleep_mock = AsyncMock()
    with patch("package.parser.kenbiyaParser.asyncio.sleep", sleep_mock), patch(
        "package.parser.kenbiyaParser.random.uniform", return_value=1.5
    ):
        await KenbiyaParserBase._throttle_before_request()
        await KenbiyaParserBase._throttle_before_request()

    assert state_file.exists()
    # 2回目の呼び出しは 1.0 + 1.5 = 2.5s 近いスリープが要求される
    assert sleep_mock.await_count >= 1
    assert sleep_mock.await_args_list[-1].args[0] >= 2.0


@pytest.mark.asyncio
async def test_kenbiya_503_shared_circuit_breaker_stops_other_requests(
    tmp_path, monkeypatch
):
    """503検知時に共有サーキットブレーカーが開き、後続リクエストが即座にServerBusyExceptionで停止すること"""
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from package.parser.baseParser import ServerBusyException

    state_file = tmp_path / "kenbiya_503_state.json"
    monkeypatch.setenv("KENBIYA_THROTTLE_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_CROSS_PROCESS_LOCK_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_503_CIRCUIT_COOLDOWN_SEC", "60")
    monkeypatch.setenv("KENBIYA_RATE_LIMIT_STATE_FILE", str(state_file))

    from unittest.mock import patch

    with patch.object(KenbiyaParserBase, "_disconnect_pppoe_on_503") as mock_disconnect:
        KenbiyaParserBase._record_503_circuit_open("https://www.kenbiya.com/pp1/s/tokyo/n-49/")
        # 既にサーキット開放中なら2回目は切断を重複実行しない
        KenbiyaParserBase._record_503_circuit_open("https://www.kenbiya.com/pp1/s/tokyo/n-50/")
        mock_disconnect.assert_called_once_with("https://www.kenbiya.com/pp1/s/tokyo/n-49/")

    with pytest.raises(ServerBusyException, match="shared 503 circuit breaker active"):
        await KenbiyaParserBase._throttle_before_request()


@pytest.mark.asyncio
async def test_kenbiya_global_rpm_cap_and_long_pause(tmp_path, monkeypatch):
    """大量件数クロール時にグローバルRPM上限と定期ロングポーズが発動すること"""
    from unittest.mock import AsyncMock, patch
    from package.parser.kenbiyaParser import KenbiyaParserBase

    state_file = tmp_path / "kenbiya_rpm_state.json"
    monkeypatch.setenv("KENBIYA_THROTTLE_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_CROSS_PROCESS_LOCK_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_MIN_INTERVAL", "0.5")
    monkeypatch.setenv("KENBIYA_GLOBAL_MAX_RPM", "2")
    monkeypatch.setenv("KENBIYA_LONG_PAUSE_EVERY", "2")
    monkeypatch.setenv("KENBIYA_LONG_PAUSE_SEC", "10")
    monkeypatch.setenv("KENBIYA_RATE_LIMIT_STATE_FILE", str(state_file))

    sleep_mock = AsyncMock()
    with patch("package.parser.kenbiyaParser.asyncio.sleep", sleep_mock), patch(
        "package.parser.kenbiyaParser.random.uniform", return_value=1.0
    ):
        await KenbiyaParserBase._throttle_before_request()  # 1回目
        await KenbiyaParserBase._throttle_before_request()  # 2回目 -> ロングポーズ発動 (+10s以上)
        await KenbiyaParserBase._throttle_before_request()  # 3回目 -> RPM=2超過 -> 60秒ウィンドウ待機

    sleeps = [call.args[0] for call in sleep_mock.await_args_list]
    # 2回目でロングポーズ（10s以上）、3回目でRPMウィンドウ待機（40s以上）が要求される
    assert any(s >= 10.0 for s in sleeps)
    assert sleeps[-1] >= 40.0


@pytest.mark.asyncio
async def test_kenbiya_503_triggers_pppoe_recovery_and_resumes_in_place(
    tmp_path, monkeypatch
):
    """503受信時にプロセスを終了せず、PPPoE解放・指定時間スリープ・再接続後に同一URLを再開できること"""
    from unittest.mock import AsyncMock, MagicMock, patch
    from package.parser.kenbiyaParser import KenbiyaParserBase

    class ConcreteKenbiyaParser(KenbiyaParserBase):
        def createEntity(self):
            return None

    state_file = tmp_path / "kenbiya_503_recovery_state.json"
    monkeypatch.setenv("KENBIYA_THROTTLE_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_CROSS_PROCESS_LOCK_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_MIN_INTERVAL", "0.1")
    monkeypatch.setenv("KENBIYA_GLOBAL_MAX_RPM", "100")
    monkeypatch.setenv("KENBIYA_LONG_PAUSE_EVERY", "0")
    monkeypatch.setenv("KENBIYA_PPPOE_ROTATE_WAIT_SEC", "1200")
    monkeypatch.setenv("KENBIYA_RATE_LIMIT_STATE_FILE", str(state_file))

    parser = ConcreteKenbiyaParser()
    call_count = 0

    def mock_get(url, headers=None, timeout=None):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        if call_count == 1:
            mock_resp.status = 503
            mock_resp.read = AsyncMock(return_value=b"Service Unavailable")
        else:
            mock_resp.status = 200
            mock_resp.read = AsyncMock(return_value=b"<html>ok</html>")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    mock_session = MagicMock()
    mock_session.get = mock_get

    sleep_mock = AsyncMock()
    rotate_mock = AsyncMock()
    with patch("package.parser.kenbiyaParser.asyncio.sleep", sleep_mock), patch.object(
        KenbiyaParserBase, "_rotate_pppoe_ip", rotate_mock
    ):
        body = await parser._getContent(mock_session, "https://www.kenbiya.com/pp1/s/tokyo/n-56/")

    assert body == b"<html>ok</html>"
    assert call_count == 2
    assert rotate_mock.await_count == 1
    assert rotate_mock.await_args.args[0] == "https://www.kenbiya.com/pp1/s/tokyo/n-56/"
    assert rotate_mock.await_args.args[1] == 1200.0


def test_kenbiya_rotation_remaining_and_fire_and_forget_timeout_extension(
    tmp_path, monkeypatch
):
    """PPPoEローテーション中は残り秒数を返し、fire-and-forget待機タイムアウトが自動延長されること (Issue #1788)"""
    import json
    import time
    from unittest.mock import patch
    from package.parser.kenbiyaParser import KenbiyaParserBase
    from package.api import api as api_mod

    state_file = tmp_path / "kenbiya_rot_timeout.json"
    monkeypatch.setenv("KENBIYA_THROTTLE_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_CROSS_PROCESS_LOCK_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_RATE_LIMIT_STATE_FILE", str(state_file))

    state_file.write_text(
        json.dumps({"rotating_until": time.time() + 120.0}), encoding="utf-8"
    )
    assert KenbiyaParserBase.get_active_rotation_remaining_seconds() > 100.0
    assert api_mod._is_pppoe_rotation_active() is True

    # ローテーション中は短い timeout (0.05s) でも即タイムアウトせず、完了判定で正常終了すること
    calls = {"n": 0}

    def fake_check(*args, **kwargs):
        calls["n"] += 1
        return (calls["n"] >= 3, args[2], 0, (), False)

    with patch.object(api_mod, "_check_and_log_wait_progress", side_effect=fake_check), patch.object(
        api_mod, "_check_wait_results"
    ) as mock_check_results, patch.object(api_mod.time, "sleep"):
        api_mod._wait_for_active_fire_and_forget_threads(timeout=0.05)

    assert calls["n"] == 3
    mock_check_results.assert_called_once()


def test_shared_cooldown_pause_and_resume_coordinates_all_processes(tmp_path, monkeypatch):
    """5プロセス並列時の定期クールダウンが共有状態ファイル経由で一体連動すること"""
    from unittest.mock import patch
    from package.api import kenbiya as kenbiya_api
    from package.parser.kenbiyaParser import KenbiyaParserBase

    state_file = tmp_path / "kenbiya_cooldown_sync.json"
    monkeypatch.setenv("KENBIYA_THROTTLE_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_CROSS_PROCESS_LOCK_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_RATE_LIMIT_STATE_FILE", str(state_file))
    kenbiya_api._cooldown_leader_hosts.clear()

    # 全5種別の詳細クラスが _KenbiyaDetailBase を継承してクールダウンフックを共有していること
    for cls in (
        kenbiya_api.ParseKenbiyaMansionDetailFuncAsync,
        kenbiya_api.ParseKenbiyaKodateDetailFuncAsync,
        kenbiya_api.ParseKenbiyaTochiDetailFuncAsync,
        kenbiya_api.ParseKenbiyaInvestApartmentDetailFuncAsync,
        kenbiya_api.ParseKenbiyaInvestBuildingDetailFuncAsync,
    ):
        assert issubclass(cls, kenbiya_api._KenbiyaDetailBase)

    ssh_cmds = []
    with patch.object(kenbiya_api, "_run_router_ssh", side_effect=lambda cmd: ssh_cmds.append(cmd)), patch.object(
        kenbiya_api.time, "sleep"
    ), patch.object(kenbiya_api.requests, "get", side_effect=RuntimeError("skip network")):
        # 1つ目のプロセス（リーダー）が ifdown を実行し rotating_until を設定
        kenbiya_api._kenbiya_on_pause("www.kenbiya.com")
        assert ssh_cmds == ["ifdown wan_pppoe"]
        assert KenbiyaParserBase.get_active_rotation_remaining_seconds() > 0.0

        # 2つ目のプロセス（フォロワー）は重複 ifdown を行わない
        assert KenbiyaParserBase.begin_shared_cooldown_pause(60.0) is False
        assert ssh_cmds == ["ifdown wan_pppoe"]

        # リーダーが復帰時に ifup を実行し rotating_until を解除
        kenbiya_api._kenbiya_on_resume("www.kenbiya.com")
        assert ssh_cmds == [
            "ifdown wan_pppoe",
            "ifup wan_pppoe; sleep 5; /etc/init.d/vpn-policy-routing reload",
        ]
        assert KenbiyaParserBase.get_active_rotation_remaining_seconds() == 0.0


def test_shared_cooldown_window_start_reset_prevents_back_to_back_cooldown(tmp_path, monkeypatch):
    """リーダー復帰時に共有 cooldown_window_start が更新され、フォロワーの連続クールダウン発火を防ぐこと (#1820)"""
    import time
    from package.api.api import CrawlCooldownController
    from package.parser.kenbiyaParser import KenbiyaParserBase

    state_file = tmp_path / "kenbiya_window_reset.json"
    monkeypatch.setenv("KENBIYA_THROTTLE_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_CROSS_PROCESS_LOCK_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_RATE_LIMIT_STATE_FILE", str(state_file))

    # リーダーが復帰完了した時点で共有 cooldown_window_start が現在時刻に更新される
    before = time.time()
    KenbiyaParserBase.end_shared_cooldown_pause()
    shared_start = KenbiyaParserBase.get_shared_cooldown_window_start()
    assert shared_start >= before

    # フォロワーのローカルタイマーは既に 3600s 超過している状態
    ctrl = CrawlCooldownController()
    assert ctrl.get_wait_seconds("www.kenbiya.com", work_seconds=3600.0, rest_seconds=1800.0, now=100.0) == 0.0
    # 共有 window_start を渡すと、直近復帰済みのため再クールダウンが発火しない（wait == 0.0）
    wait = ctrl.get_wait_seconds(
        "www.kenbiya.com",
        work_seconds=3600.0,
        rest_seconds=1800.0,
        now=3800.0,
        shared_window_start=shared_start,
    )
    assert wait == 0.0


def test_503_pppoe_rotation_repeats_until_ip_changes(tmp_path, monkeypatch):
    """503時のwan_pppoeローテーションが5分単位でIPが変わるまで切断→待機→再接続を繰り返すこと"""
    import asyncio
    from unittest.mock import AsyncMock, patch
    from package.api import kenbiya as kenbiya_api
    from package.parser.kenbiyaParser import KenbiyaParserBase

    state_file = tmp_path / "kenbiya_503_ip_loop.json"
    monkeypatch.setenv("KENBIYA_THROTTLE_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_CROSS_PROCESS_LOCK_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_503_PPPOE_RECOVERY_DISABLED", "false")
    monkeypatch.setenv("KENBIYA_RATE_LIMIT_STATE_FILE", str(state_file))
    monkeypatch.delenv("KENBIYA_PPPOE_ROTATE_WAIT_SEC", raising=False)

    ssh_cmds = []
    # 初回IP取得: 1.2.3.4 -> 1回目再接続後: 1.2.3.4(不変) -> 2回目再接続後: 5.6.7.8(変更)
    ips = iter(["1.2.3.4", "1.2.3.4", "5.6.7.8"])
    sleep_mock = AsyncMock()

    with patch.object(kenbiya_api, "_run_router_ssh", side_effect=lambda cmd: ssh_cmds.append(cmd) or ""), patch.object(
        kenbiya_api, "_get_wan_pppoe_ip", side_effect=lambda: next(ips)
    ), patch.object(kenbiya_api, "_ensure_proxysql_tunnel_ready", return_value=True) as mock_proxysql, patch(
        "package.parser.kenbiyaParser.asyncio.sleep", sleep_mock
    ):
        handled = asyncio.run(
            KenbiyaParserBase._handle_503_with_pppoe_recovery("https://www.kenbiya.com/pp1/s/tokyo/")
        )

    assert handled is True
    mock_proxysql.assert_called_once()
    assert ssh_cmds == [
        "ifdown wan_pppoe",
        "ifup wan_pppoe; sleep 5; /etc/init.d/vpn-policy-routing reload",
        "ifdown wan_pppoe",
        "ifup wan_pppoe; sleep 5; /etc/init.d/vpn-policy-routing reload",
    ]
    assert [call.args[0] for call in sleep_mock.call_args_list] == [600.0, 600.0]
    assert KenbiyaParserBase.get_active_rotation_remaining_seconds() == 0.0


def test_ensure_proxysql_tunnel_ready_starts_vm_and_tunnel(monkeypatch):
    """ProxySQL疎通不可時にVM起動およびIAPトンネル再確立を自動実行すること"""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch
    from package.api import kenbiya as kenbiya_api

    monkeypatch.delenv("IS_CLOUD", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("CLOUD_RUN_JOB", raising=False)
    monkeypatch.setenv("KENBIYA_PROXYSQL_AUTO_RECOVERY_DISABLED", "false")
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_PORT", "6033")

    # 1回目: 疎通不可 -> VM起動＆トンネル起動 -> 2回目: 疎通OK
    checks = iter([False, True])
    run_mock = MagicMock(return_value=SimpleNamespace(stdout="TERMINATED\n"))
    popen_mock = MagicMock()

    with patch.object(kenbiya_api, "_check_proxysql_select1", side_effect=lambda *a, **kw: next(checks)), patch.object(
        kenbiya_api.subprocess, "run", run_mock
    ), patch.object(kenbiya_api.subprocess, "Popen", popen_mock), patch.object(kenbiya_api.time, "sleep"):
        ok = kenbiya_api._ensure_proxysql_tunnel_ready()

    assert ok is True
    assert run_mock.call_count == 2  # describe + start
    popen_mock.assert_called_once()


def test_stale_tokyo_fallback_detection_and_cooldown_default():
    """WAF Cookie失効時の東京都1ページ目フォールバック検知と定期クールダウン10分デフォルトを検証"""
    from package.api import kenbiya as kenbiya_api
    from package.parser.kenbiyaParser import KenbiyaParserBase

    assert kenbiya_api.COOLDOWN_REST_SECONDS == 600.0

    stale_html = (
        '<html><body><h1>東京都の投資用マンション一覧</h1>'
        '<a rel="next" href="/pp1/s/tokyo/n-2/">次へ</a></body></html>'
    ).encode("utf-8")
    valid_kanagawa_html = (
        '<html><body><h1>神奈川県の投資用マンション一覧</h1>'
        '<a rel="next" href="/pp1/s/kanagawa/n-2/">次へ</a></body></html>'
    ).encode("utf-8")
    valid_tokyo_p53_html = (
        '<html><body><h1>東京都の投資用マンション一覧</h1>'
        '<a rel="next" href="/pp1/s/tokyo/n-54/">次へ</a></body></html>'
    ).encode("utf-8")

    # 正常系: 東京1ページ目、神奈川正常、東京53ページ目正常、詳細ページ
    assert KenbiyaParserBase._is_stale_tokyo_fallback("https://www.kenbiya.com/pp1/s/tokyo/", stale_html) is False
    assert KenbiyaParserBase._is_stale_tokyo_fallback("https://www.kenbiya.com/pp1/s/kanagawa/", valid_kanagawa_html) is False
    assert KenbiyaParserBase._is_stale_tokyo_fallback("https://www.kenbiya.com/pp1/s/tokyo/n-53/", valid_tokyo_p53_html) is False
    assert KenbiyaParserBase._is_stale_tokyo_fallback("https://www.kenbiya.com/pp1/s/kanagawa/yokohama-shi/re_123/", stale_html) is False

    # 異常系: 神奈川/埼玉/愛知や2ページ目以降で東京1ページ目が返された場合
    assert KenbiyaParserBase._is_stale_tokyo_fallback("https://www.kenbiya.com/pp1/s/kanagawa/", stale_html) is True
    assert KenbiyaParserBase._is_stale_tokyo_fallback("https://www.kenbiya.com/pp1/t/aichi/", stale_html) is True
    assert KenbiyaParserBase._is_stale_tokyo_fallback("https://www.kenbiya.com/pp1/s/tokyo/n-53/", stale_html) is True


@pytest.mark.asyncio
async def test_cffi_session_reuse_and_invalidation(monkeypatch):
    """curl_cffi AsyncSession が再利用され、_invalidate_waf_cookies 後に再生成されることを検証"""
    import sys
    import types
    from package.parser.kenbiyaParser import KenbiyaMansionParser, KenbiyaParserBase

    closed_sessions = []

    class _DummyAsyncSession:
        def __init__(self, impersonate=None):
            self.impersonate = impersonate
            self.cookies = {}

        async def close(self):
            closed_sessions.append(self)

    dummy_requests = types.SimpleNamespace(AsyncSession=_DummyAsyncSession)
    dummy_pkg = types.SimpleNamespace(requests=dummy_requests)
    monkeypatch.setitem(sys.modules, "curl_cffi", dummy_pkg)
    monkeypatch.setitem(sys.modules, "curl_cffi.requests", dummy_requests)

    parser = KenbiyaMansionParser()
    s1 = await parser._get_or_create_cffi_session("chrome124")
    s2 = await parser._get_or_create_cffi_session("chrome124")
    assert s1 is s2

    KenbiyaParserBase._invalidate_waf_cookies()
    s3 = await parser._get_or_create_cffi_session("chrome124")
    assert s3 is not s1
    assert closed_sessions == [s1]
    await s3.close()


def test_fire_and_forget_wait_timeout_default_is_12_hours(monkeypatch):
    """CRAWLER_FIRE_AND_FORGET_WAIT_TIMEOUT のデフォルトが 43200.0 秒（12時間）であることを検証"""
    from package.api import api as api_mod

    monkeypatch.delenv("CRAWLER_FIRE_AND_FORGET_WAIT_TIMEOUT", raising=False)
    assert api_mod._get_fire_and_forget_wait_timeout() == 43200.0













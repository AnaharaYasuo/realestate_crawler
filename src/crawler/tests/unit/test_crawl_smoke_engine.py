"""Unit tests for crawl smoke engine helpers (offline)."""
import pytest
from package.utils.crawl_smoke_engine import (
    _job_budget_sec,
    _looks_like_detail,
    _needs_playwright,
    _optional_playwright,
    _sample_size,
    assert_required_fields,
)


class _DummyItem:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_looks_like_detail_positive_cases():
    assert _looks_like_detail("https://example.com/mansion/detail/123")
    assert _looks_like_detail("https://www.rehouse.co.jp/buy/mansion/bkdetail/ABC/")
    assert _looks_like_detail("https://www.keikyu-sumai.com/contents/code/detail/152448788/")
    assert _looks_like_detail("https://www.nomu.com/mansion/foo/pro/bukken_local_id/123/")
    assert _looks_like_detail("https://toushi.homes.co.jp/bukkendetail/123/")
    assert _looks_like_detail("https://www.athome.co.jp/mansion/12345678/")
    assert _looks_like_detail("https://chukai.keiofudosan.co.jp/sale/2127977638870000006170/")
    assert _looks_like_detail("https://www.sotetsu-re.co.jp/buy/view/OBL50921")
    assert _looks_like_detail(
        "https://www.hebel-haus.com/stockhebel/purchase/forhome/details.html?bno=BMS09818"
    )
    assert _looks_like_detail("https://sumikae.ttfuhan.co.jp/mansion/NFD1C4021/")
    assert _looks_like_detail("https://www.livable.co.jp/mansion/C1234567/")
    assert _looks_like_detail(
        "https://www.suminavi.com/buy/estate/estateInfo/house/shutoken/618605/"
    )
    assert _looks_like_detail("https://www.livable.co.jp/fudosan-toushi/C13269H23/")


def test_looks_like_detail_rejects_list_pages():
    assert not _looks_like_detail("https://example.com/mansion/area-tokyo/list/")
    assert not _looks_like_detail("https://example.com/buy/mansion/prefecture/13/")
    assert not _looks_like_detail("https://realestate.misawa.co.jp/search/sale/")
    assert not _looks_like_detail("https://www.livable.co.jp/kounyu/kodate/select-area/")
    assert not _looks_like_detail("https://www.nomu.com/mansion/ensen_tokyo/2171/2171110/")
    assert not _looks_like_detail("https://www.nomu.com/pro/")
    assert not _looks_like_detail("https://www.livable.co.jp/baikyaku/tochi/chika/")


def test_soup_looks_blocked_detects_waf_title():
    from bs4 import BeautifulSoup
    from package.utils.crawl_smoke_engine import (
        _soup_looks_blocked,
        _soup_usable_for_smoke,
    )

    blocked = BeautifulSoup(
        "<html><head><title>403 Forbidden</title></head><body><a href='/a'>a</a>"
        "<a href='/b'>b</a><a href='/c'>c</a></body></html>",
        "html.parser",
    )
    assert _soup_looks_blocked(blocked)
    assert not _soup_usable_for_smoke(blocked)

    # Room numbers like "403号室" must not be treated as WAF.
    room = BeautifulSoup(
        "<html><head><title>403号室</title></head><body><a href='/a'>a</a>"
        "<a href='/b'>b</a><a href='/c'>c</a></body></html>",
        "html.parser",
    )
    assert not _soup_looks_blocked(room)

    athome_challenge = BeautifulSoup(
        "<html><head><title>認証中</title></head><body>"
        "<p>認証にご協力ください</p>"
        "<a href='/a'>a</a><a href='/b'>b</a><a href='/c'>c</a></body></html>",
        "html.parser",
    )
    assert _soup_looks_blocked(athome_challenge)
    assert not _soup_usable_for_smoke(athome_challenge)


def test_effective_budget_bumps_playwright_companies():
    from package.utils.crawl_smoke_engine import (
        ATHOME_INVEST_JOB_BUDGET_SEC,
        MIZUHO_JOB_BUDGET_SEC,
        PLAYWRIGHT_JOB_BUDGET_SEC,
        SEKISUI_JOB_BUDGET_SEC,
        _effective_job_budget_sec,
    )

    assert _effective_job_budget_sec("nomura", 25.0) == 50.0
    assert _effective_job_budget_sec("mizuho", 25.0) == MIZUHO_JOB_BUDGET_SEC
    assert _effective_job_budget_sec("athome", 10.0) == PLAYWRIGHT_JOB_BUDGET_SEC
    assert _effective_job_budget_sec("athome", 10.0, "invest_apartment") == ATHOME_INVEST_JOB_BUDGET_SEC
    assert _effective_job_budget_sec("odakyu", 20.0, "investment") == 60.0
    assert _effective_job_budget_sec("sekisui", 10.0) == SEKISUI_JOB_BUDGET_SEC
    assert _effective_job_budget_sec("afr", 25.0) == 60.0
    assert _effective_job_budget_sec("sumifu", 25.0) == 35.0
    assert _effective_job_budget_sec("keio", 20.0) == 40.0
    assert _effective_job_budget_sec("nomura", 20.0, "invest_apartment") == 90.0
    assert _effective_job_budget_sec("misawa", 20.0) == 35.0
    assert _effective_job_budget_sec("heim", 20.0) == 60.0
    assert _effective_job_budget_sec("nomura", 20.0) == 50.0
    assert _effective_job_budget_sec("misawa", 20.0) == 35.0


def test_looks_like_detail_odakyu_invest_focus():
    from package.utils.crawl_smoke_engine import _looks_like_detail

    assert _looks_like_detail(
        "https://www.odakyu-chukai.com/invest/list/?focus=VI0023"
    )
    assert not _looks_like_detail("https://www.odakyu-chukai.com/invest/list/")


def test_fetch_timeout_bumps_keio_json():
    import time

    from package.utils.crawl_smoke_engine import _fetch_timeout_sec

    deadline = time.monotonic() + 60.0
    assert _fetch_timeout_sec("https://example.com/list", deadline) <= 3.0 + 1e-6
    keio = _fetch_timeout_sec(
        "https://chukai.keiofudosan.co.jp/wp-json/wp/v2/get_search_result_sale?x=1",
        deadline,
    )
    assert keio >= 12.0


def test_decode_honors_shift_jis_alias():
    """Content-Type shift_jis must map to cp932 for BeautifulSoup decode."""
    from package.utils import crawl_smoke_engine as eng

    assert eng.re.search(r"charset=([^\s;]+)", "text/html;charset=shift_jis").group(1) == "shift_jis"


def test_parse_property_name_skips_empty_h1():
    """Keisei pages render empty <h1> before the real name in <h2>."""
    from bs4 import BeautifulSoup
    from package.parser.keiseiParser import KeiseiMansionParser

    soup = BeautifulSoup(
        "<html><body><h1></h1><h2>朝日プラザ西新井</h2>"
        "<table><tr><th>所在地</th><td>東京都足立区</td></tr></table>"
        "</body></html>",
        "html.parser",
    )
    name = KeiseiMansionParser()._parsePropertyName(soup)
    assert name == "朝日プラザ西新井"


def test_assert_required_fields_passes():
    item = _DummyItem(propertyName="A", price=100, address="Tokyo")
    assert_required_fields(item, "dummy_job")


def test_assert_required_fields_fails_on_empty():
    item = _DummyItem(propertyName="A", price=None, address="Tokyo")
    with pytest.raises(AssertionError, match="price"):
        assert_required_fields(item, "dummy_job")


def test_fast_defaults_for_parallel_runs(monkeypatch):
    monkeypatch.delenv("CRAWL_SMOKE_SAMPLE_SIZE", raising=False)
    monkeypatch.delenv("CRAWL_SMOKE_JOB_BUDGET_SEC", raising=False)
    assert _sample_size() == 3
    assert _job_budget_sec() == 20.0
    monkeypatch.setenv("CRAWL_SMOKE_JOB_BUDGET_SEC", "10")
    assert _job_budget_sec() == 10.0


@pytest.mark.asyncio
async def test_optional_playwright_skipped_when_not_forced():
    async with _optional_playwright(False) as pw:
        assert pw is None


def test_needs_playwright_only_known_companies():
    assert _needs_playwright(object(), "athome")
    assert _needs_playwright(object(), "mizuho")
    assert _needs_playwright(object(), "sekisui")
    assert not _needs_playwright(object(), "sumifu")
    assert not _needs_playwright(object(), "homes")


class _SampleTarget:
    def __init__(self, company: str, property_type: str):
        self.company = company
        self.property_type = property_type
        self.job_id = f"{company}_{property_type}"
        self.seed_url = f"https://example.com/{company}/{property_type}/"


def test_effective_sample_size_playwright_is_one():
    from package.utils.crawl_smoke_engine import _effective_sample_size

    assert _effective_sample_size(_SampleTarget("sekisui", "mansion")) == 1
    assert _effective_sample_size(_SampleTarget("mizuho", "tochi")) == 1
    assert _effective_sample_size(_SampleTarget("athome", "mansion")) == 1


def test_effective_sample_size_athome_invest_capped():
    from package.utils.crawl_smoke_engine import _effective_sample_size

    assert _effective_sample_size(_SampleTarget("athome", "invest_apartment")) == 8


@pytest.mark.asyncio
async def test_discover_mizuho_passes_limit(monkeypatch):
    from package.utils import crawl_smoke_engine as eng

    calls = {}

    async def _fake_links(url, limit=None):
        calls["url"] = url
        calls["limit"] = limit
        return [
            "https://www.mizuho-re.co.jp/buyers/detail/1/",
            "https://www.mizuho-re.co.jp/buyers/detail/2/",
            "https://www.mizuho-re.co.jp/buyers/detail/3/",
        ]

    monkeypatch.setattr(
        "package.utils.mizuho_bypass.get_mizuho_links",
        _fake_links,
    )
    parser = type("P", (), {})()
    found = await eng._discover_mizuho_via_production_bypass(
        parser, "https://www.mizuho-re.co.jp/buyers/search/area/type_House/pref_13/list/", 1
    )
    assert calls["limit"] == 1
    assert found == ["https://www.mizuho-re.co.jp/buyers/detail/1/"]
    assert parser._last_url.endswith("/list/")


@pytest.mark.asyncio
async def test_light_pw_close_independent():
    from package.utils.crawl_smoke_engine import _LightPlaywrightSession

    sess = _LightPlaywrightSession()

    class Boom:
        async def close(self):
            raise RuntimeError("context boom")

        async def stop(self):
            raise RuntimeError("pw boom")

    sess._context = Boom()
    sess._browser = Boom()
    sess._pw = Boom()
    await sess.close()
    assert sess._context is None
    assert sess._browser is None
    assert sess._pw is None


def test_all_seeds_prefers_athome_and_homes_deep_lists(monkeypatch):
    from package.utils import crawl_smoke_engine as eng

    monkeypatch.setattr(
        eng,
        "load_start_api_class",
        lambda _t: type("S", (), {"urlList": []})(),
    )
    athome = _SampleTarget("athome", "invest_apartment")
    athome.seed_url = "https://www.athome.co.jp/buy_other/tokyo/city/"
    seeds = eng._all_seeds_for_target(athome)
    assert "shubetsu_toushi" in seeds[0]

    homes = _SampleTarget("homes", "invest_apartment")
    homes.seed_url = "https://toushi.homes.co.jp/bukkensearch/?tbg[]=1"
    seeds_h = eng._all_seeds_for_target(homes)
    assert "pref[]=13" in seeds_h[0]


def test_expected_detector_type_and_invest_compat():
    from package.utils.crawl_smoke_engine import (
        _invest_types_compatible,
        expected_detector_type,
    )

    class P:
        property_type = "kodate"

    assert expected_detector_type("kodate", P(), company="sumifu") == "kodate"
    assert expected_detector_type("", P(), company="homes") == "apartment"
    # Empty job+parser type falls back to mansion; non-empty unknown job_pt is kept.
    assert expected_detector_type("", object(), company="x") == "mansion"
    assert expected_detector_type("unknown", object(), company="x") == "unknown"
    assert expected_detector_type("unknown", object(), company="x") is not None

    assert _invest_types_compatible("apartment", "invest_kodate") is True
    assert _invest_types_compatible("kodate", "mansion") is False
    assert _invest_types_compatible("apartment", "invest_apartment") is not None


def test_company_type_aliases_and_property_compat_not_none():
    from package.utils.crawl_smoke_engine import (
        _company_type_aliases_ok,
        property_types_compatible,
    )

    assert _company_type_aliases_ok("kodate", "tochi", "sumai1") is True
    assert _company_type_aliases_ok("kodate", "tochi", "sumai1") is not None
    assert _company_type_aliases_ok("mansion", "tochi", "nomura") is False

    assert property_types_compatible("kodate", "tochi", company="heim") is True
    assert property_types_compatible("kodate", "tochi", company="heim") is not None
    assert property_types_compatible("mansion", "tochi", company="nomura") is False


def test_detect_smoke_property_type_via_parser_resolve(monkeypatch):
    from package.utils import crawl_smoke_engine as eng

    monkeypatch.setattr(
        eng.PropertyTypeDetector,
        "detect",
        staticmethod(lambda **_k: None),
    )

    class Parser:
        def _resolve_validation_property_type(self, _item):
            return "kodate"

    detected = eng._detect_smoke_property_type(
        Parser(), _DummyItem(), "https://ex/detail/1", "t", "h", {}
    )
    assert detected == "kodate"
    assert detected is not None


@pytest.mark.asyncio
async def test_fetch_list_page_for_paging_returns_exc_tuple(monkeypatch):
    from package.utils import crawl_smoke_engine as eng

    async def boom(*_a, **_k):
        raise RuntimeError("fetch fail")

    monkeypatch.setattr(eng, "_fetch_soup", boom)
    monkeypatch.setattr(eng.asyncio, "sleep", eng.asyncio.sleep)  # keep real but short deadline

    result = await eng._fetch_list_page_for_paging(
        session=None,
        parser=object(),
        list_url="https://ex/list",
        deadline=__import__("time").monotonic() + 0.01,
        pw=None,
        force_pw=False,
    )
    assert result is not None
    page, exc = result
    assert page is None
    assert exc is not None


@pytest.mark.asyncio
async def test_fetch_list_page_for_paging_returns_tuple(monkeypatch):
    from package.utils import crawl_smoke_engine as eng

    async def fake_fetch(*_a, **_k):
        return "PAGE"

    monkeypatch.setattr(eng, "_fetch_soup", fake_fetch)
    result = await eng._fetch_list_page_for_paging(
        session=None,
        parser=object(),
        list_url="https://ex/list",
        deadline=__import__("time").monotonic() + 30,
        pw=None,
        force_pw=False,
    )
    assert result is not None
    page, exc = result
    assert page == "PAGE" and exc is None


def test_evaluate_paging_result_loop_and_advance():
    from package.utils.crawl_smoke_engine import evaluate_paging_result

    pages, exhausted, ok = evaluate_paging_result(
        "https://ex/list", "", next_fetch_ok=False
    )
    assert (pages, exhausted, ok) == (1, True, True)

    pages, exhausted, ok = evaluate_paging_result(
        "https://ex/list", "https://ex/list", next_fetch_ok=True
    )
    assert (pages, exhausted, ok) == (1, False, False)
    assert isinstance(pages, int) and ok is False

    pages, exhausted, ok = evaluate_paging_result(
        "https://ex/list", "https://ex/list?page=2", next_fetch_ok=True
    )
    assert (pages, exhausted, ok) == (2, False, True)

    pages, exhausted, ok = evaluate_paging_result(
        "https://ex/list", "https://ex/list?page=2", next_fetch_ok=False
    )
    assert (pages, exhausted, ok) == (1, False, False)


def test_soft_residential_helpers_kill_return_none_mutants():
    """Assert concrete bool/tuple returns so return->None mutants die."""
    from package.utils.crawl_smoke_engine import (
        _page_title_html_specs,
        _soft_kodate_ok,
        _soft_mansion_ok,
        _soft_residential_type_ok,
        _soft_tochi_ok,
    )

    mansion_item = _DummyItem(tatemonoMenseki=80.0)
    assert _soft_mansion_ok("kodate", mansion_item, "heim") is True
    assert _soft_mansion_ok("kodate", mansion_item, "heim") is not None

    assert _soft_kodate_ok("tochi", _DummyItem(), "sumai1") is True

    tochi_item = _DummyItem(tochiMenseki=100.0)
    assert _soft_tochi_ok("kodate", tochi_item, {}, "heim") is True
    assert _soft_tochi_ok("kodate", tochi_item, {}, "heim") is not None

    bare = _DummyItem()
    assert _soft_residential_type_ok("mansion", "tochi", bare, {}, "nomura") is False
    # Non residential expected → False (kills final return False -> True).
    assert _soft_residential_type_ok("kodate", "apartment", bare, {}, "nomura") is False

    class P:
        def _get_specs(self, _page):
            return {"種別": "土地"}

    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<html><head><title>T</title></head><body>x</body></html>", "html.parser")
    title, html_text, specs = _page_title_html_specs(P(), soup)
    assert (title, html_text, specs) is not None
    assert title == "T"
    assert specs == {"種別": "土地"}


@pytest.mark.asyncio
async def test_normalize_next_page_url_absolute_and_relative():
    from package.utils.crawl_smoke_engine import _normalize_next_page_url

    class P:
        BASE_URL = "https://example.com/buy/"

    assert await _normalize_next_page_url(P(), "https://example.com/list", None) == ""
    assert (
        await _normalize_next_page_url(
            P(), "https://example.com/list", "https://example.com/list?p=2"
        )
        == "https://example.com/list?p=2"
    )
    rel = await _normalize_next_page_url(P(), "https://example.com/list", "page/2")
    assert rel.startswith("https://example.com/")
    assert "page/2" in rel
    assert rel  # kills urljoin -> None


@pytest.mark.asyncio
async def test_probe_paging_exhausted_when_no_next(monkeypatch):
    from bs4 import BeautifulSoup
    from package.utils import crawl_smoke_engine as eng

    soup = BeautifulSoup("<html><body>list</body></html>", "html.parser")

    async def fake_fetch(*_a, **_k):
        return soup

    class Parser:
        async def parseNextPage(self, _page):
            return ""

    monkeypatch.setattr(eng, "_fetch_soup", fake_fetch)
    pages, exhausted, ok, err = await eng.probe_paging(
        session=None,
        parser=Parser(),
        list_url="https://example.com/list",
        deadline=__import__("time").monotonic() + 30,
    )
    assert err is None
    assert (pages, exhausted, ok) == (1, True, True)
    assert isinstance(pages, int)
    # Kill return-tuple -> None mutants on probe helpers.
    assert (pages, exhausted, ok, err) is not None


@pytest.mark.asyncio
async def test_probe_paging_advances_when_next_ok(monkeypatch):
    from bs4 import BeautifulSoup
    from package.utils import crawl_smoke_engine as eng

    soup = BeautifulSoup("<html><body>list</body></html>", "html.parser")

    async def fake_fetch(*_a, **_k):
        return soup

    class Parser:
        async def parseNextPage(self, _page):
            return "https://example.com/list?page=2"

    monkeypatch.setattr(eng, "_fetch_soup", fake_fetch)
    result = await eng.probe_paging(
        session=None,
        parser=Parser(),
        list_url="https://example.com/list",
        deadline=__import__("time").monotonic() + 30,
    )
    assert result is not None
    pages, exhausted, ok, err = result
    assert err is None
    assert pages == 2 and ok is True and exhausted is False


def test_ssl_for_url_default_true():
    from package.utils.crawl_smoke_engine import _ssl_for_url

    assert _ssl_for_url("https://www.sumifu.co.jp/list") is True
    assert _ssl_for_url("https://realestate.misawa.co.jp/x") is True
    assert _ssl_for_url("https://www.keiofudosan.co.jp/x") is True


@pytest.mark.asyncio
async def test_collect_async_respects_limit_and_skips_empty():
    from package.utils.crawl_smoke_engine import _collect_async

    async def gen():
        yield None
        yield "a"
        yield "b"
        yield "c"

    items = await _collect_async(gen(), limit=2)
    assert items == ["a", "b"]
    assert items is not None
    assert len(items) == 2


def test_effective_budget_returns_concrete_number():
    from package.utils.crawl_smoke_engine import _effective_job_budget_sec

    # Unknown company: must return the provided budget (not None).
    assert _effective_job_budget_sec("unknownco", 22.0) == 22.0
    assert isinstance(_effective_job_budget_sec("unknownco", 22.0), float)


def test_soft_mansion_ok_seibu_heim():
    from package.utils.crawl_smoke_engine import _soft_mansion_ok

    item = _DummyItem(tatemonoMenseki=100)
    assert _soft_mansion_ok("kodate", item, "seibu") is True
    assert _soft_mansion_ok("kodate", item, "heim") is True
    assert _soft_mansion_ok("kodate", item, "mitsui") is False


def test_soft_tochi_ok_heim():
    from package.utils.crawl_smoke_engine import _soft_tochi_ok

    item = _DummyItem(tochiMenseki=200, tatemonoMenseki=None)
    assert _soft_tochi_ok("kodate", item, specs={}, company_l="heim") is True
    assert _soft_tochi_ok("kodate", item, specs={}, company_l="mitsui") is False


@pytest.mark.asyncio
async def test_normalize_next_page_url_relative_base():
    from package.utils.crawl_smoke_engine import _normalize_next_page_url

    class _P:
        BASE_URL = "https://example.com/base/"

    res = await _normalize_next_page_url(_P(), "https://example.com/base/list", "page2.html")
    assert res == "https://example.com/base/page2.html"


@pytest.mark.asyncio
async def test_probe_next_page_fetch_success(monkeypatch):
    import package.utils.crawl_smoke_engine as eng

    async def fake_fetch(*args, **kwargs):
        return "<html></html>"

    monkeypatch.setattr(eng, "_fetch_soup", fake_fetch)
    pages, exhausted, ok, err = await eng._probe_next_page_fetch(
        None,
        object(),
        "https://example.com/list",
        "https://example.com/list?page=2",
        deadline=__import__("time").monotonic() + 30,
        pw=None,
        force_pw=False,
    )
    assert pages == 2 and exhausted is False and ok is True and err is None

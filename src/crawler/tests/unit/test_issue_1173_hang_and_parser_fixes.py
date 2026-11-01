import concurrent.futures
import datetime
from decimal import Decimal
from bs4 import BeautifulSoup
from django.utils import timezone
import pytest

from package.api import api
from package.api.differential import ListItem, _detect_company_and_type_from_model, _should_fetch_item
from package.models.reguide import ReguideInvestment
from package.parser.adcastParser import AdCastKodateParser
from package.parser.athomeParser import AthomeMansionParser
from package.parser.baseParser import ListingEndedException, SkipPropertyException
from package.parser.hasekoParser import HasekoMansionParser
from package.parser.heimParser import HeimKodateParser
from package.parser.homesParser import HomesInvestmentApartmentParser
from package.parser.ietanParser import IetanMansionParser
from package.parser.mitsuiParser import MitsuiInvestmentApartmentParser
from package.parser.rearieParser import RearieMansionParser
from package.parser.reguideParser import ReguideInvestmentParser
from package.parser.sumai1Parser import Sumai1InvestmentParser
from package.parser.sumifuParser import SumifuMansionParser
from package.parser.tohoParser import TohoTochiParser, check_toho_listing_ended
from package.parser.tokyuParser import TokyuKodateParser, TokyuMansionParser, TokyuTochiParser
from package.utils import converter, crawler_diagnostics
from package.utils.property_type_detector import PropertyTypeDetector
from package.utils.url_router import UrlRouter


def test_cancel_unstarted_futures_no_self_deadlock():
    """_cancel_unstarted_futures_on_stop must not deadlock when cancel() triggers done_callback."""
    fut = concurrent.futures.Future()
    api._track_fire_and_forget_future(fut)
    api._cancel_unstarted_futures_on_stop()
    assert fut.cancelled()
    with api._active_threads_lock:
        assert fut not in api._active_fire_and_forget_futures


def test_differential_price_unit_normalization():
    """Legacy DB price in 万円 (e.g. 1260) vs ListItem price in 円 (12600000) must not trigger false fetch."""
    now = timezone.now()
    assert not _should_fetch_item(
        ListItem(url="https://www.rehouse.co.jp/buy/mansion/bkdetail/F01/", price=12_600_000),
        {"price": 1260, "updateDateTime": now},
        now,
        ttl_days=7,
    )
    assert not _should_fetch_item(
        ListItem(url="https://www.rehouse.co.jp/buy/mansion/bkdetail/F02/", price=12_600_000),
        {"price": 12_600_000, "updateDateTime": now},
        now,
        ttl_days=7,
    )
    assert _should_fetch_item(
        ListItem(url="https://www.rehouse.co.jp/buy/mansion/bkdetail/F03/", price=12_600_000),
        {"price": 1300, "updateDateTime": now},
        now,
        ttl_days=7,
    )


def test_differential_detect_reguide_company():
    comp, ptype = _detect_company_and_type_from_model(ReguideInvestment)
    assert comp == "reguide"
    assert ptype == "investment"


def test_crawler_diagnostics_flushes_immediately_on_phase_transition():
    crawler_diagnostics.record_thread_activity(
        phase="detail_page_parse",
        current_url="https://example.com/1",
        company="mitsui",
        property_type="mansion",
        force_flush=True,
    )
    crawler_diagnostics.clear_thread_activity()
    # Immediately transition back to detail_page_fetch within <1s without force_flush
    crawler_diagnostics.record_thread_activity(
        phase="detail_page_fetch",
        current_url="https://example.com/2",
        company="mitsui",
        property_type="mansion",
        force_flush=False,
    )
    active = crawler_diagnostics.read_persisted_thread_states("mitsui", "mansion")
    matching = [d for d in active if d.get("current_url") == "https://example.com/2"]
    assert matching, "Phase transition from idle -> detail_page_fetch must flush to disk immediately"
    assert matching[0]["phase"] == "detail_page_fetch"
    crawler_diagnostics.clear_thread_activity()


def test_reguide_charset_and_extract_detail_urls():
    parser = ReguideInvestmentParser()
    assert parser.getCharset().lower() in ("euc-jp", "euc_jp")
    html = """
    <html><body>
      <ul id="result_list">
        <li><a href="/investment/detail/id/R00123/">物件詳細へ</a></li>
      </ul>
    </body></html>
    """
    urls_from_str = parser.extract_detail_urls(html)
    soup = BeautifulSoup(html, "html.parser")
    urls_from_soup = parser.extract_detail_urls(soup)
    assert urls_from_str == ["https://www.re-guide.jp/investment/detail/id/R00123/"]
    assert urls_from_soup == urls_from_str


def test_strict_price_extraction_rejects_noise_and_non_price_elements():
    # 1. Athome: .num has neighborhood average 10.0万 and management fee, specs has true price
    athome_html = """
    <html><body>
      <div class="loan-sim"><span class="num">10.0万</span></div>
      <div class="fee"><span class="price">管理費 12,000円</span></div>
      <table>
        <tr><th>価格</th><td>4,980万円</td></tr>
      </table>
    </body></html>
    """
    athome_soup = BeautifulSoup(athome_html, "html.parser")
    ap = AthomeMansionParser()
    assert ap._parsePrice(athome_soup) == 49_800_000

    # 2. Tokyu: span.num has 12,000円 management fee and div has loan simulation 万円
    tokyu_html = """
    <html><body>
      <div>月々のお支払い 8万円</div>
      <span class="num">管理費 12,000円</span>
      <table>
        <tr><th>販売価格</th><td>6,480万円</td></tr>
      </table>
    </body></html>
    """
    tokyu_soup = BeautifulSoup(tokyu_html, "html.parser")
    tp = TokyuMansionParser()
    assert tp._parsePrice(tokyu_soup) == 64_800_000

    # 3. Heim: earlier td has 12万円, specs has 5,280万円
    heim_html = """
    <html><body>
      <table>
        <tr><th>諸費用目安</th><td>12万円</td></tr>
        <tr><th>価格</th><td>5,280万円</td></tr>
      </table>
    </body></html>
    """
    heim_soup = BeautifulSoup(heim_html, "html.parser")
    hp = HeimKodateParser()
    assert hp._parsePrice(heim_soup) == 52_800_000

    # 4. AdCast / Haseko / Ietan / Toho: earlier class="loan-price" has 月々10万円, specs has 7,980万円
    broker_html = """
    <html><body>
      <div class="loan-price">月々支払 10万円</div>
      <table>
        <tr><th>価格</th><td>7,980万円</td></tr>
      </table>
    </body></html>
    """
    broker_soup = BeautifulSoup(broker_html, "html.parser")
    assert AdCastKodateParser()._parsePrice(broker_soup) == 79_800_000
    assert HasekoMansionParser()._parsePrice(broker_soup) == 79_800_000
    assert IetanMansionParser()._parsePrice(broker_soup) == 79_800_000
    assert TohoTochiParser()._parsePrice(broker_soup) == 79_800_000


def test_property_type_detector_and_router_fixes():
    # 1. Keisei title with multi-type SEO suffix must detect 'mansion'
    keisei_title = (
        "Brilliaタワー東京 東京都墨田区太平４丁目 中古マンション 15998万円 "
        "JR総武本線錦糸町駅 徒歩7分｜京成線の不動産 一戸建て マンション 土地 京成不動産"
    )
    keisei_specs = {"種目": "中古マンション", "専有面積": "70.12㎡", "所在階": "11階"}
    assert (
        PropertyTypeDetector.detect(
            url="https://www.keisei-land.co.jp/contents/code/detail/6083070/",
            title=keisei_title,
            specs=keisei_specs,
        )
        == "mansion"
    )

    # 2. Nomura sectional-title mansion with 'テラスハウス' in building name must stay 'mansion'
    nomura_title = "【ノムコム】テラスハウスヴィップ東長崎｜中古マンション(FD9C9020)"
    nomura_specs = {
        "専有面積": "47.95m 2",
        "管理費": "15,200円 / 月",
        "修繕積立金": "7,600円 / 月",
        "所在階": "2階",
    }
    assert (
        PropertyTypeDetector.detect(
            url="https://www.nomu.com/mansion/id/FD9C9020/",
            title=nomura_title,
            specs=nomura_specs,
        )
        == "mansion"
    )

    # 3. Daikyo kodate with '賃貸中' in specs must resolve to DaikyoKodateParser via UrlRouter
    daikyo_parser = UrlRouter.create_parser(
        url="https://www.daikyo-anabuki.co.jp/buy/detail/OAL08972/",
        title="東京都新宿区四谷４丁目 3LDK｜新宿区の一戸建て購入【OAL08972】｜大京穴吹不動産",
        specs={"建物面積": "77.21m2", "土地面積": "49.48m2", "構造": "木造", "現況": "賃貸中"},
    )
    assert daikyo_parser.__class__.__name__ == "DaikyoKodateParser"

    # 4. Mitsui kodate with partial fixed-term tenancy in remarks and no yield must stay 'kodate'
    mitsui_specs = {
        "価格": "8,480万円",
        "土地面積": "120.5㎡",
        "建物面積": "95.2㎡",
        "間取り": "3LDK",
        "備考": "3戸中1戸は2027年3月まで定期賃貸借契約中",
    }
    assert (
        PropertyTypeDetector.detect(
            url="https://www.rehouse.co.jp/buy/kodate/bkdetail/F15BPA17/",
            title="世田谷区の中古一戸建て",
            specs=mitsui_specs,
        )
        == "kodate"
    )


def test_site_specific_parser_fixes():
    # 1. MitsuiInvestmentParser._delegate_shumoku_parser preserves _switched_from_property_type
    mp = MitsuiInvestmentApartmentParser()
    src_item = mp.createEntity()
    src_item.pageUrl = "https://www.rehouse.co.jp/buy/kodate/bkdetail/F15BPA17/"
    src_item._switched_from_property_type = "kodate"
    soup = BeautifulSoup(
        "<html><body><h1>テスト戸建</h1><table><tr><th>物件種目</th><td>一戸建て</td></tr>"
        "<tr><th>価格</th><td>5,000万円</td></tr>"
        "<tr><th>所在地</th><td>東京都世田谷区1-1</td></tr>"
        "<tr><th>土地面積</th><td>100㎡</td></tr><tr><th>建物面積</th><td>80㎡</td></tr>"
        "<tr><th>間取り</th><td>3LDK</td></tr><tr><th>築年月</th><td>2015年5月</td></tr>"
        "<tr><th>構造</th><td>木造2階建</td></tr></table></body></html>",
        "html.parser",
    )
    delegated = mp._delegate_shumoku_parser(src_item, soup)
    assert getattr(delegated, "_switched_from_property_type", None) == "kodate"

    # 2. SumifuMansionParser fallback for syuzenTsumitateStr and tochikenri
    sp = SumifuMansionParser()
    s_soup = BeautifulSoup(
        "<html><body><table><tr><th>敷地の権利形態</th><td>所有権</td></tr><tr><th>修繕積立金</th><td>-</td></tr></table></body></html>",
        "html.parser",
    )
    assert sp._parseSyuzenTsumitateStr(s_soup) == "-"
    assert sp._parseSyuzenTsumitate(s_soup) == 0
    assert sp._parseTochikenri(s_soup) == "所有権"

    # 3. TokyuMansionParser / TokyuKodateParser / TokyuTochiParser fixes
    tp_m = TokyuMansionParser()
    t_soup = BeautifulSoup(
        "<html><body><table><tr><th>管理費</th><td>-</td></tr><tr><th>修繕積立金</th><td>－</td></tr></table></body></html>",
        "html.parser",
    )
    assert tp_m._parseKanrihi(t_soup) == 0
    assert tp_m._parseSyuzenTsumitate(t_soup) == 0
    with pytest.raises(SkipPropertyException):
        tp_m._reject_non_property_url("https://www.livable.co.jp/fudosan-toushi/C11268A17/")

    tp_k = TokyuKodateParser()
    with pytest.raises(SkipPropertyException):
        tp_k._reject_non_property_url("https://www.livable.co.jp/kounyu/bunjou/D14266015/")

    tp_t = TokyuTochiParser()
    assert tp_t._parseKuiki(BeautifulSoup("<html><body><table></table></body></html>", "html.parser")) == "-"

    # 4. HomesInvestmentApartmentParser skips abnormal yield >= 1000% when rent is missing
    hp = HomesInvestmentApartmentParser()
    h_item = hp.createEntity()
    h_soup = BeautifulSoup(
        "<html><body><h1>テストアパート</h1><table><tr><th>価格</th><td>5,000万円</td></tr>"
        "<tr><th>所在地</th><td>東京都新宿区1-1</td></tr>"
        "<tr><th>表面利回り</th><td>61569.76%</td></tr></table></body></html>",
        "html.parser",
    )
    with pytest.raises(SkipPropertyException):
        hp._parsePropertyDetailPage(h_item, h_soup)

    # 5. Toho seyaku URL raises ListingEndedException
    with pytest.raises(ListingEndedException):
        check_toho_listing_ended(
            BeautifulSoup("<html><body></body></html>", "html.parser"),
            "https://th-yokohama.com/estate_list_seyaku/estate_detail_54811_1517.html",
        )

    # 6. converter.parse_chikunengetsu rejects pre-1900 typo (1878年3月)
    assert converter.parse_chikunengetsu("1878年3月") is None
    assert converter.parse_chikunengetsu("1998年3月") is not None

    # 7. RearieMansionParser skips unresolved Vue template
    rp = RearieMansionParser()
    r_soup = BeautifulSoup("<html><body><h1>{{ prop.name }}</h1><div>{{ prop.price }}</div></body></html>", "html.parser")
    with pytest.raises(SkipPropertyException):
        rp._parsePropertyDetailPage(rp.createEntity(), r_soup)

    # 8. Sumai1InvestmentParser rejects /buyers/tochi/ and /buyers/kodate/
    s1 = Sumai1InvestmentParser()
    with pytest.raises(SkipPropertyException):
        s1._reject_non_property_url("https://www.sumai1.com/buyers/tochi/detail_123/")
    with pytest.raises(SkipPropertyException):
        s1._reject_non_property_url("https://www.sumai1.com/buyers/kodate/detail_123/")

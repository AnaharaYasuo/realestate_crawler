# -*- coding: utf-8 -*-
import json
import logging
import importlib
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from main import app

from package.utils.url_security import UrlSecurityValidator
from package.utils.url_router import UrlRouter
from package.utils.singleflight import SingleflightGroup
from package.utils.rate_limiter import SlidingWindowRateLimiter
from package.utils.url_matcher import UrlMatcher
from package.parser.heimParser import HeimKodateParser, HeimMansionParser, HeimTochiParser
from package.parser.sumai1Parser import (
    Sumai1InvestmentParser,
    Sumai1KodateParser,
    Sumai1MansionParser,
    Sumai1TochiParser,
)


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


# ==============================================================================
# 1. URL Security & SSRF Defense Unit Tests
# ==============================================================================
def test_url_security_valid_public_url():
    is_safe, reason = UrlSecurityValidator.validate_url_security("https://www.rehouse.co.jp/buy/mansion/bkdetail/FKPBAA05/")
    assert is_safe is True
    assert reason == ""


def test_url_security_invalid_scheme():
    is_safe, reason = UrlSecurityValidator.validate_url_security("ftp://example.com/property/1")
    assert is_safe is False
    assert "Invalid scheme" in reason


def test_url_security_blocked_loopback_and_private_ips():
    dangerous_urls = [
        "http://127.0.0.1/admin",
        "http://localhost:8000/internal",
        "http://192.168.1.10/status",
        "http://10.0.0.1/secret",
        "http://172.16.0.1/api",
        "http://169.254.169.254/computeMetadata/v1/",  # Cloud metadata SSRF
    ]
    for url in dangerous_urls:
        is_safe, reason = UrlSecurityValidator.validate_url_security(url)
        assert is_safe is False, f"URL should be blocked: {url}"
        assert "Blocked" in reason or "SSRF" in reason or "private" in reason.lower() or "loopback" in reason.lower()


def test_url_security_blocked_ports():
    is_safe, reason = UrlSecurityValidator.validate_url_security("http://example.com:22/test")
    assert is_safe is False
    assert "port" in reason.lower()


# ==============================================================================
# 2. URL Router Unit Tests
# ==============================================================================
def test_url_router_resolution():
    router = UrlRouter()
    
    # 三井のリハウス (マンション)
    route = router.resolve("https://www.rehouse.co.jp/buy/mansion/bkdetail/FKPBAA05/")
    assert route is not None
    assert route["site"] == "mitsui"
    assert route["property_type"] == "mansion"

    # 東急リバブル (戸建て)
    route = router.resolve("https://www.livable.co.jp/kounyu/kodate/tokyo/a13101/C12345/")
    assert route is not None
    assert route["site"] == "tokyu"
    assert route["property_type"] == "kodate"

    # 未対応ドメイン
    route = router.resolve("https://unknown-broker.co.jp/bukken/detail/123")
    assert route is None

    # 住まい1 (Sumai1)
    # mansion
    route_sumai1_m = router.resolve("https://www.sumai1.com/buyers/mansion/bukken/buk_39026K00614/")
    assert route_sumai1_m is not None
    assert route_sumai1_m["site"] == "sumai1"
    assert route_sumai1_m["property_type"] == "mansion"
    parser_sumai1_m = UrlRouter.create_parser("https://www.sumai1.com/buyers/mansion/bukken/buk_39026K00614/")
    assert isinstance(parser_sumai1_m, Sumai1MansionParser)

    # kodate
    route_sumai1_k = router.resolve("https://www.sumai1.com/buyers/kodate/bukken/buk_YAAA15785/")
    assert route_sumai1_k is not None
    assert route_sumai1_k["site"] == "sumai1"
    assert route_sumai1_k["property_type"] == "kodate"
    parser_sumai1_k = UrlRouter.create_parser("https://www.sumai1.com/buyers/kodate/bukken/buk_YAAA15785/")
    assert isinstance(parser_sumai1_k, Sumai1KodateParser)

    # tochi
    route_sumai1_t = router.resolve("https://www.sumai1.com/buyers/tochi/bukken/buk_NFA8BY007/")
    assert route_sumai1_t is not None
    assert route_sumai1_t["site"] == "sumai1"
    assert route_sumai1_t["property_type"] == "tochi"
    parser_sumai1_t = UrlRouter.create_parser("https://www.sumai1.com/buyers/tochi/bukken/buk_NFA8BY007/")
    assert isinstance(parser_sumai1_t, Sumai1TochiParser)

    # investor / apartment
    route_sumai1_i = router.resolve("https://www.sumai1.com/buyers/investor/bukken/buk_40025S00114/")
    assert route_sumai1_i is not None
    assert route_sumai1_i["site"] == "sumai1"
    assert route_sumai1_i["property_type"] == "apartment"
    parser_sumai1_i = UrlRouter.create_parser("https://www.sumai1.com/buyers/investor/bukken/buk_40025S00114/")
    assert isinstance(parser_sumai1_i, Sumai1InvestmentParser)

    # セキスイハイム (Heim)
    heim_url = "https://www.tokyo816.jp/bunjou/property/240046522/index.html"
    # デフォルト解決 (kodate)
    route_heim_def = router.resolve(heim_url)
    assert route_heim_def is not None
    assert route_heim_def["site"] == "heim"
    assert route_heim_def["property_type"] == "kodate"
    parser_heim_def = UrlRouter.create_parser(heim_url)
    assert isinstance(parser_heim_def, HeimKodateParser)

    # property_type / 動的判定による解決 (mansion)
    route_heim_m = router.resolve(heim_url, property_type="mansion")
    assert route_heim_m is not None
    assert route_heim_m["property_type"] == "mansion"
    parser_heim_m = UrlRouter.create_parser(heim_url, property_type="mansion")
    assert isinstance(parser_heim_m, HeimMansionParser)

    # property_type / 動的判定による解決 (tochi)
    route_heim_t = router.resolve(heim_url, property_type="tochi")
    assert route_heim_t is not None
    assert route_heim_t["property_type"] == "tochi"
    parser_heim_t = UrlRouter.create_parser(heim_url, property_type="tochi")
    assert isinstance(parser_heim_t, HeimTochiParser)

    # plan_detail URL
    heim_plan_url = "https://www.tokyo816.jp/plan_detail/12345/index.html"
    assert router.resolve(heim_plan_url)["site"] == "heim"

    # 大京穴吹不動産 (Daikyo)
    daikyo_url = "https://www.daikyo-anabuki.co.jp/buy/detail/MHF89471/"
    route_daikyo = router.resolve(daikyo_url)
    assert route_daikyo is not None
    assert route_daikyo["site"] == "daikyo"
    assert route_daikyo["property_type"] == "mansion"
    from package.parser.daikyoParser import DaikyoMansionParser
    assert isinstance(UrlRouter.create_parser(daikyo_url), DaikyoMansionParser)

    # みずほ不動産販売 (Mizuho)
    mizuho_invest_url = "https://www.mizuho-re.co.jp/investors/property/000000935845/"
    route_mizuho_i = router.resolve(mizuho_invest_url)
    assert route_mizuho_i is not None
    assert route_mizuho_i["site"] == "mizuho"
    assert route_mizuho_i["property_type"] == "apartment"
    from package.parser.mizuhoParser import MizuhoInvestmentParser, MizuhoMansionParser
    assert isinstance(UrlRouter.create_parser(mizuho_invest_url), MizuhoInvestmentParser)

    mizuho_buyer_url = "https://www.mizuho-re.co.jp/buyers/property/001201249674/"
    route_mizuho_m = router.resolve(mizuho_buyer_url, property_type="mansion")
    assert route_mizuho_m is not None
    assert route_mizuho_m["site"] == "mizuho"
    assert isinstance(UrlRouter.create_parser(mizuho_buyer_url, property_type="mansion"), MizuhoMansionParser)

    # 大和ハウスリアルエステート (Daiwa)
    daiwa_url = "https://www.dh-realestate.co.jp/buy/mansion/f0065000hd260047"
    route_daiwa = router.resolve(daiwa_url)
    assert route_daiwa is not None
    assert route_daiwa["site"] == "daiwa"
    assert route_daiwa["property_type"] == "mansion"
    from package.parser.daiwaParser import DaiwaMansionParser
    assert isinstance(UrlRouter.create_parser(daiwa_url), DaiwaMansionParser)

    # 東急リバブル (Tokyu: fudosan-toushi & sumikae)
    tokyu_toushi_url = "https://www.livable.co.jp/fudosan-toushi/C13269J06/"
    route_tokyu_toushi = router.resolve(tokyu_toushi_url)
    assert route_tokyu_toushi is not None
    assert route_tokyu_toushi["site"] == "tokyu"
    assert route_tokyu_toushi["property_type"] == "apartment"
    from package.parser.tokyuParser import TokyuInvestmentApartmentParser, TokyuMansionParser
    assert isinstance(UrlRouter.create_parser(tokyu_toushi_url), TokyuInvestmentApartmentParser)

    sumikae_url = "https://sumikae.ttfuhan.co.jp/mansion/DMHF91449/"
    route_sumikae = router.resolve(sumikae_url)
    assert route_sumikae is not None
    assert route_sumikae["site"] == "tokyu"
    assert route_sumikae["property_type"] == "mansion"
    assert isinstance(UrlRouter.create_parser(sumikae_url), TokyuMansionParser)

    # 小田急不動産 (Odakyu)
    odakyu_invest_url = "https://www.odakyu-chukai.com/invest/list?focus=VA0389"
    route_odakyu_i = router.resolve(odakyu_invest_url)
    assert route_odakyu_i is not None
    assert route_odakyu_i["site"] == "odakyu"
    assert route_odakyu_i["property_type"] == "apartment"
    from package.parser.odakyuParser import OdakyuInvestmentParser, OdakyuMansionParser
    assert isinstance(UrlRouter.create_parser(odakyu_invest_url), OdakyuInvestmentParser)

    odakyu_mansion_url = "https://www.odakyu-chukai.com/mansion/detail/B01412-008200/"
    route_odakyu_m = router.resolve(odakyu_mansion_url)
    assert route_odakyu_m is not None
    assert route_odakyu_m["site"] == "odakyu"
    assert route_odakyu_m["property_type"] == "mansion"
    assert isinstance(UrlRouter.create_parser(odakyu_mansion_url), OdakyuMansionParser)

    # 京王不動産 (Keio)
    keio_url = "https://chukai.keiofudosan.co.jp/sale/2127977638870000006546/"
    route_keio = router.resolve(keio_url)
    assert route_keio is not None
    assert route_keio["site"] == "keio"
    from package.parser.keioParser import KeioMansionParser
    assert isinstance(UrlRouter.create_parser(keio_url), KeioMansionParser)

    # 京急すまい (Keikyu)
    keikyu_url = "https://www.keikyu-sumai.com/contents/code/detail/152450258/"
    route_keikyu = router.resolve(keikyu_url)
    assert route_keikyu is not None
    assert route_keikyu["site"] == "keikyu"
    from package.parser.keikyuParser import KeikyuMansionParser
    assert isinstance(UrlRouter.create_parser(keikyu_url), KeikyuMansionParser)

    # 京成不動産 (Keisei)
    keisei_url = "https://www.keisei-land.co.jp/contents/code/detail/6083101/"
    route_keisei = router.resolve(keisei_url)
    assert route_keisei is not None
    assert route_keisei["site"] == "keisei"
    from package.parser.keiseiParser import KeiseiMansionParser
    assert isinstance(UrlRouter.create_parser(keisei_url), KeiseiMansionParser)

    # 住友林業ホームサービス すみなび (Sumirin)
    sumirin_url = "https://www.suminavi.com/buy/estate/estateInfo/mansion/kansai/633928/"
    route_sumirin = router.resolve(sumirin_url)
    assert route_sumirin is not None
    assert route_sumirin["site"] == "sumirin"
    assert route_sumirin["property_type"] == "mansion"
    from package.parser.sumirinParser import SumirinMansionParser
    assert isinstance(UrlRouter.create_parser(sumirin_url), SumirinMansionParser)

    # アットホーム その他 (Athome buy_other)
    athome_other_url = "https://www.athome.co.jp/buy_other/6991614140?BKLISTID=001LPC&SEARCHDIV=1&sref=list_simple"
    route_athome_other = router.resolve(athome_other_url)
    assert route_athome_other is not None
    assert route_athome_other["site"] == "athome"
    assert route_athome_other["property_type"] == "tochi"
    from package.parser.athomeParser import AthomeTochiParser
    assert isinstance(UrlRouter.create_parser(athome_other_url), AthomeTochiParser)

    # 野村不動産 (Nomura: pro apartment & pro invest_kodate)
    nomura_pro_url = "https://www.nomu.com/pro/bukken_local_id/FB9C6017/"
    route_nomura_apt = router.resolve(nomura_pro_url)
    assert route_nomura_apt is not None
    assert route_nomura_apt["site"] == "nomura"
    assert route_nomura_apt["property_type"] == "apartment"

    route_nomura_kodate = router.resolve(nomura_pro_url, property_type="invest_kodate")
    assert route_nomura_kodate is not None
    assert route_nomura_kodate["site"] == "nomura"
    assert route_nomura_kodate["property_type"] == "invest_kodate"
    from package.parser.nomuraParser import NomuraInvestmentKodateParser, NomuraInvestmentApartmentParser
    assert isinstance(UrlRouter.create_parser(nomura_pro_url, property_type="invest_kodate"), NomuraInvestmentKodateParser)
    assert isinstance(UrlRouter.create_parser(nomura_pro_url, property_type="apartment"), NomuraInvestmentApartmentParser)


# ==============================================================================
# 3. Singleflight Concurrency Control Unit Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_singleflight_coalescing():
    group = SingleflightGroup()
    call_count = 0

    async def expensive_crawl(url: str):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return f"result_for_{url}"

    target_url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKPBAA05/"
    
    # 5つの並行リクエストを実行
    tasks = [group.do(target_url, expensive_crawl, target_url) for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # 5回呼ばれても実処理は1回だけ
    assert call_count == 1
    assert all(r == f"result_for_{target_url}" for r in results)


@pytest.mark.asyncio
async def test_singleflight_coalescing_different_query_params():
    """異なるクエリパラメータが付与された同一物件URLの並行リクエストが1回に合流すること"""
    group = SingleflightGroup()
    call_count = 0

    async def expensive_crawl(u):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return "crawled_data"

    raw_urls = [
        "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKPBAA05/?utm_source=twitter",
        "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKPBAA05/?utm_source=google",
        "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKPBAA05/#overview",
        "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKPBAA05/?DOWN=1"
    ]
    tasks = [group.do(UrlMatcher.normalize(u), expensive_crawl, u) for u in raw_urls]
    results = await asyncio.gather(*tasks)

    assert call_count == 1
    assert all(r == "crawled_data" for r in results)


# ==============================================================================
# 4. Rate Limiter Unit Tests
# ==============================================================================
def test_rate_limiter():
    limiter = SlidingWindowRateLimiter(limit_per_minute=5, burst_per_second=3)
    client_id = "test_client_ip"

    # 3回までは通る (burst_per_second=3)
    assert limiter.is_allowed(client_id)[0] is True
    assert limiter.is_allowed(client_id)[0] is True
    assert limiter.is_allowed(client_id)[0] is True

    # 4回目は同一秒内でバースト制限にかかる
    allowed, retry_after = limiter.is_allowed(client_id)
    assert allowed is False
    assert retry_after >= 1


# ==============================================================================
# 5. API End-to-End & Tier Caching Tests
# ==============================================================================
def test_predict_by_url_tier1_evaluation_cache(client):
    """Tier 1: PropertyEvaluation に推論結果が存在する場合、キャッシュから即返却"""
    test_url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/TIER1TEST/"
    
    # モックデータ
    mock_eval = MagicMock()
    mock_eval.first_stage_predicted_price = 52000000
    mock_eval.second_stage_predicted_price = 53500000
    mock_eval.company = "mitsui"
    mock_eval.property_type = "mansion"
    mock_eval.property_id = 999

    mock_mansion = MagicMock()
    mock_mansion.propertyName = "テストマンション1"
    mock_mansion.price = 50000000
    mock_mansion.address = "東京都世田谷区桜丘1-1"
    mock_mansion.station1 = "経堂"
    mock_mansion.railwayWalkMinute1 = 5
    mock_mansion.senyuMenseki = 65.0
    mock_mansion.chikunengetsuStr = "2015-04-01"
    mock_mansion.kouzou = "RC"

    with patch('package.models.evaluation.PropertyEvaluation.objects.filter') as mock_filter, \
         patch('package.models.mitsui.MitsuiMansion.objects.filter') as mock_m_filter:
        mock_filter.return_value.first.return_value = mock_eval
        mock_m_filter.return_value.first.return_value = mock_mansion

        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({"url": test_url}),
            content_type='application/json'
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data_source"] == "evaluation_cache"
        assert data["prediction"]["first_stage_predicted_price"] == 52000000
        assert data["prediction"]["price_gap"] == 2000000


def test_predict_by_url_tier2_db_property(client):
    """Tier 2: PropertyEvaluation に未存在だが、物件テーブルにデータがある場合オンデマンド推論"""
    test_url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/TIER2TEST/"

    mock_mansion = MagicMock()
    mock_mansion.propertyName = "テストマンション2"
    mock_mansion.price = 40000000
    mock_mansion.address = "東京都世田谷区桜丘2-2"
    mock_mansion.station1 = "経堂"
    mock_mansion.railwayWalkMinute1 = 7
    mock_mansion.senyuMenseki = 58.0
    mock_mansion.chikunengetsuStr = "2012-08-01"
    mock_mansion.kouzou = "RC"

    with patch('package.models.evaluation.PropertyEvaluation.objects.filter') as mock_filter, \
         patch('package.models.mitsui.MitsuiMansion.objects.filter') as mock_m_filter, \
         patch('routes.evaluation_routes.predict_first_stage_local', return_value=43000000), \
         patch('routes.evaluation_routes.predict_second_stage_local', return_value=44000000), \
         patch('package.models.evaluation.PropertyEvaluation.objects.update_or_create') as mock_upsert:
        
        # PropertyEvaluation は存在しない
        mock_filter.return_value.first.return_value = None
        # 物件テーブルには存在する
        mock_m_filter.return_value.first.return_value = mock_mansion

        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({"url": test_url}),
            content_type='application/json'
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data_source"] == "db_property"
        assert data["prediction"]["first_stage_predicted_price"] == 43000000
        assert mock_upsert.called


def test_predict_by_url_unsupported_candidate_recorded(client):
    """未対応サイトの場合、安全性・物件キーワード判定を経て候補DBに記録し 400 を返却"""
    test_url = "https://unsupported-realtor.com/bukken/detail/9999"

    with patch('package.models.evaluation.PropertyEvaluation.objects.filter') as mock_p_filter, \
         patch('package.utils.url_security.UrlSecurityValidator.check_property_content_and_reachability') as mock_check, \
         patch('package.models.candidate.CandidatePropertyUrl.objects.filter') as mock_c_filter, \
         patch('package.models.candidate.CandidatePropertyUrl.objects.create') as mock_c_create:
        
        mock_p_filter.return_value.first.return_value = None
        # 物件判定合格
        mock_check.return_value = (True, "未対応物件ページ", ["価格", "専有面積", "間取り"])
        mock_c_filter.return_value.first.return_value = None  # 新規

        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({"url": test_url}),
            content_type='application/json'
        )
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False
        assert data["error_code"] == "UNSUPPORTED_SITE_CANDIDATE_RECORDED"
        assert mock_c_create.called


def test_predict_by_url_unsupported_candidate_logs_error(client, caplog):
    """パーサー未対応サイトの場合、新規パーサー開発対象として [PARSER_UNAVAILABLE] の ERROR ログが出力されること"""
    test_url = "https://unsupported-realtor.com/bukken/detail/8888"

    with patch('package.models.evaluation.PropertyEvaluation.objects.filter') as mock_p_filter, \
         patch('package.utils.url_security.UrlSecurityValidator.check_property_content_and_reachability') as mock_check, \
         patch('package.models.candidate.CandidatePropertyUrl.objects.filter') as mock_c_filter, \
         patch('package.models.candidate.CandidatePropertyUrl.objects.create'), \
         caplog.at_level(logging.ERROR):

        mock_p_filter.return_value.first.return_value = None
        mock_check.return_value = (True, "テスト新着物件", ["価格", "所在地", "間取り"])
        mock_c_filter.return_value.first.return_value = None

        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({"url": test_url}),
            content_type='application/json'
        )
        assert res.status_code == 400
        assert any("[PARSER_UNAVAILABLE]" in record.message and "unsupported-realtor" in record.message for record in caplog.records)


def test_predict_by_url_parser_loading_failure_logs_error(client, caplog):
    """パーサーモジュール/クラスの読込に失敗した場合、[PARSER_NOT_FOUND] の ERROR ログが出力されること"""
    test_url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/LOADFAIL/"

    real_import = importlib.import_module
    def selective_import(name, *args, **kwargs):
        if "parser" in name:
            raise ImportError("Mocked parser missing")
        return real_import(name, *args, **kwargs)

    with patch('package.models.evaluation.PropertyEvaluation.objects.filter') as mock_p_filter, \
         patch('package.models.mitsui.MitsuiMansion.objects.filter') as mock_m_filter, \
         patch('importlib.import_module', side_effect=selective_import), \
         caplog.at_level(logging.ERROR):

        mock_p_filter.return_value.first.return_value = None
        mock_m_filter.return_value.first.return_value = None

        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({"url": test_url}),
            content_type='application/json'
        )
        assert res.status_code == 500
        data = res.get_json()
        assert data["error_code"] == "PARSER_NOT_FOUND"
        assert any("[PARSER_NOT_FOUND]" in record.message for record in caplog.records)


def test_predict_by_url_toushi_homes_routes_correctly(client):
    """toushi.homes.co.jp の投資用物件URLが HomesInvestmentApartmentParser / apartment に正しくルーティングされること"""
    test_url = "https://toushi.homes.co.jp/bukkendetail/index/4721792/"

    fake_item = MagicMock()
    fake_item.id = 777
    fake_item.pageUrl = test_url
    fake_item.price = 41200000
    fake_item.address = "埼玉県さいたま市中央区円阿弥"
    fake_item.station1 = "与野本町"
    fake_item.railwayWalkMinute1 = 15
    fake_item.grossYield = 6.02
    fake_item.annualRent = 2480000
    fake_item.kouzou = "木造"
    fake_item.youseki = 200.0
    fake_item.kenpei = 60.0
    fake_item.tochikenri = "所有権"
    fake_item.biko = ""
    fake_item.chikunengetsu = None
    fake_item.chikunengetsuStr = "1995-04"
    fake_item.tatemonoMenseki = 180.5
    fake_item.tochiMenseki = 150.0
    fake_item.maguchi = 8.5
    fake_item.roadWidth = 4.0
    fake_item.setsudou = "公道"

    with patch('package.models.evaluation.PropertyEvaluation.objects.filter') as mock_p_filter, \
         patch('package.models.homes.HomesInvestmentApartment.objects.filter') as mock_h_filter, \
         patch('package.models.evaluation.PropertyEvaluation.objects.update_or_create'), \
         patch('routes.evaluation_routes.predict_first_stage_local', return_value=4300), \
         patch('routes.evaluation_routes.predict_second_stage_local', return_value=4350):

        mock_p_filter.return_value.first.return_value = None
        mock_h_filter.return_value.first.return_value = fake_item

        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({"url": test_url}),
            content_type='application/json'
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["site"] == "homes"
        assert data["property_type"] == "apartment"
        assert data["prediction"]["first_stage_predicted_price"] == 4300


def test_predict_by_url_with_property_type_param(client):
    """リクエストボディで property_type が指定された場合、指定された種別のパーサー/モデルにルーティングされること"""
    test_url = "https://smtrc.jp/detail/12345"

    fake_item = MagicMock()
    fake_item.id = 888
    fake_item.pageUrl = test_url
    fake_item.price = 55000000
    fake_item.address = "東京都世田谷区桜丘"
    fake_item.station1 = "経堂"
    fake_item.railwayWalkMinute1 = 10
    fake_item.kouzou = "木造"
    fake_item.youseki = 150.0
    fake_item.kenpei = 50.0
    fake_item.tochikenri = "所有権"
    fake_item.biko = ""
    fake_item.chikunengetsu = None
    fake_item.chikunengetsuStr = "2015-06"
    fake_item.tatemonoMenseki = 95.0
    fake_item.tochiMenseki = 110.0
    fake_item.maguchi = 7.0
    fake_item.roadWidth = 4.5
    fake_item.setsudou = "南側道路公道"

    with patch('package.models.evaluation.PropertyEvaluation.objects.filter') as mock_p_filter, \
         patch('package.models.smtrc.SmtrcKodate.objects.filter') as mock_s_filter, \
         patch('package.models.evaluation.PropertyEvaluation.objects.update_or_create'), \
         patch('routes.evaluation_routes.predict_first_stage_local', return_value=5400), \
         patch('routes.evaluation_routes.predict_second_stage_local', return_value=5450):

        mock_p_filter.return_value.first.return_value = None
        mock_s_filter.return_value.first.return_value = fake_item

        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({"url": test_url, "property_type": "kodate"}),
            content_type='application/json'
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["site"] == "smtrc"
        assert data["property_type"] == "kodate"
        assert data["prediction"]["first_stage_predicted_price"] == 5400


def test_lockout_manager():
    from package.utils.rate_limiter import LockoutManager
    manager = LockoutManager(lockout_seconds=60, strike_threshold=2)
    bad_ip = "192.0.2.1"

    # 初期状態はロックアウトされていない
    is_locked, remaining = manager.is_locked_out(bad_ip)
    assert is_locked is False

    # 1回目のストライク
    banned, _ = manager.record_strike(bad_ip)
    assert banned is False

    # 2回目のストライク ➔ 閾値到達でBAN
    banned, ban_duration = manager.record_strike(bad_ip)
    assert banned is True
    assert ban_duration == 60

    # BAN判定の確認
    is_locked, remaining = manager.is_locked_out(bad_ip)
    assert is_locked is True
    assert remaining > 0

    # 即時BAN (SSRF等) の確認
    another_bad_ip = "192.0.2.2"
    banned, _ = manager.record_strike(another_bad_ip, instant_ban=True)
    assert banned is True
    assert manager.is_locked_out(another_bad_ip)[0] is True


def test_predict_by_url_locked_out_client(client):
    """ロックアウトされた外部IPからのリクエストは403 Forbiddenで即遮断される"""
    with patch('routes.evaluation_routes.is_internal_client', return_value=False), \
         patch('routes.evaluation_routes.lockout_manager.is_locked_out', return_value=(True, 450)):
        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({"url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/TEST/"}),
            headers={"X-Forwarded-For": "203.0.113.50"},
            content_type='application/json'
        )
        assert res.status_code == 403
        data = res.get_json()
        assert data["success"] is False
        assert data["error_code"] == "IP_LOCKED_OUT"
        assert "450" in str(data["retry_after_seconds"])


def test_predict_by_url_internal_bypasses_rate_limit(client):
    """自作内部システムからの接続は、レートリミット上限を超えていても429にならず処理される"""
    with patch('routes.evaluation_routes.is_internal_client', return_value=True), \
         patch('routes.evaluation_routes.rate_limiter.is_allowed', return_value=(False, 60)), \
         patch('package.models.evaluation.PropertyEvaluation.objects.filter') as mock_filter:
        
        mock_eval = MagicMock()
        mock_eval.first_stage_predicted_price = 45000000
        mock_eval.second_stage_predicted_price = 46000000
        mock_eval.company = "mitsui"
        mock_eval.property_type = "mansion"
        mock_filter.return_value.first.return_value = mock_eval

        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({"url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/INTERNALTEST/"}),
            headers={"X-INTERNAL-REQUEST": "true"},
            content_type='application/json'
        )
        # 429 ではなく 200 OK で正常処理されること
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True


# ==============================================================================
# 8. URL Matcher & Query Parameter Ignoring Unit Tests
# ==============================================================================
def test_url_matcher_normalize_and_same_url():
    """クエリパラメータ・フラグメント・ポート・大文字小文字を除去した正規化と同一性検証"""
    u1 = "https://WWW.Rehouse.co.jp:443/buy/mansion/bkdetail/F24X2A08/?utm_source=twitter&utm_medium=cpc&token=123#overview"
    u2 = "https://www.rehouse.co.jp/buy/mansion/bkdetail/F24X2A08/"
    u3 = "https://www.rehouse.co.jp/buy/mansion/bkdetail/F24X2A08"
    u4 = "https://www.rehouse.co.jp/buy/mansion/bkdetail/F24X2A08/?DOWN=1"
    u_diff = "https://www.rehouse.co.jp/buy/mansion/bkdetail/OTHER123/"

    assert UrlMatcher.normalize(u1) == "https://www.rehouse.co.jp/buy/mansion/bkdetail/F24X2A08/"
    assert UrlMatcher.is_same_url(u1, u2) is True
    assert UrlMatcher.is_same_url(u1, u3) is True
    assert UrlMatcher.is_same_url(u1, u4) is True
    assert UrlMatcher.is_same_url(u2, u4) is True
    assert UrlMatcher.is_same_url(u1, u_diff) is False

    # Rearie の ?id= パラメータは保持されること（衝突防止）
    r1 = "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=12345&utm_source=test#top"
    r2 = "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=67890"
    r1_norm = UrlMatcher.normalize(r1)
    r2_norm = UrlMatcher.normalize(r2)
    assert r1_norm == "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=12345"
    assert r2_norm == "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=67890"
    assert UrlMatcher.is_same_url(r1, r2) is False


def test_url_matcher_build_db_filter():
    """build_db_filter がクエリパラメータ・末尾スラッシュを網羅するQオブジェクトを生成すること"""
    q = UrlMatcher.build_db_filter("pageUrl", "https://site.com/detail/123/?utm_source=test")
    q_str = str(q)
    assert "https://site.com/detail/123/" in q_str
    assert "https://site.com/detail/123/?" in q_str
    assert "https://site.com/detail/123" in q_str
    assert "https://site.com/detail/123?" in q_str

    # クエリ維持サイト（Rearie等）のフィルター生成
    q_rearie = UrlMatcher.build_db_filter("pageUrl", "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=12345&utm_source=test")
    q_rearie_str = str(q_rearie)
    assert "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=12345" in q_rearie_str
    assert "id=12345&" in q_rearie_str


def test_predict_by_url_tier1_ignores_query_params(client):
    """リクエストにクエリパラメータが付与されていても、DBにクリーンなURLで保存された評価キャッシュにヒットすること"""
    with patch('package.models.evaluation.PropertyEvaluation.objects.filter') as mock_filter, \
         patch('package.models.mitsui.MitsuiMansion.objects.filter') as mock_mitsui:

        mock_eval = MagicMock()
        mock_eval.property_url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/NORMTEST01/"
        mock_eval.first_stage_predicted_price = 52000000
        mock_eval.second_stage_predicted_price = 53500000
        mock_eval.company = "mitsui"
        mock_eval.property_type = "mansion"
        mock_filter.return_value.first.return_value = mock_eval
        mock_mitsui.return_value.first.return_value = None

        # トラッキングパラメータ付きでリクエスト
        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({
                "url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/NORMTEST01/?utm_source=google&gclid=xyz123#map"
            }),
            content_type='application/json'
        )

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data_source"] == "evaluation_cache"
        assert data["prediction"]["first_stage_predicted_price"] == 52000000


def test_predict_by_url_tier2_ignores_query_params(client):
    """リクエストにクエリパラメータが付与されていても、DBに保存された物件レコードと突合してオンデマンド推論されること"""
    with patch('package.models.evaluation.PropertyEvaluation.objects.filter') as mock_filter, \
         patch('package.models.mitsui.MitsuiMansion.objects.filter') as mock_mitsui, \
         patch('routes.evaluation_routes.predict_first_stage_local', return_value=4800), \
         patch('routes.evaluation_routes.predict_second_stage_local', return_value=4850), \
         patch('package.models.evaluation.PropertyEvaluation.objects.update_or_create'):

        # Tier 1 はミス
        mock_filter.return_value.first.return_value = None

        # Tier 2: DB物件データあり（DB側はクリーンURL）
        mock_item = MagicMock()
        mock_item.pageUrl = "https://www.rehouse.co.jp/buy/mansion/bkdetail/NORMTEST02/"
        mock_item.propertyName = "パークホームズ中野"
        mock_item.price = 45000000
        mock_item.address = "東京都中野区中央1-1"
        mock_item.senyuMenseki = 65.0
        mock_mitsui.return_value.first.return_value = mock_item

        # 追跡パラメータ付きでリクエスト
        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({
                "url": "https://www.rehouse.co.jp/buy/mansion/bkdetail/NORMTEST02/?ref=campaign&fbclid=abc"
            }),
            content_type='application/json'
        )

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data_source"] == "db_property"
        assert data["prediction"]["first_stage_predicted_price"] == 4800
        assert data["prediction"]["price_gap"] == 300
        assert data["prediction"]["divergence_ratio"] == 1.067
        assert data["prediction"]["is_bargain"] is False


def test_predict_by_url_scale_normalization_and_bargain_detection(client):
    """円単位(asking_price)と万円単位(predicted_price)のスケール自動正規化と割安判定の検証"""
    from routes.evaluation_routes import _calculate_prediction_metrics

    # 1. 万円推論 (4800万) vs 円売出 (4000万) -> 割安 (4800/4000 = 1.20 >= 1.15)
    gap, ratio, is_bargain = _calculate_prediction_metrics(4800, 40000000)
    assert gap == 800
    assert ratio == 1.2
    assert is_bargain is True

    # 2. 円推論 (4800万) vs 円売出 (4000万) -> 双方が円単位
    gap, ratio, is_bargain = _calculate_prediction_metrics(48000000, 40000000)
    assert gap == 8000000
    assert ratio == 1.2
    assert is_bargain is True

    # 3. 万円推論 (3500万) vs 円売出 (4000万) -> 割高 (3500/4000 = 0.875)
    gap, ratio, is_bargain = _calculate_prediction_metrics(3500, 40000000)
    assert gap == -500
    assert ratio == 0.875
    assert is_bargain is False

    # 4. None / 0 入力耐性
    gap, ratio, is_bargain = _calculate_prediction_metrics(None, 40000000)
    assert gap is None and ratio is None and is_bargain is False


def test_predict_by_url_kenbiya_support(client, monkeypatch):
    """健美家URLが正常にルーティング・パース・推論されることを検証"""
    import datetime
    import json
    from decimal import Decimal
    from package.models.kenbiya import KenbiyaInvestmentApartment

    async def mock_parse(self, session, url):
        item = KenbiyaInvestmentApartment()
        item.pageUrl = url
        item.propertyName = "世田谷区桜2丁目アパート"
        item.price = 59800000
        item.priceStr = "5,980万円"
        item.grossYield = Decimal("5.67")
        item.annualRent = 3396000
        item.monthlyRent = 283000
        item.address = "東京都世田谷区桜2-7"
        item.propertyType = "Apartment"
        item.tochiMenseki = Decimal("91.56")
        item.tatemonoMenseki = Decimal("99.02")
        item.kouzou = "木造2階建"
        item.chikunengetsu = datetime.date(1990, 6, 1)
        return item

    monkeypatch.setattr("package.parser.kenbiyaParser.KenbiyaInvestmentApartmentParser.parsePropertyDetailPage", mock_parse)

    target_url = "https://www.kenbiya.com/pp2/s/tokyo/setagaya-ku/re_4721854dw3/"
    with patch('routes.evaluation_routes.predict_first_stage_local', return_value=58000000), \
         patch('routes.evaluation_routes.predict_second_stage_local', return_value=58500000):
        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({
                "url": target_url,
                "force_refresh": True
            }),
            content_type='application/json'
        )

    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["site"] == "kenbiya"
    assert data["property_type"] == "apartment"
    assert data["property_info"]["price"] == 59800000
    assert data["prediction"]["first_stage_predicted_price"] == 58000000


def test_predict_by_url_rate_limited_returns_429(client, monkeypatch):
    """対象サイトから429 RateLimitedExceptionが送出された場合、HTTP 429 TARGET_SITE_RATE_LIMITED が返却されること"""
    from package.parser.baseParser import RateLimitedException

    async def mock_parse_rate_limited(self, session, url):
        raise RateLimitedException("Kenbiya rate limited (429)")

    monkeypatch.setattr("package.parser.kenbiyaParser.KenbiyaInvestmentApartmentParser.parsePropertyDetailPage", mock_parse_rate_limited)

    target_url = "https://www.kenbiya.com/pp2/s/tokyo/setagaya-ku/re_4721854dw3/"
    res = client.post(
        '/api/evaluation/predict-by-url',
        data=json.dumps({
            "url": target_url,
            "force_refresh": True
        }),
        content_type='application/json'
    )

    assert res.status_code == 429
    data = res.get_json()
    assert data["success"] is False
    assert data["error_code"] == "TARGET_SITE_RATE_LIMITED"
    assert "429" in data["message"]


def test_predict_by_url_normalizes_tracking_url_for_live_crawl(client, monkeypatch):
    """ライブ取得時にトラッキングパラメータ（utm_*等）が除去された正規化URLでパーサーが実行されること"""
    from package.models.kenbiya import KenbiyaInvestmentApartment
    import datetime
    from decimal import Decimal

    received_urls = []

    async def mock_parse(self, session, url):
        received_urls.append(url)
        item = KenbiyaInvestmentApartment()
        item.pageUrl = url
        item.price = 59800000
        item.propertyName = "世田谷区桜2丁目アパート"
        item.address = "東京都世田谷区桜2-7"
        item.tatemonoMenseki = Decimal("99.02")
        item.kouzou = "木造2階建"
        item.chikunengetsu = datetime.date(1990, 6, 1)
        return item

    monkeypatch.setattr("package.parser.kenbiyaParser.KenbiyaInvestmentApartmentParser.parsePropertyDetailPage", mock_parse)

    tracking_url = "https://www.kenbiya.com/pp2/s/tokyo/setagaya-ku/re_4721854dw3/?utm_source=newmail&utm_medium=email"
    with patch('routes.evaluation_routes.predict_first_stage_local', return_value=58000000), \
         patch('routes.evaluation_routes.predict_second_stage_local', return_value=58500000):
        res = client.post(
            '/api/evaluation/predict-by-url',
            data=json.dumps({
                "url": tracking_url,
                "force_refresh": True
            }),
            content_type='application/json'
        )

    assert res.status_code == 200
    assert len(received_urls) == 1
    # トラッキングパラメータが除去されてクリーンなURLになっていること
    assert "utm_source" not in received_urls[0]
    assert received_urls[0] == "https://www.kenbiya.com/pp2/s/tokyo/setagaya-ku/re_4721854dw3/"





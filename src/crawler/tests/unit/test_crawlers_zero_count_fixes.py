import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from package.parser.reguideParser import ReguideInvestmentParser
from package.parser.baseParser import ListingEndedException
from routes.heim_routes import HEIM_TOKYO_SEARCH_URL
from routes.sumirin_routes import API_KEY_SUMIRIN_INVESTMENT_START
from package.utils.crawl_jobs import UNCRAWLED_COMPANIES


def test_heim_search_url_includes_five_prefectures():
    """セキスイハイムが東京(13)、神奈川(14)、千葉(12)、埼玉(11)、山梨(19)の1都4県を網羅していること"""
    assert "pref_check%5B%5D=13" in HEIM_TOKYO_SEARCH_URL
    assert "pref_check%5B%5D=14" in HEIM_TOKYO_SEARCH_URL
    assert "pref_check%5B%5D=12" in HEIM_TOKYO_SEARCH_URL
    assert "pref_check%5B%5D=11" in HEIM_TOKYO_SEARCH_URL
    assert "pref_check%5B%5D=19" in HEIM_TOKYO_SEARCH_URL


def test_sumirin_investment_url_targets_capital_region():
    """住友林業の投資物件ルートが首都圏・東京（r_seq=1, p_cd=13）をターゲットにしていること"""
    from routes import sumirin_routes
    import inspect
    source = inspect.getsource(sumirin_routes.sumirin_investment_start)
    assert "r_seq=1" in source
    assert "p_cd=13" in source
    assert "r_seq=9" not in source


def test_seibu_in_uncrawled_companies():
    """西武不動産がポータル縮小に伴いクロール対象外(UNCRAWLED_COMPANIES)に設定されていること"""
    assert "seibu" in UNCRAWLED_COMPANIES


@pytest.mark.asyncio
async def test_reguide_get_content_retry_success():
    """リガイドの_getContentが初回タイムアウト/エラー時に指数バックオフでリトライし成功すること"""
    parser = ReguideInvestmentParser()
    
    # 1回目は例外、2回目は正常レスポンスを返すモックSession
    mock_session = MagicMock()
    mock_resp_fail = MagicMock()
    
    mock_resp_success = MagicMock()
    mock_resp_success.status = 200
    mock_resp_success.read = AsyncMock(return_value=b"<html><head><title>RE-Guide Test</title></head><body>" + b"x" * 200 + b"</body></html>")

    class MockContextManager:
        def __init__(self, should_fail):
            self.should_fail = should_fail
        async def __aenter__(self):
            if self.should_fail:
                raise TimeoutError("Connection timed out")
            return mock_resp_success
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    call_count = 0
    def mock_get(url, headers=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MockContextManager(should_fail=True)
        return MockContextManager(should_fail=False)

    mock_session.get = mock_get

    # sleepをスキップして高速実行
    import unittest.mock as mock
    with mock.patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        content = await parser._getContent(mock_session, "https://www.re-guide.jp/investment/list/")
        assert b"RE-Guide Test" in content
        assert call_count == 2
        mock_sleep.assert_called_once_with(2.0)


@pytest.mark.asyncio
async def test_reguide_get_content_404_raises_listing_ended():
    """リガイドの404応答時にListingEndedExceptionが送出されること"""
    parser = ReguideInvestmentParser()
    mock_session = MagicMock()
    mock_resp_404 = MagicMock()
    mock_resp_404.status = 404

    class MockContextManager:
        async def __aenter__(self):
            return mock_resp_404
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    mock_session.get = MagicMock(return_value=MockContextManager())

    with pytest.raises(ListingEndedException):
        await parser._getContent(mock_session, "https://www.re-guide.jp/investment/detail/12345")

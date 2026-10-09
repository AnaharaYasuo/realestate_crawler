# -*- coding: utf-8 -*-
"""Unit tests for crawler stability and count aggregator fixes (Issues #819, #820, #821, #822)."""
import datetime
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from package.parser.tokyuParser import TokyuInvestmentKodateParser
from package.parser.smtrcParser import SmtrcMansionParser
from package.parser.sumai1Parser import Sumai1MansionParser
from scripts.ops.run_all_crawlers import get_count_for_job


class TestTokyuInvestmentKodatePropertyType:
    def test_tokyu_investment_kodate_property_type(self):
        """TokyuInvestmentKodateParser の property_type が 'invest_kodate' であること (Issue #819)"""
        parser = TokyuInvestmentKodateParser()
        assert parser.property_type == "invest_kodate"


class TestCountAggregatorForDynamicSwitch:
    def test_get_count_for_job_aggregates_switched_apartment_for_invest_kodate(self):
        """invest_kodate 実行時に動的種別判定で apartment に保存された件数も加算されること (Issues #819, #821)"""
        now = datetime.datetime.now(datetime.timezone.utc)

        # Mock models for TokyuInvestmentKodate and TokyuInvestmentApartment
        mock_kodate_model = MagicMock()
        mock_kodate_model.__name__ = "TokyuInvestmentKodate"
        mock_kodate_model.objects.filter.return_value.count.side_effect = [0, 0]  # detail, skip

        mock_apartment_model = MagicMock()
        mock_apartment_model.__name__ = "TokyuInvestmentApartment"
        mock_apartment_model.objects.filter.return_value.count.side_effect = [5, 10]  # detail, skip

        with patch("scripts.ops.run_all_crawlers.apps.get_models", return_value=[mock_kodate_model, mock_apartment_model]):
            detail_cnt, skip_cnt, total_cnt = get_count_for_job("tokyu", "invest_kodate", now)
            assert detail_cnt == 5
            assert skip_cnt == 10
            assert total_cnt == 15


class TestSumai1TimeoutConfig:
    def test_sumai1_request_timeout_setting(self):
        """Sumai1Parser に適切なリクエストタイムアウト設定が存在すること (Issue #822)"""
        parser = Sumai1MansionParser()
        timeout = getattr(parser, "REQUEST_TIMEOUT_SEC", 15)
        assert timeout >= 20


class TestSmtrcWafSmallPayloadRetry:
    @pytest.mark.asyncio
    async def test_smtrc_waf_small_content_triggers_retry(self):
        """SMTRC でレスポンスが 1000 bytes 未満の場合はリトライまたは Playwright ステルス取得されること (Issue #820)"""
        parser = SmtrcMansionParser()
        session = AsyncMock()
        url = "https://smtrc.jp/list/listViewLive/index?search=city&prefcode=13&bukenkind=1"

        # base _getContent が 144 bytes（WAF/空応答）を返すケース
        with patch("package.parser.baseParser.ParserBase._getContent", return_value=b"short 144 bytes") as mock_base_get:
            with patch.object(
                parser,
                "_smtrc_fetch_with_playwright",
                side_effect=[b"short 144 bytes", b"<html>" + b"x" * 2000 + b"</html>"]
            ) as mock_fetch:
                content = await parser._getContent(session, url)
                assert len(content) > 1000
                assert mock_fetch.call_count >= 1
                mock_base_get.assert_called()

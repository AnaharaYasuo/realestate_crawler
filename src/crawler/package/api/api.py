import asyncio
import aiohttp
import os
import json
import ssl
import traceback
from abc import ABCMeta, abstractmethod
from typing import Dict, Any, Optional

from bs4 import BeautifulSoup
from package.parser.baseParser import LoadPropertyPageException, ParserBase, \
    ReadPropertyNameException, SkipPropertyException
import datetime
from django.core.exceptions import ValidationError
from django import db
from django.db import close_old_connections, OperationalError
from builtins import Exception
from time import sleep
import logging
from package.api.middleware import CrawlerMiddleware, LoggingMiddleware
from package.utils.report import CrawlerReporter
from fake_useragent import UserAgent,FakeUserAgent
from asgiref.sync import sync_to_async
header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}


TCP_CONNECTOR_LIMIT = 100
API_KEY_MANSION_ALL_START = '/api/all/mansion/start'
API_KEY_TOCHI_ALL_START = '/api/all/tochi/start'

API_KEY_MITSUI_MANSION_START = '/api/mitsui/mansion/start'
API_KEY_MITSUI_MANSION_START_GCP = '/sumifu_mansion_start'
API_KEY_MITSUI_MANSION_AREA = '/api/mitsui/mansion/area'
API_KEY_MITSUI_MANSION_AREA_GCP = '/mitsui_mansion_area'
API_KEY_MITSUI_MANSION_LIST = '/api/mitsui/mansion/list'
API_KEY_MITSUI_MANSION_LIST_GCP = '/mitsui_mansion_list'
API_KEY_MITSUI_MANSION_DETAIL = '/api/mitsui/mansion/detail'
API_KEY_MITSUI_MANSION_DETAIL_GCP = '/mitsui_mansion_detail'
API_KEY_MITSUI_MANSION_DETAIL_TEST = '/api/mitsui/mansion/detail/test'

API_KEY_MITSUI_TOCHI_START = '/api/mitsui/tochi/start'
API_KEY_MITSUI_TOCHI_START_GCP = '/sumifu_tochi_start'
API_KEY_MITSUI_TOCHI_AREA = '/api/mitsui/tochi/area'
API_KEY_MITSUI_TOCHI_AREA_GCP = '/mitsui_tochi_area'
API_KEY_MITSUI_TOCHI_LIST = '/api/mitsui/tochi/list'
API_KEY_MITSUI_TOCHI_LIST_GCP = '/mitsui_tochi_list'
API_KEY_MITSUI_TOCHI_DETAIL = '/api/mitsui/tochi/detail'
API_KEY_MITSUI_TOCHI_DETAIL_GCP = '/mitsui_tochi_detail'
API_KEY_MITSUI_TOCHI_DETAIL_TEST = '/api/mitsui/tochi/detail/test'

API_KEY_MITSUI_KODATE_START = '/api/mitsui/kodate/start'
API_KEY_MITSUI_KODATE_START_GCP = '/sumifu_kodate_start'
API_KEY_MITSUI_KODATE_AREA = '/api/mitsui/kodate/area'
API_KEY_MITSUI_KODATE_AREA_GCP = '/mitsui_kodate_area'
API_KEY_MITSUI_KODATE_LIST = '/api/mitsui/kodate/list'
API_KEY_MITSUI_KODATE_LIST_GCP = '/mitsui_kodate_list'
API_KEY_MITSUI_KODATE_DETAIL = '/api/mitsui/kodate/detail'
API_KEY_MITSUI_KODATE_DETAIL_GCP = '/mitsui_kodate_detail'
API_KEY_MITSUI_KODATE_DETAIL_TEST = '/api/mitsui/kodate/detail/test'

API_KEY_SUMIFU_MANSION_START = '/api/sumifu/mansion/start'
API_KEY_SUMIFU_MANSION_START_GCP = '/sumifu_mansion_start'
API_KEY_SUMIFU_MANSION_REGION = '/api/sumifu/mansion/region'
API_KEY_SUMIFU_MANSION_REGION_GCP = '/sumifu_mansion_region'
API_KEY_SUMIFU_MANSION_AREA = '/api/sumifu/mansion/area'
API_KEY_SUMIFU_MANSION_AREA_GCP = '/sumifu_mansion_area'
API_KEY_SUMIFU_MANSION_LIST = '/api/sumifu/mansion/list'
API_KEY_SUMIFU_MANSION_LIST_GCP = '/sumifu_mansion_list'
API_KEY_SUMIFU_MANSION_DETAIL = '/api/sumifu/mansion/detail'
API_KEY_SUMIFU_MANSION_DETAIL_GCP = '/sumifu_mansion_detail'
API_KEY_SUMIFU_MANSION_LIST_DETAIL = '/api/sumifu/mansion/listdetail'
API_KEY_SUMIFU_MANSION_LIST_DETAIL_GCP = '/sumifu_mansion_listdetail'
API_KEY_SUMIFU_MANSION_DETAIL_TEST = '/api/sumifu/mansion/detail/test'

API_KEY_SUMIFU_TOCHI_START = '/api/sumifu/tochi/start'
API_KEY_SUMIFU_TOCHI_START_GCP = '/sumifu_tochi_start'
API_KEY_SUMIFU_TOCHI_REGION = '/api/sumifu/tochi/region'
API_KEY_SUMIFU_TOCHI_REGION_GCP = '/sumifu_tochi_region'
API_KEY_SUMIFU_TOCHI_AREA = '/api/sumifu/tochi/area'
API_KEY_SUMIFU_TOCHI_AREA_GCP = '/sumifu_tochi_area'
API_KEY_SUMIFU_TOCHI_LIST = '/api/sumifu/tochi/list'
API_KEY_SUMIFU_TOCHI_LIST_GCP = '/sumifu_tochi_list'
API_KEY_SUMIFU_TOCHI_DETAIL = '/api/sumifu/tochi/detail'
API_KEY_SUMIFU_TOCHI_DETAIL_GCP = '/sumifu_tochi_detail'
API_KEY_SUMIFU_TOCHI_LIST_DETAIL = '/api/sumifu/tochi/listdetail'
API_KEY_SUMIFU_TOCHI_LIST_DETAIL_GCP = '/sumifu_tochi_listdetail'
API_KEY_SUMIFU_TOCHI_DETAIL_TEST = '/api/sumifu/tochi/detail/test'

API_KEY_SUMIFU_KODATE_START = '/api/sumifu/kodate/start'
API_KEY_SUMIFU_KODATE_START_GCP = '/sumifu_kodate_start'
API_KEY_SUMIFU_KODATE_REGION = '/api/sumifu/kodate/region'
API_KEY_SUMIFU_KODATE_REGION_GCP = '/sumifu_kodate_region'
API_KEY_SUMIFU_KODATE_AREA = '/api/sumifu/kodate/area'
API_KEY_SUMIFU_KODATE_AREA_GCP = '/sumifu_kodate_area'
API_KEY_SUMIFU_KODATE_LIST = '/api/sumifu/kodate/list'
API_KEY_SUMIFU_KODATE_LIST_GCP = '/sumifu_kodate_list'
API_KEY_SUMIFU_KODATE_DETAIL = '/api/sumifu/kodate/detail'
API_KEY_SUMIFU_KODATE_DETAIL_GCP = '/sumifu_kodate_detail'
API_KEY_SUMIFU_KODATE_LIST_DETAIL = '/api/sumifu/kodate/listdetail'
API_KEY_SUMIFU_KODATE_LIST_DETAIL_GCP = '/sumifu_kodate_listdetail'
API_KEY_SUMIFU_KODATE_DETAIL_TEST = '/api/sumifu/kodate/detail/test'

API_KEY_SUMIFU_INVEST_START = '/api/sumifu/investment/start'
API_KEY_SUMIFU_INVEST_START_GCP = '/sumifu_investment_start'
API_KEY_SUMIFU_INVEST_REGION = '/api/sumifu/investment/region'
API_KEY_SUMIFU_INVEST_REGION_GCP = '/sumifu_investment_region'
API_KEY_SUMIFU_INVEST_AREA = '/api/sumifu/investment/area'
API_KEY_SUMIFU_INVEST_AREA_GCP = '/sumifu_investment_area'
API_KEY_SUMIFU_INVEST_LIST = '/api/sumifu/investment/list'
API_KEY_SUMIFU_INVEST_LIST_GCP = '/sumifu_investment_list'
API_KEY_SUMIFU_INVEST_DETAIL = '/api/sumifu/investment/detail'
API_KEY_SUMIFU_INVEST_DETAIL_GCP = '/sumifu_investment_detail'

# Sumifu Investment Kodate (戸建て賃貸)
API_KEY_SUMIFU_INVEST_KODATE_START = '/api/sumifu/investment/kodate/start'
API_KEY_SUMIFU_INVEST_KODATE_START_GCP = '/sumifu_investment_kodate_start'
API_KEY_SUMIFU_INVEST_KODATE_LIST = '/api/sumifu/investment/kodate/list'
API_KEY_SUMIFU_INVEST_KODATE_LIST_GCP = '/sumifu_investment_kodate_list'
API_KEY_SUMIFU_INVEST_KODATE_DETAIL = '/api/sumifu/investment/kodate/detail'
API_KEY_SUMIFU_INVEST_KODATE_DETAIL_GCP = '/sumifu_investment_kodate_detail'

# Sumifu Investment Apartment (アパート)
API_KEY_SUMIFU_INVEST_APARTMENT_START = '/api/sumifu/investment/apartment/start'
API_KEY_SUMIFU_INVEST_APARTMENT_START_GCP = '/sumifu_investment_apartment_start'
API_KEY_SUMIFU_INVEST_APARTMENT_LIST = '/api/sumifu/investment/apartment/list'
API_KEY_SUMIFU_INVEST_APARTMENT_LIST_GCP = '/sumifu_investment_apartment_list'
API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL = '/api/sumifu/investment/apartment/detail'
API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL_GCP = '/sumifu_investment_apartment_detail'

# Mitsui Investment Kodate (戸建て賃貸)
API_KEY_MITSUI_INVEST_KODATE_START = '/api/mitsui/investment/kodate/start'
API_KEY_MITSUI_INVEST_KODATE_START_GCP = '/mitsui_investment_kodate_start'
API_KEY_MITSUI_INVEST_KODATE_AREA = '/api/mitsui/investment/kodate/area'
API_KEY_MITSUI_INVEST_KODATE_AREA_GCP = '/mitsui_investment_kodate_area'
API_KEY_MITSUI_INVEST_KODATE_LIST = '/api/mitsui/investment/kodate/list'
API_KEY_MITSUI_INVEST_KODATE_LIST_GCP = '/mitsui_investment_kodate_list'
API_KEY_MITSUI_INVEST_KODATE_DETAIL = '/api/mitsui/investment/kodate/detail'
API_KEY_MITSUI_INVEST_KODATE_DETAIL_GCP = '/mitsui_investment_kodate_detail'

# Mitsui Investment Apartment (アパート)
API_KEY_MITSUI_INVEST_APARTMENT_START = '/api/mitsui/investment/apartment/start'
API_KEY_MITSUI_INVEST_APARTMENT_START_GCP = '/mitsui_investment_apartment_start'
API_KEY_MITSUI_INVEST_APARTMENT_AREA = '/api/mitsui/investment/apartment/area'
API_KEY_MITSUI_INVEST_APARTMENT_AREA_GCP = '/mitsui_investment_apartment_area'
API_KEY_MITSUI_INVEST_APARTMENT_LIST = '/api/mitsui/investment/apartment/list'
API_KEY_MITSUI_INVEST_APARTMENT_LIST_GCP = '/mitsui_investment_apartment_list'
API_KEY_MITSUI_INVEST_APARTMENT_DETAIL = '/api/mitsui/investment/apartment/detail'
API_KEY_MITSUI_INVEST_APARTMENT_DETAIL_GCP = '/mitsui_investment_apartment_detail'

# Tokyu Investment Kodate (戸建て賃貸)
API_KEY_TOKYU_INVEST_KODATE_START = '/api/tokyu/investment/kodate/start'
API_KEY_TOKYU_INVEST_KODATE_START_GCP = '/tokyu_investment_kodate_start'
API_KEY_TOKYU_INVEST_KODATE_LIST = '/api/tokyu/investment/kodate/list'
API_KEY_TOKYU_INVEST_KODATE_LIST_GCP = '/tokyu_investment_kodate_list'
API_KEY_TOKYU_INVEST_KODATE_DETAIL = '/api/tokyu/investment/kodate/detail'
API_KEY_TOKYU_INVEST_KODATE_DETAIL_GCP = '/tokyu_investment_kodate_detail'

# Tokyu Investment Apartment (アパート)
API_KEY_TOKYU_INVEST_APARTMENT_START = '/api/tokyu/investment/apartment/start'
API_KEY_TOKYU_INVEST_APARTMENT_START_GCP = '/tokyu_investment_apartment_start'
API_KEY_TOKYU_INVEST_APARTMENT_LIST = '/api/tokyu/investment/apartment/list'
API_KEY_TOKYU_INVEST_APARTMENT_LIST_GCP = '/tokyu_investment_apartment_list'
API_KEY_TOKYU_INVEST_APARTMENT_DETAIL = '/api/tokyu/investment/apartment/detail'
API_KEY_TOKYU_INVEST_APARTMENT_DETAIL_GCP = '/tokyu_investment_apartment_detail'

# Nomura Investment Kodate (戸建て賃貸)
API_KEY_NOMURA_INVEST_KODATE_START = '/api/nomura/investment/kodate/start'
API_KEY_NOMURA_INVEST_KODATE_START_GCP = '/nomura_investment_kodate_start'
API_KEY_NOMURA_INVEST_KODATE_LIST = '/api/nomura/investment/kodate/list'
API_KEY_NOMURA_INVEST_KODATE_LIST_GCP = '/nomura_investment_kodate_list'
API_KEY_NOMURA_INVEST_KODATE_DETAIL = '/api/nomura/investment/kodate/detail'
API_KEY_NOMURA_INVEST_KODATE_DETAIL_GCP = '/nomura_investment_kodate_detail'

# Nomura Investment Apartment (アパート)
API_KEY_NOMURA_INVEST_APARTMENT_START = '/api/nomura/investment/apartment/start'
API_KEY_NOMURA_INVEST_APARTMENT_START_GCP = '/nomura_investment_apartment_start'
API_KEY_NOMURA_INVEST_APARTMENT_LIST = '/api/nomura/investment/apartment/list'
API_KEY_NOMURA_INVEST_APARTMENT_LIST_GCP = '/nomura_investment_apartment_list'
API_KEY_NOMURA_INVEST_APARTMENT_DETAIL = '/api/nomura/investment/apartment/detail'
API_KEY_NOMURA_INVEST_APARTMENT_DETAIL_GCP = '/nomura_investment_apartment_detail'

# Misawa Investment Kodate (戸建て賃貸)
API_KEY_MISAWA_INVEST_KODATE_START = '/api/misawa/investment/kodate/start'
API_KEY_MISAWA_INVEST_KODATE_START_GCP = '/misawa_investment_kodate_start'
API_KEY_MISAWA_INVEST_KODATE_LIST = '/api/misawa/investment/kodate/list'
API_KEY_MISAWA_INVEST_KODATE_LIST_GCP = '/misawa_investment_kodate_list'
API_KEY_MISAWA_INVEST_KODATE_DETAIL = '/api/misawa/investment/kodate/detail'
API_KEY_MISAWA_INVEST_KODATE_DETAIL_GCP = '/misawa_investment_kodate_detail'

# Misawa Investment Apartment (アパート)
API_KEY_MISAWA_INVEST_APARTMENT_START = '/api/misawa/investment/apartment/start'
API_KEY_MISAWA_INVEST_APARTMENT_START_GCP = '/misawa_investment_apartment_start'
API_KEY_MISAWA_INVEST_APARTMENT_LIST = '/api/misawa/investment/apartment/list'
API_KEY_MISAWA_INVEST_APARTMENT_LIST_GCP = '/misawa_investment_apartment_list'
API_KEY_MISAWA_INVEST_APARTMENT_DETAIL = '/api/misawa/investment/apartment/detail'
API_KEY_MISAWA_INVEST_APARTMENT_DETAIL_GCP = '/misawa_investment_apartment_detail'

API_KEY_TOKYU_MANSION_START = '/api/tokyu/mansion/start'
API_KEY_TOKYU_MANSION_START_GCP = '/sumifu_mansion_start'
API_KEY_TOKYU_MANSION_AREA = '/api/tokyu/mansion/area'
API_KEY_TOKYU_MANSION_AREA_GCP = '/tokyu_mansion_area'
API_KEY_TOKYU_MANSION_LIST = '/api/tokyu/mansion/list'
API_KEY_TOKYU_MANSION_LIST_GCP = '/tokyu_mansion_list'
API_KEY_TOKYU_MANSION_DETAIL = '/api/tokyu/mansion/detail'
API_KEY_TOKYU_MANSION_DETAIL_GCP = '/tokyu_mansion_detail'
API_KEY_TOKYU_MANSION_DETAIL_TEST = '/api/tokyu/mansion/detail/test'
API_KEY_TOKYU_MANSION_DETAIL_TEST = '/api/tokyu/mansion/detail/test'

API_KEY_TOKYU_TOCHI_START = '/api/tokyu/tochi/start'
API_KEY_TOKYU_TOCHI_START_GCP = '/tokyu_tochi_start'
API_KEY_TOKYU_TOCHI_AREA = '/api/tokyu/tochi/area'
API_KEY_TOKYU_TOCHI_AREA_GCP = '/tokyu_tochi_area'
API_KEY_TOKYU_TOCHI_LIST = '/api/tokyu/tochi/list'
API_KEY_TOKYU_TOCHI_LIST_GCP = '/tokyu_tochi_list'
API_KEY_TOKYU_TOCHI_DETAIL = '/api/tokyu/tochi/detail'
API_KEY_TOKYU_TOCHI_DETAIL_GCP = '/tokyu_tochi_detail'
API_KEY_TOKYU_TOCHI_DETAIL_TEST = '/api/tokyu/tochi/detail/test'

API_KEY_TOKYU_KODATE_START = '/api/tokyu/kodate/start'
API_KEY_TOKYU_KODATE_START_GCP = '/tokyu_kodate_start'
API_KEY_TOKYU_KODATE_AREA = '/api/tokyu/kodate/area'
API_KEY_TOKYU_KODATE_AREA_GCP = '/tokyu_kodate_area'
API_KEY_TOKYU_KODATE_LIST = '/api/tokyu/kodate/list'
API_KEY_TOKYU_KODATE_LIST_GCP = '/tokyu_kodate_list'
API_KEY_TOKYU_KODATE_DETAIL = '/api/tokyu/kodate/detail'
API_KEY_TOKYU_KODATE_DETAIL_GCP = '/tokyu_kodate_detail'
API_KEY_TOKYU_KODATE_DETAIL_TEST = '/api/tokyu/kodate/detail/test'


# Nomura Mansion
API_KEY_NOMURA_MANSION_START = '/api/nomura/mansion/start'
API_KEY_NOMURA_MANSION_START_GCP = '/nomura_mansion_start'
API_KEY_NOMURA_MANSION_REGION = '/api/nomura/mansion/region'
API_KEY_NOMURA_MANSION_REGION_GCP = '/nomura_mansion_region'
API_KEY_NOMURA_MANSION_AREA = '/api/nomura/mansion/area'
API_KEY_NOMURA_MANSION_AREA_GCP = '/nomura_mansion_area'
API_KEY_NOMURA_MANSION_LIST = '/api/nomura/mansion/list'
API_KEY_NOMURA_MANSION_LIST_GCP = '/nomura_mansion_list'
API_KEY_NOMURA_MANSION_DETAIL = '/api/nomura/mansion/detail'
API_KEY_NOMURA_MANSION_DETAIL_GCP = '/nomura_mansion_detail'

# Nomura Kodate
API_KEY_NOMURA_KODATE_START = '/api/nomura/kodate/start'
API_KEY_NOMURA_KODATE_START_GCP = '/nomura_kodate_start'
API_KEY_NOMURA_KODATE_REGION = '/api/nomura/kodate/region'
API_KEY_NOMURA_KODATE_REGION_GCP = '/nomura_kodate_region'
API_KEY_NOMURA_KODATE_AREA = '/api/nomura/kodate/area'
API_KEY_NOMURA_KODATE_AREA_GCP = '/nomura_kodate_area'
API_KEY_NOMURA_KODATE_LIST = '/api/nomura/kodate/list'
API_KEY_NOMURA_KODATE_LIST_GCP = '/nomura_kodate_list'
API_KEY_NOMURA_KODATE_DETAIL = '/api/nomura/kodate/detail'
API_KEY_NOMURA_KODATE_DETAIL_GCP = '/nomura_kodate_detail'

# Nomura Tochi
API_KEY_NOMURA_TOCHI_START = '/api/nomura/tochi/start'
API_KEY_NOMURA_TOCHI_START_GCP = '/nomura_tochi_start'
API_KEY_NOMURA_TOCHI_REGION = '/api/nomura/tochi/region'
API_KEY_NOMURA_TOCHI_REGION_GCP = '/nomura_tochi_region'
API_KEY_NOMURA_TOCHI_AREA = '/api/nomura/tochi/area'
API_KEY_NOMURA_TOCHI_AREA_GCP = '/nomura_tochi_area'
API_KEY_NOMURA_TOCHI_LIST = '/api/nomura/tochi/list'
API_KEY_NOMURA_TOCHI_LIST_GCP = '/nomura_tochi_list'
API_KEY_NOMURA_TOCHI_DETAIL = '/api/nomura/tochi/detail'
API_KEY_NOMURA_TOCHI_DETAIL_GCP = '/nomura_tochi_detail'

API_KEY_TOKYU_INVEST_START = '/api/tokyu/investment/start'
API_KEY_TOKYU_INVEST_START_GCP = '/tokyu_investment_start'
API_KEY_TOKYU_INVEST_LIST = '/api/tokyu/investment/list'
API_KEY_TOKYU_INVEST_LIST_GCP = '/tokyu_investment_list'
API_KEY_TOKYU_INVEST_DETAIL = '/api/tokyu/investment/detail'
API_KEY_TOKYU_INVEST_DETAIL_GCP = '/tokyu_investment_detail'

API_KEY_SUMIFU_INVEST_START = '/api/sumifu/investment/start'
API_KEY_SUMIFU_INVEST_START_GCP = '/sumifu_investment_start'
API_KEY_SUMIFU_INVEST_LIST = '/api/sumifu/investment/list'
API_KEY_SUMIFU_INVEST_LIST_GCP = '/sumifu_investment_list'
API_KEY_SUMIFU_INVEST_DETAIL = '/api/sumifu/investment/detail'
API_KEY_SUMIFU_INVEST_DETAIL_GCP = '/sumifu_investment_detail'

API_KEY_MISAWA_MANSION_START = '/api/misawa/mansion/start'
API_KEY_MISAWA_MANSION_LIST = '/api/misawa/mansion/list'
API_KEY_MISAWA_MANSION_DETAIL = '/api/misawa/mansion/detail'

API_KEY_MISAWA_KODATE_START = '/api/misawa/kodate/start'
API_KEY_MISAWA_KODATE_LIST = '/api/misawa/kodate/list'
API_KEY_MISAWA_KODATE_DETAIL = '/api/misawa/kodate/detail'

API_KEY_MISAWA_TOCHI_START = '/api/misawa/tochi/start'
API_KEY_MISAWA_TOCHI_LIST = '/api/misawa/tochi/list'
API_KEY_MISAWA_TOCHI_DETAIL = '/api/misawa/tochi/detail'
API_KEY_MISAWA_INVEST_START = '/api/misawa/investment/start'

API_KEY_KILL = '/api/kill'


class ApiAsyncProcBase(metaclass=ABCMeta):
    USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:61.0) Gecko/20100101 Firefox/61.1'
    headersJson = {
        'Content-Type': 'application/json',
        'User-Agent': USER_AGENT,
    }
    _loop:asyncio.BaseEventLoop = None
    middlewares: list[CrawlerMiddleware] = [LoggingMiddleware()]

    def __init__(self):
        self.parser:ParserBase = self._generateParser()
        self._getActiveEventLoop()
        self.semaphore = asyncio.Semaphore(
            value=self._getPararellLimit())

    def _getActiveEventLoop(self):
        if (self._loop is None or self._loop.is_closed()):
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def _generateConnector(self, _loop):
        # SSL Context with Legacy Support
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            # OP_LEGACY_SERVER_CONNECT = 0x4
            ctx.options |= 0x4
            ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        except:
            pass
        return aiohttp.TCPConnector(loop=_loop, limit=TCP_CONNECTOR_LIMIT, ssl=ctx)

    def _generateTimeout(self):
        _total = self._getTimeOutSecond()
        return aiohttp.ClientTimeout(total=_total)

    def _getUrl(self):
        if os.getenv('IS_CLOUD', ''):
            return "https://us-central1-sumifu.cloudfunctions.net"
        return "http://127.0.0.1:8000"

    def _getApiUrl(self):
        apiUrl = self._getUrl() + self._getApiKey()
        return apiUrl

    async def _fetchWithEachSession(self, detailUrl, apiUrl, loop):
        await self.semaphore.acquire()
        try:
            async with aiohttp.ClientSession(headers=header,loop=self._getActiveEventLoop(), connector=self._generateConnector(self._getActiveEventLoop()), timeout=self._generateTimeout()) as _session:
                try:
                    return await self._fetch(_session, detailUrl, apiUrl, loop, retryTimes=0)
                finally:
                    if _session is not None:
                        await _session.close()
        finally:
            self.semaphore.release()

    async def _apply_middlewares_request(self, request_context: Dict[str, Any]) -> Optional[Any]:
        for mw in self.middlewares:
            result = await mw.process_request(request_context)
            if result is not None:
                return result
        return None

    async def _apply_middlewares_response(self, response_context: Dict[str, Any]) -> Dict[str, Any]:
        for mw in reversed(self.middlewares):
            response_context = await mw.process_response(response_context)
        return response_context

    async def _fetch(self, session:aiohttp.ClientSession, detailUrl, apiUrl, loop, retryTimes :int):
        if os.path.exists("stop.flag"):
             logging.info("stop.flag found at start of _fetch, aborting: " + detailUrl)
             return detailUrl, 200, "Aborted"

        # Middleware request hook
        request_context = {
            'method': 'POST',
            'url': apiUrl,
            'detailUrl': detailUrl,
            'retryTimes': retryTimes
        }
        mw_result = await self._apply_middlewares_request(request_context)
        if mw_result is not None:
            return mw_result

        # Fire-and-Forget implementation:
        # Instead of waiting for the recursive API chain to complete (which can take minutes),
        # we set a short timeout to ensure the request is triggered, then disconnect.
        # This treats TimeoutError as a successful "accepted" status.
        # _timeout = self._generateTimeout()
        _timeout = aiohttp.ClientTimeout(total=3.0) 

        # Local Execution Optimization
        if not os.getenv('IS_CLOUD', ''):
            from package.api.registry import ApiRegistry
            from urllib.parse import urlparse
            import threading

            parsed = urlparse(apiUrl)
            path = parsed.path
            target_class = ApiRegistry.get(path)
            
            if target_class:
                logging.info(f"Local routing: {path} -> {target_class.__name__}")
                import threading
                
                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        target_class().main(detailUrl)
                    finally:
                        new_loop.close()

                t = threading.Thread(target=run_in_new_loop)
                t.start()
                while t.is_alive():
                    t.join(1.0)
                    if os.path.exists("stop.flag"):
                         print("stop.flag found, forcing exit...", flush=True)
                         os._exit(0)
                
                return detailUrl, 200, "LocalSync"
            else:
                 logging.warning(f"No registry found for {path}, falling back to HTTP")

        post_json_data = json.dumps(
            '{"url":"' + detailUrl + '"}').encode("utf-8")
        try:
            response:aiohttp.ClientResponse = await session.post(apiUrl, headers=self.headersJson, data=post_json_data, timeout=_timeout)
        except (aiohttp.client_exceptions.ClientConnectorError) as e:
            if(retryTimes>0):
                await asyncio.sleep(10)
                return await self._fetch(session, detailUrl, apiUrl, loop, retryTimes+1)
            else:
                logging.error("ClientConnectorError:" + detailUrl)
                #logging.error(e.__cause__)
                #logging.error(traceback.format_exc())
                #logging.error(e)
                raise e
        except (aiohttp.client_exceptions.ServerDisconnectedError) as e:
            if(retryTimes>0):
                await asyncio.sleep(10)
                return await self._fetch(session, detailUrl, apiUrl, loop, retryTimes+1)
            else:
                logging.error("ServerDisconnectedError:" + detailUrl)
                #logging.error(e.__cause__)
                #logging.error(traceback.format_exc())
                #logging.error(e)
                raise e
        except (asyncio.TimeoutError, TimeoutError) as e:
            # Fire-and-Forget Success Path
            logging.info("Fire and forget - Timeout (assumed success): " + detailUrl)
            return detailUrl, 200, "FireAndForget"
        except Exception as e:
            logging.error("fetch error:" + detailUrl)
            #logging.error(e.__cause__)
            #logging.error(traceback.format_exc())
            #logging.error(e)
            raise e
        return await self._proc_response(detailUrl, response)

    async def _proc_response(self, url, response:aiohttp.ClientResponse):
        response_context = {
            'url': url,
            'status': response.status,
            'text': await response.text(),
            'response': response
        }
        # Middleware response hook
        response_context = await self._apply_middlewares_response(response_context)
        
        if response_context.get('should_retry'):
            # Note: This simple implementation might need session management refinement
            # but follows the proposed structure.
            pass

        return url, response_context['status'], response_context['text']

    async def _run(self, _url):
        _loop = self._getActiveEventLoop()
        
        _timeout: aiohttp.ClientTimeout = self._generateTimeout()
        _connector: aiohttp.TCPConnector = self._generateConnector(_loop)
        urlList = []
        try:
            async with aiohttp.ClientSession(headers=header,loop=_loop, connector=_connector, timeout=_timeout) as session:
                try:
                    urlList = await self._treatPage(session, self._getTreatPageArg())
                except Exception as e:
                    logging.error(f"Error in _run/_treatPage for {_url}: {e}")
                    raise e
                finally:
                    if session is not None:
                        await session.close()
        finally:
            if _connector is not None:
                await _connector.close()

        return await self._callApi(urlList)

    def _afterRunProc(self, runResult):
        pass

    def main(self, url):
        self.url = url
        try:
            try:
                loop:asyncio.BaseEventLoop = self._getActiveEventLoop()
                futures = asyncio.gather(*[self._run(url)])
                runResult = loop.run_until_complete(futures)
            except asyncio.exceptions.TimeoutError as e:
                if loop.is_running():
                    loop.stop()
                futures = asyncio.gather(*[self._run(url)])
                runResult = loop.run_until_complete(futures)
        except Exception as e:
            raise e
        finally:
            if loop.is_running():
                loop.stop()
            if not loop.is_closed():
                loop.close()
        self._afterRunProc(runResult)
        return "finish", 200

    async def _save_error_html_by_url(self, url, model_name, reason="Unknown Error"):
        """Save HTML of failed property/page for debugging"""
        try:
            import re
            from pathlib import Path
            import requests
            
            error_dir = Path("src/crawler/tests/error_pages")
            error_dir.mkdir(parents=True, exist_ok=True)
            
            # e.g., SumifuMansion -> sumifu_mansion
            company_type = re.sub(r'(?<!^)(?=[A-Z])', '_', model_name).lower()
            company_dir = error_dir / company_type
            company_dir.mkdir(parents=True, exist_ok=True)
            
            # Try to extract an ID or use timestamp
            property_id = re.search(r'detail_([^/]+)', url)
            if not property_id: property_id = re.search(r'bkdetail/([^/]+)', url)
            
            p_id = property_id.group(1) if property_id else str(int(datetime.datetime.now().timestamp()))
            
            html_file = company_dir / f"{p_id}.html"
            
            response = requests.get(url, headers=header, timeout=30)
            if response.status_code == 200:
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                meta_file = company_dir / f"{p_id}_meta.txt"
                with open(meta_file, 'w', encoding='utf-8') as f:
                    f.write(f"URL: {url}\n")
                    f.write(f"Model/Class: {model_name}\n")
                    f.write(f"Timestamp: {datetime.datetime.now()}\n")
                    f.write(f"Reason: {reason}\n")
                
                logging.info(f"Saved error HTML to {html_file}")
            else:
                logging.warning(f"Failed to fetch error HTML for {url}: HTTP {response.status_code}")
        except Exception as e:
            logging.error(f"Failed to save error HTML for {url}: {e}")

    def _getPararellLimit(self):
        pararellLimit = self._getLocalPararellLimit()
        if os.getenv('IS_CLOUD', ''):
            pararellLimit = self._getCloudPararellLimit()
        return pararellLimit

    @abstractmethod
    def _generateParser(self)->ParserBase:
        pass

    @abstractmethod
    def _getLocalPararellLimit(self)->int:
        pass

    @abstractmethod
    def _getCloudPararellLimit(self)->int:
        pass

    @abstractmethod
    def _getTimeOutSecond(self)->int:
        pass

    @abstractmethod
    def _getApiKey(self):
        pass

    @abstractmethod
    async def _treatPage(self, _session, *arg):
        pass

    @abstractmethod
    def _getTreatPageArg(self):
        pass

    @abstractmethod
    async def _callApi(self, urlList):
        pass


# urlを受け取って、そのページから更にドリルダウン先を呼び出す場合の基底クラス
class ParseMiddlePageAsyncBase(ApiAsyncProcBase):

    async def _treatPage(self, _session, *arg):
        try:
            if self._isBsMiddlePage():
                 response = await self.parser.getResponseBs(_session, self.url, self.parser.getCharset())
            else:
                 response = await self.parser.getResponse(_session, self.url, self.parser.getCharset())
        except Exception as e:
            logging.error(f"Failed to fetch middle page: {self.url}")
            await self._save_error_html_by_url(self.url, self.__class__.__name__, f"Middle Page Fetch Failure: {str(e)}")
            raise e

        detailUrlList = []
        try:
            parserFunc = self._getParserFunc()
            async for detailUrl in parserFunc(response):
                detailUrlList.append(detailUrl)
        except Exception as e:
            logging.error(f"Failed to parse middle page: {self.url}")
            await self._save_error_html_by_url(self.url, self.__class__.__name__, f"Middle Page Parse Failure: {str(e)}")
            raise e
        finally:
            # 次のページを開く
            parserNextFunc = self._getNextPageParserFunc()
            if parserNextFunc is not None:
                nextPageUrl = await parserNextFunc(response)
                if len(nextPageUrl) > 0:
                    async with aiohttp.ClientSession(headers=header,loop=self._getActiveEventLoop(), connector=self._generateConnector(self._getActiveEventLoop()), timeout=self._generateTimeout()) as anotherSession:
                        try:
                            task = asyncio.create_task(self._fetch(session=anotherSession, detailUrl=nextPageUrl, apiUrl=self._getUrl(
                            ) + self._getNextPageApiKey(), loop=self._getActiveEventLoop(), retryTimes=0))  # fire and forget
                            # task = asyncio.ensure_future(self._fetch(session=anotherSession, detailUrl=nextPageUrl, apiUrl=self._getUrl() + self._getNextPageApiKey(), loop=self._getActiveEventLoop()))  # fire and forget
                            await asyncio.sleep(3)
                        finally:
                            if not (task is None or task.cancelled() or task.done()):
                                task.cancel()
                            if anotherSession is not None:
                                await anotherSession.close()

        return detailUrlList

    def _getTreatPageArg(self):
        return

    async def _callApi(self, urlList):
        tasks = []
        loop = self._getActiveEventLoop()
        for detailUrl in urlList:
            colo = self._fetchWithEachSession(
                detailUrl, self._getApiUrl(), loop)
            task = asyncio.create_task(colo)
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        return responses

    @abstractmethod
    def _getParserFunc(self):
        pass

    def _getNextPageParserFunc(self):
        return None

    def _getNextPageApiKey(self):
        return None

    def _isBsMiddlePage(self):
        return False


# 物件詳細ページのurlを受け取って、そのページ内の物件情報を取得、保存する場合の基底クラス
class ParseDetailPageAsyncBase(ApiAsyncProcBase):

    async def _run(self, _url):
        _loop = self._getActiveEventLoop()
        _timeout:int = self._generateTimeout()
        _connector = self._generateConnector(_loop)
        async with aiohttp.ClientSession(headers=header,loop=_loop, connector=_connector, timeout=_timeout) as session:
            try:
                item = await self._treatPage(session, self._getTreatPageArg())
            except Exception as e:
                logging.error(traceback.format_exc())
                logging.error(e)
                item = None
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return item

    async def _getContent(self, session, url):
        max_retries = 3
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                async with session.get(url) as response:
                    status_code = response.status
                    logging.info(f"Response status: {status_code} for URL: {url}")
                    return await response.read()
            except (aiohttp.client_exceptions.ClientConnectorError, 
                    aiohttp.client_exceptions.ServerDisconnectedError) as e:
                retry_count += 1
                if retry_count > max_retries:
                    logging.error(f"Max retries ({max_retries}) exceeded for {url}")
                    logging.error(f"Exception type: {type(e).__name__}, Details: {str(e)}")
                    raise e
                
                # Exponential backoff: 2s, 4s, 8s
                wait_time = 2 ** retry_count
                logging.warning(f"Connection error for {url}, retry {retry_count}/{max_retries} after {wait_time}s")
                logging.warning(f"Exception type: {type(e).__name__}, Details: {str(e)}")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logging.error(f"Unexpected error getting content from {url}")
                logging.error(f"Exception type: {type(e).__name__}, Details: {str(e)}")
                raise e

    async def _treatPage(self, _session, *arg):

        async def getItem():
            item = None
            _connector = self._generateConnector(self._getActiveEventLoop())
            await self.semaphore.acquire()
            try:
                # with await self.semaphore:
                async with aiohttp.ClientSession(headers=header,loop=self._getActiveEventLoop(), connector=self._generateConnector(self._getActiveEventLoop()), timeout=self._generateTimeout()) as dtlSession:
                    try:
                        item = await self.parser.parsePropertyDetailPage(session=dtlSession, url=self.url)

                    except Exception as e:
                        logging.error(f"exception get item for URL: {self.url}")
                        logging.error(f"Exception type: {type(e).__name__}, Details: {str(e)}")
                        logging.error(traceback.format_exc())
                        raise e
                    finally:
                        if dtlSession is not None:
                            await dtlSession.close()
                        if _connector is not None:
                            await _connector.close()
            finally:
                self.semaphore.release()
            return item

        retry = False
        item = None
        try:
            item = await getItem()
        except (LoadPropertyPageException, asyncio.TimeoutError, TimeoutError, ReadPropertyNameException):
            retry = True
        except SkipPropertyException as e:
            logging.info(f"Skipping property (Expected): {type(e).__name__} for URL: {self.url}")
            item = None
        except Exception as e:
            logging.error(f"get item exception for URL: {self.url}")
            logging.error(f"Exception type: {type(e).__name__}, Details: {str(e)}")
            logging.error(traceback.format_exc())
        if retry:
            logging.info("get item retry")
            try:
                item = await getItem()
            except (LoadPropertyPageException, asyncio.TimeoutError, TimeoutError, ReadPropertyNameException) as e:
                logging.error(f"get item exception (retry failed) for URL: {self.url}")
                logging.error(f"Exception type: {type(e).__name__}")
                await self._save_error_html_by_url(self.url, self.parser.createEntity().__class__.__name__, "Detail Page Retry Failure")
                CrawlerReporter.failure(self.url, self.parser.createEntity().__class__.__name__, f"Retry Failed: {str(e)}")

        if item is not None:
            currentTime = datetime.datetime.now()
            currentDay = datetime.date.today()
            item.inputDateTime = currentTime
            item.inputDate = currentDay
            try:
                logging.info(f"Attempting to save item (Single): {item.propertyName} ({item.pageUrl})")
                await sync_to_async(item.save)()
                logging.info(f"Successfully saved item (Single): {item.propertyName} ({item.pageUrl})")
                
                # Global Limit Check for Verification
                global GLOBAL_SAVE_COUNT
                try:
                    GLOBAL_SAVE_COUNT += 1
                except NameError:
                    GLOBAL_SAVE_COUNT = 1
                
                limit = int(os.getenv("CRAWLER_LIMIT", 0))
                if limit > 0:
                    logging.info(f"Global Save Count: {GLOBAL_SAVE_COUNT}/{limit}")
                    if GLOBAL_SAVE_COUNT >= limit:
                        logging.info(f"Hit limit {limit}. Exiting...")
                        os._exit(0)
                        
            except Exception as e:
                logging.error(f"Failed to save item (Single): {e} for URL: {item.pageUrl}")
                logging.error(traceback.format_exc())
            await sync_to_async(CrawlerReporter.success)(self.url, item.__class__.__name__)
        else:
             await sync_to_async(CrawlerReporter.failure)(self.url, self.parser.createEntity().__class__.__name__, "Item is None")

        return item

    def _getTreatPageArg(self):
        return

    async def _callApi(self, urlList):
        return

    async def _save_error_html_by_url(self, url, model_name, reason="Live Fetch Failure/Parsing Error"):
        """Save HTML of failed property for debugging when we only have the URL"""
        try:
            import os
            import re
            from pathlib import Path
            import requests
            import datetime
            
            error_dir = Path("src/crawler/tests/error_pages")
            error_dir.mkdir(parents=True, exist_ok=True)
            
            # e.g., SumifuMansion -> sumifu_mansion
            company_type = re.sub(r'(?<!^)(?=[A-Z])', '_', model_name).lower()
            company_dir = error_dir / company_type
            company_dir.mkdir(parents=True, exist_ok=True)
            
            property_id = re.search(r'detail_([^/]+)', url)
            property_id = property_id.group(1) if property_id else str(int(datetime.datetime.now().timestamp()))
            
            html_file = company_dir / f"{property_id}.html"
            
            response = requests.get(url, headers=header, timeout=30)
            if response.status_code == 200:
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                meta_file = company_dir / f"{property_id}_meta.txt"
                with open(meta_file, 'w', encoding='utf-8') as f:
                    f.write(f"URL: {url}\n")
                    f.write(f"Model: {model_name}\n")
                    f.write(f"Timestamp: {datetime.datetime.now()}\n")
                    f.write(f"Reason: {reason}\n")
                
                logging.info(f"Saved error HTML to {html_file}")
        except Exception as e:
            logging.error(f"Failed to save error HTML by URL: {e}")

    def _afterRunProc(self, runResult):

        def _save_error_html(item):
            """Save HTML of failed property for debugging"""
            try:
                import os
                import re
                from pathlib import Path
                import requests
                
                error_dir = Path("src/crawler/tests/error_pages")
                error_dir.mkdir(parents=True, exist_ok=True)
                
                model_name = item.__class__.__name__
                company_type = re.sub(r'(?<!^)(?=[A-Z])', '_', model_name).lower()
                
                company_dir = error_dir / company_type
                company_dir.mkdir(parents=True, exist_ok=True)
                
                url = getattr(item, 'pageUrl', '')
                property_id = re.search(r'detail_([^/]+)', url)
                if property_id:
                    property_id = property_id.group(1)
                else:
                    import time
                    property_id = str(int(time.time()))
                
                html_file = company_dir / f"{property_id}.html"
                
                try:
                    response = requests.get(url, headers=header, timeout=30)
                    if response.status_code == 200:
                        with open(html_file, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        
                        meta_file = company_dir / f"{property_id}_meta.txt"
                        with open(meta_file, 'w', encoding='utf-8') as f:
                            f.write(f"URL: {url}\n")
                            f.write(f"Property Name: {getattr(item, 'propertyName', 'UNKNOWN')}\n")
                            f.write(f"Model: {model_name}\n")
                            f.write(f"Timestamp: {datetime.datetime.now()}\n")
                        
                        logging.info(f"Saved error HTML to {html_file}")
                    else:
                        logging.warning(f"Failed to fetch HTML for {url}: HTTP {response.status_code}")
                except Exception as e:
                    logging.error(f"Failed to fetch HTML for error page {url}: {e}")
                    
            except Exception as e:
                logging.error(f"Failed to save error HTML: {e}")
                logging.error(traceback.format_exc())

        def _save(item):
            try:
                # Strict validation before save
                item.full_clean()
                logging.info(f"Attempting to save item (Batch): {item.propertyName} ({item.pageUrl})")
                item.save(False, False, None, None)
                logging.info("Successfully saved item (Batch):" + item.propertyName + ":" + item.pageUrl)
            except ValidationError as ve:
                # Detailed logging for validation failures
                msg = f"Validation failed for property: {getattr(item, 'pageUrl', 'UNKNOWN_URL')}\n"
                msg += f"Property name: {getattr(item, 'propertyName', 'UNKNOWN')}\n"
                missing_fields = []
                for field, errors in ve.message_dict.items():
                    field_value = getattr(item, field, 'N/A')
                    missing_fields.append(f"{field} (value: {field_value}): {', '.join(errors)}")
                msg += f"Missing/invalid fields: {'; '.join(missing_fields)}"
                logging.warning(msg)
                logging.warning(f"Skipping save for this property due to validation errors.")
                
                # Save HTML for debugging
                _save_error_html(item)
                # Do not re-raise, just skip this item

        logging.info("start afterRunProc")
        try:
            for item in runResult:
                if item is not None:
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            _save(item)
                            # Only close stale/expired connections
                            close_old_connections()
                            break
                        except OperationalError as e:
                            # Handle "Too many connections" (1040)
                            if attempt < max_retries - 1:
                                logging.warning(f"Database error (attempt {attempt + 1}/{max_retries}): {e}. Closing stale connections and retrying in 5 seconds...")
                                close_old_connections()
                                from time import sleep
                                sleep(5)
                            else:
                                logging.error(f"Max retries reached. Failed to save {getattr(item, 'pageUrl', 'UNKNOWN')}")
                                logging.error(traceback.format_exc())
                                raise e
                        except Exception as e:
                            logging.error("save error " +
                                          getattr(item, 'propertyName', 'UNKNOWN') + ":" + getattr(item, 'pageUrl', 'UNKNOWN_URL'))
                            logging.error(traceback.format_exc())
                            raise e
        finally:
            # Final cleanup of stale connections
            close_old_connections()
            logging.info("finished afterRunProc")

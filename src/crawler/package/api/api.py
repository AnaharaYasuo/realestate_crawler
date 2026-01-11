import asyncio
import aiohttp
import os
import json
import traceback
from abc import ABCMeta, abstractmethod
from typing import Dict, Any, Optional

from bs4 import BeautifulSoup
from package.parser.baseParser import LoadPropertyPageException, ParserBase, \
    ReadPropertyNameException
import datetime
from django.core.exceptions import ValidationError
from django.db.utils import OperationalError
from builtins import Exception
from time import sleep
import logging
from package.api.middleware import CrawlerMiddleware, LoggingMiddleware
from fake_useragent import UserAgent,FakeUserAgent
ua:FakeUserAgent = UserAgent()
header = {'User-Agent': str(ua.chrome)}


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

API_KEY_NOMURA_PRO_START = '/api/nomura/pro/start'
API_KEY_NOMURA_PRO_START_GCP = '/nomura_pro_start'
API_KEY_NOMURA_PRO_LIST = '/api/nomura/pro/list'
API_KEY_NOMURA_PRO_LIST_GCP = '/nomura_pro_list'
API_KEY_NOMURA_PRO_DETAIL = '/api/nomura/pro/detail'
API_KEY_NOMURA_PRO_DETAIL_GCP = '/nomura_pro_detail'

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
API_KEY_MISAWA_KODATE_START = '/api/misawa/kodate/start'
API_KEY_MISAWA_TOCHI_START = '/api/misawa/tochi/start'
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
        return aiohttp.TCPConnector(loop=_loop, limit=TCP_CONNECTOR_LIMIT, ssl=False)

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
                def run_worker():
                    try:
                        target_class().main(detailUrl)
                    except Exception as e:
                        logging.error(f"Worker error for {detailUrl}: {e}")
                        logging.error(traceback.format_exc())

                threading.Thread(target=run_worker).start()
                return detailUrl, 200, "FireAndForgetLocal"
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
        async with aiohttp.ClientSession(headers=header,loop=_loop, connector=_connector, timeout=_timeout) as session:
            try:
                urlList = await self._treatPage(session, self._getTreatPageArg())
            except Exception as e:
                raise e
            finally:
                if session is not None:
                    await session.close()
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
        response:BeautifulSoup = await self._generateParser().getResponse(_session, self.url, self.parser.getCharset())

        detailUrlList = []
        try:
            parserFunc = self._getParserFunc()
            async for detailUrl in parserFunc(response):
                detailUrlList.append(detailUrl)
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


# 物件詳細ページのurlを受け取って、そのページ内の物件情報を取得、保存する場合の基底クラス
class ParseDetailPageAsyncBase(ApiAsyncProcBase):

    async def _run(self, _url):
        _loop = self._getActiveEventLoop()
        _timeout:int = self._generateTimeout()
        _connector = self._generateConnector(_loop)
        async with aiohttp.ClientSession(headers=header,loop=_loop, connector=_connector, timeout=_timeout) as session:
            try:
                item = await self._treatPage(session, self._getTreatPageArg())
            except BaseException as e:
                logging.error(traceback.format_exc())
                logging.error(e)
                item = None
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return item

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
                        logging.error("exception get item")
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
        except:
            logging.error("get item exception")
        if retry:
            logging.info("get item retry")
            try:
                item = await getItem()
            except (LoadPropertyPageException, asyncio.TimeoutError, TimeoutError, ReadPropertyNameException):
                logging.error("get item exception")

        if item is not None:
            currentTime = datetime.datetime.now()
            currentDay = datetime.date.today()
            item.inputDateTime = currentTime
            item.inputDate = currentDay

        return item

    def _getTreatPageArg(self):
        return

    async def _callApi(self, urlList):
        return

    def _afterRunProc(self, runResult):

        def _save(item):
            item.save(False, False, None, None)
            logging.info("saved:" + item.propertyName + ":" + item.pageUrl)

        logging.info("start afterRunProc")
        for item in runResult:
            if item is not None:
                try:
                    _save(item)
                except (OperationalError) as e:  # too many connection
                    logging.error(traceback.format_exc())
                    logging.error(e.__cause__)
                    sleep(30)  # 30秒待機
                    _save(item)   
                except (Exception, ValidationError) as e:
                    logging.error("save error " +
                                  item.propertyName + ":" + item.pageUrl)
                    logging.error(traceback.format_exc())
                    logging.error(e.__cause__)
                    raise e

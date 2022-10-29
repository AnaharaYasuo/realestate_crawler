import asyncio
import aiohttp
import os
import json
import traceback
from abc import ABCMeta, abstractmethod

from bs4 import BeautifulSoup
from package.parser.baseParser import LoadPropertyPageException, ParserBase, \
    ReadPropertyNameException
import datetime
from django.core.exceptions import ValidationError
from django.db.utils import OperationalError
from builtins import Exception
from time import sleep
import logging
from fake_useragent import UserAgent
ua = UserAgent()
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
API_KEY_KILL = '/api/kill'


class ApiAsyncProcBase(metaclass=ABCMeta):
    USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:61.0) Gecko/20100101 Firefox/61.1'
    headersJson = {
        'Content-Type': 'application/json',
        'User-Agent': USER_AGENT,
    }
    _loop:asyncio.BaseEventLoop = None

    def __init__(self):
        self.parser:ParserBase = self._generateParser()
        self._getActiveEventLoop()
        self.semaphore = asyncio.Semaphore(
            value=self._getPararellLimit(), loop=self._loop)

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

    async def _fetch(self, session:aiohttp.ClientSession, detailUrl, apiUrl, loop, retryTimes :int):
        _timeout = self._generateTimeout()
        post_json_data = json.dumps(
            '{"url":"' + detailUrl + '"}').encode("utf-8")
        try:
            response:aiohttp.ClientResponse = await session.post(apiUrl, headers=self.headersJson, data=post_json_data, timeout=_timeout)
        except (aiohttp.client_exceptions.ClientConnectorError):
            if(retryTimes>0):
                sleep(10000)
                self._fetch(session, detailUrl, apiUrl, loop, retryTimes+1)
            else:
                logging.error("ClientConnectorError:" + detailUrl)
                #logging.error(e.__cause__)
                #logging.error(traceback.format_exc())
                #logging.error(e)
                raise e
        except (aiohttp.client_exceptions.ServerDisconnectedError):
            if(retryTimes>0):
                sleep(10000)
                self._fetch(session, detailUrl, apiUrl, loop, retryTimes+1)
            #_connector = self._generateConnector(self._getActiveEventLoop())
            #async with aiohttp.ClientSession(headers=header,loop=loop, connector=_connector, timeout=_timeout) as retrySession:
            #    try:
            #        response = await retrySession.post(apiUrl, headers=self.headersJson, data=post_json_data, timeout=_timeout)
            #    finally:
            #        if retrySession is not None:
            #            await retrySession.close()
            #        if _connector is not None:
            #            await _connector.close()
            else:
                logging.error("ServerDisconnectedError:" + detailUrl)
                #logging.error(e.__cause__)
                #logging.error(traceback.format_exc())
                #logging.error(e)
                raise e
        except (asyncio.TimeoutError, TimeoutError) as e:
            logging.error("TimeoutError:" + detailUrl)
            #logging.error(e.__cause__)
            #logging.error(traceback.format_exc())
            #logging.error(e)
            raise e
        except Exception as e:
            logging.error("fetch error:" + detailUrl)
            #logging.error(e.__cause__)
            #logging.error(traceback.format_exc())
            #logging.error(e)
            raise e
        return await self._proc_response(detailUrl, response)

    async def _proc_response(self, url, response:aiohttp.ClientResponse):
        return url, response.status, await response.text()

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
                futures = asyncio.gather(*[self._run(url)], loop=loop)
                runResult = loop.run_until_complete(futures)
            except asyncio.exceptions.TimeoutError as e:
                if loop.is_running():
                    loop.stop()
                futures = asyncio.gather(*[self._run(url)], loop=loop)
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
                            sleep(3)
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

        responses = await asyncio.gather(*tasks, loop=self._getActiveEventLoop())
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
                    except ReadPropertyNameException:
                        item = None
                        logging.warn("None get item")
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
        except (LoadPropertyPageException, asyncio.TimeoutError, TimeoutError):
            retry = True
        except:
            logging.error("get item exception")
        if retry:
            logging.info("get item retry")
            try:
                item = await getItem()
            except (LoadPropertyPageException, asyncio.TimeoutError, TimeoutError):
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
                    sleep(30000)  # u30秒待機
                    _save(item)   
                except (Exception, ValidationError) as e:
                    logging.error("save error " +
                                  item.propertyName + ":" + item.pageUrl)
                    logging.error(traceback.format_exc())
                    logging.error(e.__cause__)
                    raise e

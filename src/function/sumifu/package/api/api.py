import asyncio
import aiohttp
import os
import json
import traceback
from abc import ABCMeta, abstractmethod
from package.parser.baseParser import LoadPropertyPageException, \
    ReadPropertyNameException
import datetime
from django.core.exceptions import ValidationError
from django.db.utils import OperationalError
from builtins import Exception
from time import sleep
import logging

API_KEY_ALL_START = '/api/all/mansion/start'
API_KEY_MITSUI_START = '/api/mitsui/mansion/start'
API_KEY_MITSUI_START_GCP = '/sumifu_mansion_start'
API_KEY_MITSUI_AREA = '/api/mitsui/mansion/area'
API_KEY_MITSUI_AREA_GCP = '/mitsui_mansion_area'
API_KEY_MITSUI_LIST = '/api/mitsui/mansion/list'
API_KEY_MITSUI_LIST_GCP = '/mitsui_mansion_list'
API_KEY_MITSUI_DETAIL = '/api/mitsui/mansion/detail'
API_KEY_MITSUI_DETAIL_GCP = '/mitsui_mansion_detail'
API_KEY_MITSUI_DETAIL_TEST = '/api/mitsui/mansion/detail/test'

API_KEY_SUMIFU_START = '/api/sumifu/mansion/start'
API_KEY_SUMIFU_START_GCP = '/sumifu_mansion_start'
API_KEY_SUMIFU_REGION = '/api/sumifu_mansion/region'
API_KEY_SUMIFU_REGION_GCP = '/sumifu_mansion_region'
API_KEY_SUMIFU_AREA = '/api/sumifu/mansion/area'
API_KEY_SUMIFU_AREA_GCP = '/sumifu_mansion_area'
API_KEY_SUMIFU_LIST = '/api/sumifu/mansion/list'
API_KEY_SUMIFU_LIST_GCP = '/sumifu_mansion_list'
API_KEY_SUMIFU_DETAIL = '/api/sumifu/mansion/detail'
API_KEY_SUMIFU_DETAIL_GCP = '/sumifu_mansion_detail'
API_KEY_SUMIFU_LIST_DETAIL = '/api/sumifu/mansion/listdetail'
API_KEY_SUMIFU_LIST_DETAIL_GCP = '/sumifu_mansion_listdetail'
API_KEY_SUMIFU_DETAIL_TEST = '/api/sumifu/mansion/detail/test'

API_KEY_TOKYU_START = '/api/tokyu/mansion/start'
API_KEY_TOKYU_START_GCP = '/sumifu_mansion_start'
API_KEY_TOKYU_AREA = '/api/tokyu/mansion/area'
API_KEY_TOKYU_AREA_GCP = '/tokyu_mansion_area'
API_KEY_TOKYU_LIST = '/api/tokyu/mansion/list'
API_KEY_TOKYU_LIST_GCP = '/tokyu_mansion_list'
API_KEY_TOKYU_DETAIL = '/api/tokyu/mansion/detail'
API_KEY_TOKYU_DETAIL_GCP = '/tokyu_mansion_detail'
API_KEY_TOKYU_DETAIL_TEST = '/api/tokyu/mansion/detail/test'
API_KEY_KILL = '/api/kill'


class ApiAsyncProcBase(metaclass=ABCMeta):
    USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:61.0) Gecko/20100101 Firefox/61.1'
    headersJson = {
        'Content-Type': 'application/json',
        'User-Agent': USER_AGENT,
    }
    _loop = None

    def __init__(self):
        self.parser = self._generateParser()
        self._getActiveEventLoop()
        self.semaphore = asyncio.Semaphore(value=self._getPararellLimit(), loop=self._loop)

    def _getActiveEventLoop(self):
        if (self._loop is None or self._loop.is_closed()):
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(None)
        return self._loop

    def _generateConnector(self, _loop):
        return aiohttp.TCPConnector(loop=_loop, limit=40, ssl=False)
    
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
            async with aiohttp.ClientSession(loop=self._getActiveEventLoop(), connector=self._generateConnector(self._getActiveEventLoop()), timeout=self._generateTimeout()) as _session:
                try:
                    return await self._fetch(_session, detailUrl, apiUrl, loop)
                finally:
                    if _session is not None:
                        await _session.close()
        finally:
            self.semaphore.release()
            
#        with await self.semaphore:
#            async with aiohttp.ClientSession(loop=self._getActiveEventLoop(), connector=self._generateConnector(self._getActiveEventLoop()), timeout=self._generateTimeout()) as _session:
#                try:
#                    return await self._fetch(_session, detailUrl, apiUrl, loop)
#                finally:
#                    if _session is not None:
#                        await _session.close()

    async def _fetch(self, session, detailUrl, apiUrl, loop):
        _timeout = self._generateTimeout()
        post_json_data = json.dumps('{"url":"' + detailUrl + '"}').encode("utf-8")
        try:
            response = await session.post(apiUrl, headers=self.headersJson, data=post_json_data, timeout=_timeout)
        except (aiohttp.client_exceptions.ClientConnectorError, aiohttp.client_exceptions.ServerDisconnectedError):
            sleep(10000)
            _connector = self._generateConnector(self._getActiveEventLoop())
            async with aiohttp.ClientSession(loop=loop, connector=_connector, timeout=_timeout) as retrySession:
                try:
                    response = await session.post(apiUrl, headers=self.headersJson, data=post_json_data, timeout=_timeout)
                finally:
                    if retrySession is not None:
                        await retrySession.close()
                    if _connector is not None:
                        await _connector.close()
        except (asyncio.TimeoutError, TimeoutError) as e:
            logging.error("call api timeout error:" + detailUrl)
            raise e
        except Exception as e:
            logging.error("fetch error:" + detailUrl)
            raise e
        return await self._proc_response(detailUrl, response)
    
    async def _proc_response(self, url, response):
        return url, response.status, await response.text()

    async def _run(self, _url):
        _loop = self._getActiveEventLoop()
        _timeout = self._generateTimeout()
        _connector = self._generateConnector(_loop)
        urlList = []
        async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as session:
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
            loop = self._getActiveEventLoop();
            futures = asyncio.gather(*[self._run(url)], loop=loop)
            runResult = loop.run_until_complete(futures)
        except Exception as e:
            raise e
        finally:
            loop.close()
        self._afterRunProc(runResult)
        return "finish", 200;

    def _getPararellLimit(self):
        pararellLimit = self._getLocalPararellLimit()
        if os.getenv('IS_CLOUD', ''):
            pararellLimit = self._getCloudPararellLimit()
        return pararellLimit

    @abstractmethod
    def _generateParser(self):
        pass

    @abstractmethod
    def _getLocalPararellLimit(self):
        pass

    @abstractmethod
    def _getCloudPararellLimit(self):
        pass

    @abstractmethod
    def _getTimeOutSecond(self):
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
        response = await self._generateParser().getResponse(_session, self.url, self.parser.getCharset())

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
                    async with aiohttp.ClientSession(loop=self._getActiveEventLoop(), connector=self._generateConnector(self._getActiveEventLoop()), timeout=self._generateTimeout()) as anotherSession:
                        try:
                            task = asyncio.create_task(self._fetch(session=anotherSession, detailUrl=nextPageUrl, apiUrl=self._getUrl() + self._getNextPageApiKey(), loop=self._getActiveEventLoop()))  # fire and forget
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
            colo = self._fetchWithEachSession(detailUrl, self._getApiUrl(), loop)
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
        _timeout = self._generateTimeout()
        _connector = self._generateConnector(_loop)
        async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as session:
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

    async def _treatPage(self, _session, *arg):

        async def getItem():
            item = None
            _connector = self._generateConnector(self._getActiveEventLoop())
            await self.semaphore.acquire()
            try:
            #with await self.semaphore:
                async with aiohttp.ClientSession(loop=self._getActiveEventLoop(), connector=self._generateConnector(self._getActiveEventLoop()), timeout=self._generateTimeout()) as dtlSession:
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
        except :
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
                    sleep(30000);  # u30秒待機
                    _save(item)
                except (Exception, ValidationError) as e:
                    logging.error("save error " + item.propertyName + ":" + item.pageUrl)
                    raise e

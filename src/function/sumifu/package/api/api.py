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

API_KEY_TOKYU_START = '/api/tokyu/mansion/start'
API_KEY_TOKYU_START_GCP = '/sumifu_mansion_start'
API_KEY_TOKYU_AREA = '/api/tokyu/mansion/area'
API_KEY_TOKYU_AREA_GCP = '/tokyu_mansion_area'
API_KEY_TOKYU_LIST = '/api/tokyu/mansion/list'
API_KEY_TOKYU_LIST_GCP = '/tokyu_mansion_list'
API_KEY_TOKYU_DETAIL = '/api/tokyu/mansion/detail'
API_KEY_TOKYU_DETAIL_GCP = '/tokyu_mansion_detail'
API_KEY_TOKYU_DETAIL_TEST = '/api/tokyu/mansion/detail/test'


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

    async def _fetch(self, session, detailUrl, apiUrl, loop):
        _timeout = self._generateTimeout()
        post_json_data = json.dumps('{"url":"' + detailUrl + '"}').encode("utf-8")
        try:
            response = await session.post(apiUrl, headers=self.headersJson, data=post_json_data, timeout=_timeout)
        except (asyncio.TimeoutError, TimeoutError, aiohttp.client_exceptions.ClientConnectorError, aiohttp.client_exceptions.ServerDisconnectedError):
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
        except Exception as e:
            print("fetch error:" + detailUrl)
            print(traceback.format_exc())
            raise e
        return await self._proc_response(detailUrl, response)
    
    async def _bound_fetch(self, session, detailUrl):
        # async with
        # __aenter__がasync with ブロックを呼んだ直後に呼ばれる
        # __aexit__がasync with ブロックを抜けた直後に呼ばれる
        with await self.semaphore:
            loop = self._getActiveEventLoop()
            return await self._fetch(session, detailUrl, self._getApiUrl(), loop)

    async def _proc_response(self, url, response):
        return url, response.status, await response.text()

    async def _run(self, _url):
        responses = None
        _loop = self._getActiveEventLoop()
        _timeout = self._generateTimeout()
        _connector = self._generateConnector(_loop)
        async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as session:
            try:
                responses = await self._treatPage(session, self._getTreatPageArg())
            except Exception as e:
                print(traceback.format_exc())
                print(e)
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return responses
    
    def _afterRunProc(self, runResult):
        pass
    
    def main(self, url):
        self.url = url
        try:
            loop = self._getActiveEventLoop();
            futures = asyncio.gather(*[self._run(url)], loop=loop)
            runResult = loop.run_until_complete(futures)
        except:
            return "error end", 500;
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


# urlを受け取って、そのページから更にドリルダウン先を呼び出す場合の基底クラス
class ParseMiddlePageAsyncBase(ApiAsyncProcBase):

    async def _treatPage(self, _session, *arg):
        tasks = []
        response = await self._generateParser().getResponse(_session, self.url, self.parser.getCharset())

        try:
            parserFunc = self._getParserFunc()
            async for detailUrl in parserFunc(response):
                # colo = self._fetch(session=_session, detailUrl=detailUrl, apiUrl=self._getApiUrl(), loop=self._getActiveEventLoop())
                colo = self._bound_fetch(session=_session, detailUrl=detailUrl)
                # task = asyncio.ensure_future(colo)
                task = asyncio.create_task(colo)
                tasks.append(task)
        finally:
            # 次のページを開く
            parserNextFunc = self._getNextPageParserFunc()
            if parserNextFunc is not None:
                nextPageUrl = await parserNextFunc(response)
                if len(nextPageUrl) > 0:
                    asyncio.ensure_future(self._fetch(session=_session, detailUrl=nextPageUrl, apiUrl=self._getUrl() + self._getNextPageApiKey(), loop=self._getActiveEventLoop()))  # fire and forget                
            
        responses = await asyncio.gather(*tasks)

        return responses

    def _getTreatPageArg(self):
        return 

    @abstractmethod
    def _getParserFunc(self):
        pass

    def _getNextPageParserFunc(self):
        return None

    def _getNextPageApiKey(self):
        return None


# 物件詳細ページのurlを受け取って、そのページ内の物件情報を取得、保存する場合の基底クラス
class ParseDetailPageAsyncBase(ApiAsyncProcBase):

    async def _treatPage(self, _session, *arg):

        async def getItem(_timeout):
            item = None
            _connector = self._generateConnector(self._getActiveEventLoop())
            with await self.semaphore:
                async with aiohttp.ClientSession(loop=self._getActiveEventLoop(), connector=_connector, timeout=_timeout) as dtlSession:
                    try:
                        item = await self.parser.parsePropertyDetailPage(session=dtlSession, url=self.url)
                    except ReadPropertyNameException:
                        item = None
                        print("None get item")
                    except Exception:
                        print("exception get item")
                    finally:
                        if dtlSession is not None:
                            await dtlSession.close()
                        if _connector is not None:
                            await _connector.close()
            return item

        _timeout = self._generateTimeout()
        retry = False
        try:
            item = await getItem(_timeout)
        except (LoadPropertyPageException, asyncio.TimeoutError, TimeoutError):
            retry = True
        except :
            print("get item exception")
        if retry:
            print("get item retry")
            item = await getItem(_timeout)

        if item is not None:
            currentTime = datetime.datetime.now()
            currentDay = datetime.date.today()
            item.inputDateTime = currentTime
            item.inputDate = currentDay

        return item

    def _getTreatPageArg(self):
        return 
    
    def _afterRunProc(self, runResult):

        def _save(item):
            item.save(False, False, None, None)
            print(item.propertyName + ":" + item.pageUrl)

        for item in runResult:
            if item is not None:
                try:
                    _save(item)
                except (OperationalError) as e:  # too many connection
                    sleep(30000);  # u30秒待機
                    _save(item)
                except (Exception, ValidationError) as e:
                    print("save error " + item.propertyName + ":" + item.pageUrl)
                    print(traceback.format_exc())
                    print(e)

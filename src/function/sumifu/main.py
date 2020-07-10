import asyncio
import datetime
import aiohttp
import os
import django
from django.conf import settings
import traceback
from concurrent.futures._base import TimeoutError

# cloud functionsとComputeEngineはサーバーレスVPCで接続している

# デバッグ方法
# PythonRunよりデバッグを開始するとflaskが起動。
# そのうえで、http://127.0.0.1:8000/api/sumifu/mansion/startにアクセス

API_KEY_START = '/api/sumifu/mansion/start'
API_KEY_START_GCP = '/sumifu_mansion_start'
API_KEY_START_KANTO = '/api/sumifu/mansion/start/kanto'
API_KEY_REGION = '/api/sumifu_mansion/region'
API_KEY_REGION_GCP = '/sumifu_mansion_region'
API_KEY_AREA = '/api/sumifu/mansion/area'
API_KEY_AREA_GCP = '/sumifu_mansion_area'
API_KEY_LIST = '/api/sumifu/mansion/list'
API_KEY_LIST_GCP = '/sumifu_mansion_list'
API_KEY_DETAIL = '/api/sumifu/mansion/detail'
API_KEY_DETAIL_GCP = '/sumifu_mansion_detail'
API_KEY_LIST_DETAIL = '/api/sumifu/mansion/listdetail'
API_KEY_LIST_DETAIL_GCP = '/sumifu_mansion_listdetail'

if not settings.configured:
    if os.getenv('IS_CLOUD', ''):
        settings.configure(
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.mysql',
                    'NAME': 'real_estate',
                    'USER': 'sumifu',
                    'PASSWORD': 'mayumimayumi0413',
                    'HOST': '10.128.0.2',
                    'PORT': '13306',
                }
            }
            , INSTALLED_APPS=[
                 'package.apps.SumifuappConfig'
                # 'main.SumifuappConfig'
            ]
        )
    else:
        settings.configure(
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.mysql',
                    'NAME': 'real_estate',
                    'USER': 'sumifu',
                    'PASSWORD': 'mayumimayumi0413',
                    'HOST': '104.154.246.240',
                    'PORT': '13306',
                }
            }
            , INSTALLED_APPS=[
                 'package.apps.SumifuappConfig'
                # 'main.SumifuappConfig'
            ]
        )
    django.setup()
from package.getsumifu import GetSumifu, ReadPropertyNameException,\
    LoadPropertyPageException
from flask import jsonify

# from package.getsumifu import GetSumifu
# import requests
import json

USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:61.0) Gecko/20100101 Firefox/61.1'
headersJson = {
    'Content-Type': 'application/json',
    'User-Agent': USER_AGENT,
}

# loop = asyncio.get_event_loop()

currentDay = datetime.date.today()


def _getListApiKey():
    key = API_KEY_LIST#listとdetailを別の関数内で処理で行う
    # key = API_KEY_LIST_DETAIL  # listとdetailを同じ関数内で処理で行う
    return key


def _getListApiKeyGCP():
    # key = API_KEY_LIST_GCP#listとdetailを別の関数内で処理で行う
    key = API_KEY_LIST_DETAIL_GCP  # listとdetailを同じ関数内で処理で行う
    return key


def _getConnector(_loop):
    return aiohttp.TCPConnector(loop=_loop, limit=40, ssl=False)


def _getTimeout(_total):
    return aiohttp.ClientTimeout(total=_total)


def parseStartAsyncPubSub(event, context):
    parseStartAsync("")


def _callRegionAsync(targetUrl):

    def _getApiKey():
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_REGION_GCP
        return API_KEY_REGION

    async def _run(_loop, detailUrl, limit=1):
        responses = None
        tasks = []
        semaphore = asyncio.Semaphore(limit)
        _total = 3600
        _timeout = _getTimeout(_total)
        _connector=_getConnector(_loop)
        async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as session:
            try:
                task = asyncio.ensure_future(_bound_fetch(semaphore=semaphore, session=session, timeout=_timeout, apiUrl=apiUrl, detailUrl=detailUrl))
                tasks.append(task)
                responses = await asyncio.gather(*tasks)
            except Exception as e:
                # do nothing
                print("_callRegionAsync run error")
                print(traceback.format_exc())
                print(e)
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return responses

    apiUrl = getUrl() + _getApiKey()
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        pararellLimit = 2
        if os.getenv('IS_CLOUD', ''):
            pararellLimit = 10
        futures = asyncio.gather(*[_run(loop, targetUrl, pararellLimit)])
        loop.run_until_complete(futures)
    finally:
        loop.close()
    return "no respons in _callRegionAsync", 200;


def parseStartKantoAsync(request):
    targetUrl = "https://www.stepon.co.jp/mansion/shutoken/"
    return _callRegionAsync(targetUrl)


def parseStartAsync(request):

    urlList = ["https://www.stepon.co.jp/mansion/tokai/"
    , "https://www.stepon.co.jp/mansion/shutoken/"
    , "https://www.stepon.co.jp/mansion/kansai/"
    , "https://www.stepon.co.jp/mansion/hokkaido/"
    , "https://www.stepon.co.jp/mansion/tohoku/"
    , "https://www.stepon.co.jp/mansion/chugoku/"
    , "https://www.stepon.co.jp/mansion/kyushu/"]

    def _getApiKey():
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_REGION_GCP
        return API_KEY_REGION

    async def _run(_loop, limit=1):
        responses = None
        tasks = []
        semaphore = asyncio.Semaphore(limit)
        _total = 3600
        _timeout = _getTimeout(_total)
        _connector=_getConnector(_loop)
        async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as session:
            try:
                for detailUrl in urlList:
                    task = asyncio.ensure_future(_bound_fetch(semaphore=semaphore, session=session, timeout=_timeout, apiUrl=apiUrl, detailUrl=detailUrl))
                    tasks.append(task)
                responses = await asyncio.gather(*tasks)
            except Exception as e:
                # do nothing
                print("parseStartAsync run error")
                print(traceback.format_exc())
                print(e)
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return responses

    apiUrl = getUrl() + _getApiKey()
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        pararellLimit = 7
        if os.getenv('IS_CLOUD', ''):
            pararellLimit = 10
        futures = asyncio.gather(*[_run(loop, pararellLimit)])
        loop.run_until_complete(futures)
    finally:
        loop.close()
    return "no respons in parseRegionStart", 200;


def parseRegionFuncAsync(request):

    def _getApiKey():
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_AREA_GCP
        return API_KEY_AREA

    async def _run(_loop, url, limit=1):
        responses = None
        tasks = []
        _total = 3600
        semaphore = asyncio.Semaphore(limit)
        _timeout = _getTimeout(_total)
        _connector=_getConnector(_loop)
        async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as session:
            try:
                async for detailUrl in sumifu.parseRegionPage(session, url):
                    task = asyncio.ensure_future(_bound_fetch(semaphore=semaphore, session=session, timeout=_timeout, apiUrl=apiUrl, detailUrl=detailUrl))
                    tasks.append(task)
                responses = await asyncio.gather(*tasks)
            except Exception as e:
                # do nothing
                print("parseRegionFuncAsync run error")
                print(traceback.format_exc())
                print(e)
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return responses

    request_json = json.loads(request.get_json())
    url = request_json['url']
    sumifu = GetSumifu("params")
    apiUrl = getUrl() + _getApiKey()
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        pararellLimit = 2
        if os.getenv('IS_CLOUD', ''):
            pararellLimit = 10
        futures = asyncio.gather(*[_run(loop, url, pararellLimit)])
        loop.run_until_complete(futures)
    finally:
        loop.close()
    return "no respons in parseRegionFunc", 200;


def parseAreaFuncAsync(request):

    def _getApiKey():
        if os.getenv('IS_CLOUD', ''):
            return _getListApiKeyGCP()
        return _getListApiKey()

    async def _run(_loop, url, limit=1):
        responses = None
        tasks = []
        _total = 600
        semaphore = asyncio.Semaphore(limit)
        _timeout = _getTimeout(_total)
        _connector=_getConnector(_loop)
        async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as session:
            try:
                async for detailUrl in sumifu.parseAreaPage(session, url):
                    task = asyncio.ensure_future(_bound_fetch(semaphore=semaphore, session=session, timeout=_timeout, apiUrl=apiUrl, detailUrl=detailUrl))
                    tasks.append(task)
                responses = await asyncio.gather(*tasks)
            except Exception as e:
                print("parseAreaFuncAsync run error")
                print(traceback.format_exc())
                print(e)
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return responses

    request_json = json.loads(request.get_json())
    url = request_json['url']
    sumifu = GetSumifu("params")
    apiUrl = getUrl() + _getApiKey()
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        pararellLimit = 2
        if os.getenv('IS_CLOUD', ''):
            pararellLimit = 50
        futures = asyncio.gather(*[_run(loop, url, pararellLimit)])
        loop.run_until_complete(futures)
    finally:
        loop.close()
    return "no respons in parseAreaFuncAsync", 200;


def parseListFuncAsync(request):

    def _getApiKey():
        if os.getenv('IS_CLOUD', ''):
            return API_KEY_DETAIL_GCP
        return API_KEY_DETAIL

    async def _run(_loop, url, limit=1):
        responses = None
        tasks = []
        _total = 60
        semaphore = asyncio.Semaphore(limit)
        _timeout = _getTimeout(_total)
        _connector=_getConnector(_loop)
        async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as session:
            try:
                async for detailUrl in sumifu.parsePropertyListPage(session, url):
                    task = asyncio.ensure_future(_bound_fetch(semaphore=semaphore, session=session, timeout=_timeout, apiUrl=apiUrl, detailUrl=detailUrl))
                    tasks.append(task)
                responses = await asyncio.gather(*tasks)
            except Exception as e:
                # do nothing
                print("parseListFuncAsync run error")
                print(traceback.format_exc())
                print(e)
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return responses

    # url = "https://www.stepon.co.jp/mansion/area_23/list_23_101/100_1/"
    request_json = json.loads(request.get_json())
    url = request_json['url']
    sumifu = GetSumifu("params")
    apiUrl = getUrl() + _getApiKey()
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        pararellLimit = 2
        if os.getenv('IS_CLOUD', ''):
            pararellLimit = 10
        futures = asyncio.gather(*[_run(loop, url, pararellLimit)])
        loop.run_until_complete(futures)
    finally:
        loop.close()
    return "no respons in parseListFuncAsync", 200;


def parseDetailFuncAsync(request):

    async def _run(_loop, url):
        async def _runParsePropertyDetailPage(sumifu, _loop, _timeout, detailUrl):
            async def getItem(sumifu, _loop, _timeout, detailUrl):
                item = None
                _connector=_getConnector(loop)
                async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as dtlSession:
                    try:
                        item = await sumifu.parsePropertyDetailPage(session=dtlSession, url=detailUrl)
                    except ReadPropertyNameException:
                        item=None
                    finally:
                        if dtlSession is not None:
                            await dtlSession.close()
                        if _connector is not None:
                            await _connector.close()
                return item
            
            retry=False
            try:
                item = await getItem(sumifu, _loop, _timeout, detailUrl)
            except (LoadPropertyPageException,asyncio.TimeoutError,TimeoutError):
                retry=True
            if retry:
                retry=False
                try:
                    item = await getItem(sumifu, _loop, _timeout, detailUrl)
                except (LoadPropertyPageException,asyncio.TimeoutError,TimeoutError):
                    retry=True
            if retry:
                item = await getItem(sumifu, _loop, _timeout, detailUrl)
            return item

        responses = None
        tasks = []
        _total = 60
        # semaphore = asyncio.Semaphore(limit)
        _timeout = _getTimeout(_total)
        _connector=_getConnector(_loop)
        async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as session:
            try:
                #task = asyncio.ensure_future(sumifu.parsePropertyDetailPage(session=session, url=url))
                task = asyncio.ensure_future(_runParsePropertyDetailPage(sumifu, _loop, _timeout, url))
                tasks.append(task)
                responses = await asyncio.gather(*tasks)
            except Exception as e:
                # do nothing
                print("parseDetailFuncAsync run error")
                print(traceback.format_exc())
                print(e)
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return responses

    request_json = json.loads(request.get_json())
    url = request_json['url']
    sumifu = GetSumifu("params")
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        futures = asyncio.gather(*[_run(loop, url)])
        itemLists = loop.run_until_complete(futures)
    finally:
        loop.close()
        
    for itemList in itemLists:
        while len(itemList) > 0:
            item = itemList.pop()  # memory release
            if item is not None:
                currentTime = datetime.datetime.now()
                currentDay = datetime.date.today()
                item.inputDateTime = currentTime
                item.inputDate = currentDay
                print(item.propertyName+":"+item.pageUrl)
                try:
                    item.save(False, False, None, None)
                except Exception as e:
                    print("save error")
                    print(traceback.format_exc())
                    print(e)
                    # raise e
    return jsonify({'message': url}), 200;


def parseListDetailFuncAsync(request):

    async def _run(_loop, url, limit=1):
        async def _runParsePropertyDetailPage(sumifu, _loop, _timeout, detailUrl):
            async def getItem(sumifu, _loop, _timeout, detailUrl):
                item = None
                _connector=_getConnector(loop)
                async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as dtlSession:
                    try:
                        item = await sumifu.parsePropertyDetailPage(session=dtlSession, url=detailUrl)
                    except ReadPropertyNameException:
                        item=None
                    finally:
                        if dtlSession is not None:
                            await dtlSession.close()
                        if _connector is not None:
                            await _connector.close()
                return item
            
            retry=False
            try:
                item = await getItem(sumifu, _loop, _timeout, detailUrl)
            except (LoadPropertyPageException,asyncio.TimeoutError,TimeoutError):
                retry=True
            if retry:
                retry=False
                try:
                    item = await getItem(sumifu, _loop, _timeout, detailUrl)
                except (LoadPropertyPageException,asyncio.TimeoutError,TimeoutError):
                    retry=True
            if retry:
                item = await getItem(sumifu, _loop, _timeout, detailUrl)
            return item

        semaphore = asyncio.Semaphore(limit)
        responses = None
        tasks = []
        _total = 60
        _timeout = _getTimeout(_total)
        _connector=_getConnector(loop)
        async with aiohttp.ClientSession(loop=loop, connector=_connector, timeout=_timeout) as session:
            try:
                async for detailUrl in sumifu.parsePropertyListPage(session, url):
                    # task = asyncio.ensure_future(sumifu.parsePropertyDetailPage(session=session, url=detailUrl))
                    task = asyncio.ensure_future(_runParsePropertyDetailPage(sumifu, _loop, _timeout, detailUrl))
                    tasks.append(task)
                async with semaphore:
                    responses = await asyncio.gather(*tasks)
            except Exception as e:
                # do nothing
                print("parseListDetailFuncAsync run error")
                print(traceback.format_exc())
                print(e)
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return responses
            
    async def _getNextPageUrl(_loop, url, limit=1):
        semaphore = asyncio.Semaphore(limit)
        _total = 60
        _timeout = _getTimeout(_total)
        _connector=_getConnector(_loop)
        async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as session:
            nextPageUrlList = None
            try:
                async with semaphore:
                    nextPageUrlList = await sumifu.getPropertyListNextPageUrl(session, url)
            except Exception as e:
                # do nothing
                print("parseListDetailFuncAsync _getNextPageUrl error")
                print(traceback.format_exc())
                print(e)
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return nextPageUrlList

    def _getNextApiKey():
        if os.getenv('IS_CLOUD', ''):
            return _getListApiKeyGCP()
        return _getListApiKey()
    
    async def _callNextPageProc(_loop, url, limit=1):
        semaphore = asyncio.Semaphore(limit)
        responses = None
        tasks = []
        _total = 60
        _timeout = _getTimeout(_total)
        _connector=_getConnector(_loop)
        async with aiohttp.ClientSession(loop=_loop, connector=_connector, timeout=_timeout) as session:
            try:
                task = asyncio.ensure_future(_bound_fetch(semaphore=semaphore, session=session, timeout=_timeout, apiUrl=nextApiUrl, detailUrl=url))
                tasks.append(task)
                responses = await asyncio.gather(*tasks)
            except Exception as e:
                # do nothing
                print("parseListDetailFuncAsync _callNextPageProc error")
                print(traceback.format_exc())
                print(e)
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return responses
        
    request_json = json.loads(request.get_json())
    url = request_json['url']
    sumifu = GetSumifu("params")
    nextApiUrl = getUrl() + _getNextApiKey()
    pararellLimit = 2
    if os.getenv('IS_CLOUD', ''):
        pararellLimit = 10

    # 次ページURLの取得
    try:
        loopGetUrl = asyncio.new_event_loop()
        asyncio.set_event_loop(loopGetUrl)
        futuresGetUrl = asyncio.gather(*[_getNextPageUrl(loopGetUrl, url, pararellLimit)])
        nextPageUrlList = loopGetUrl.run_until_complete(futuresGetUrl)
    finally:
        loopGetUrl.close()

    # 次ページへの遷移
    if(not(len(nextPageUrlList) == 0 or nextPageUrlList[0] is None)):
        nextPageUrl = nextPageUrlList[0]
        try:
            loopCallNextPage = asyncio.new_event_loop()
            asyncio.set_event_loop(loopCallNextPage)
            futuresCall = asyncio.gather(*[_callNextPageProc(loopCallNextPage, nextPageUrl, pararellLimit)])
            nextPageUrlList = loopCallNextPage.run_until_complete(futuresCall)
        finally:
            loopCallNextPage.close()

    # 自ページ内の処理
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        futures = asyncio.gather(*[_run(loop, url, pararellLimit)])
        itemLists = loop.run_until_complete(futures)
    finally:
        loop.close()
        
    for itemList in itemLists:
        while itemList is not None and len(itemList) > 0:
            item = itemList.pop()  # memory release
            if item is not None:
                currentTime = datetime.datetime.now()
                currentDay = datetime.date.today()
                item.inputDateTime = currentTime
                item.inputDate = currentDay
                print(item.propertyName+":"+item.pageUrl)
                try:
                    item.save(False, False, None, None)
                except Exception as e:
                    print("save error")
                    print(e)
                    # raise e

    return jsonify({'message': url}), 200;


async def _proc_response(url, response):
    return url, response.status, await response.text()


def getUrl():
    if os.getenv('IS_CLOUD', ''):
        return "https://us-central1-sumifu.cloudfunctions.net"
    return "http://localhost:8000"


async def _fetch(session, timeout, apiUrl, detailUrl):
    json_data = json.dumps('{"url":"' + detailUrl + '"}').encode("utf-8")
    try:
        response = await session.post(apiUrl, headers=headersJson, data=json_data, timeout=timeout)
        return await _proc_response(detailUrl, response)
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        raise e


async def _bound_fetch(semaphore, session, timeout, apiUrl, detailUrl):
    # async with
    # __aenter__がasync with ブロックを呼んだ直後に呼ばれる
    # __aexit__がasync with ブロックを抜けた直後に呼ばれる
    async with semaphore:
        return await _fetch(session, timeout, apiUrl, detailUrl)

# #getsumifu.py
# -*- coding: utf-8 -*-
# import sys
# import importlib
# importlib.reload(sys)

# #SumifuappConfig.py
# from django.apps import AppConfig
# class SumifuappConfig(AppConfig):
#    name = '__main__'


if __name__ == "__main__":

    from flask import Flask, request
    # import yaml
    app = Flask(__name__)

    @app.route(API_KEY_START, methods=['OPTIONS', 'POST', 'GET'])
    def start():
        print("start")
        result = parseStartAsync(request)
        print("end")
        return result
    
    @app.route(API_KEY_START_KANTO, methods=['OPTIONS', 'POST', 'GET'])
    def startKanto():
        print("start startKanto")
        result = parseStartKantoAsync(request)
        print("end startKanto")
        return result

    @app.route(API_KEY_REGION, methods=['OPTIONS', 'POST', 'GET'])
    def region():
        print("start region")
        result = parseRegionFuncAsync(request)
        print("end region")
        return result

    @app.route(API_KEY_AREA, methods=['OPTIONS', 'POST', 'GET'])
    def area():
        print("start area")
        result = parseAreaFuncAsync(request)
        print("end area")
        return result

    @app.route(API_KEY_LIST, methods=['OPTIONS', 'POST', 'GET'])
    def propertyList():
        print("start propertyList")
        result = parseListFuncAsync(request)
        print("end propertyList")
        return result

    @app.route(API_KEY_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
    def propertyDetail():
        print("start propertyDetail")
        result = parseDetailFuncAsync(request)
        print("end propertyDetail")
        return result

    #loopが突然切れる、ERROR:asyncio:Task was destroyed but it is pending!が発生する
    @app.route(API_KEY_LIST_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
    def propertyListDetail():
        print("start propertyListDetail")
        result = parseListDetailFuncAsync(request)
        print("end propertyListDetail")
        return result

    if not os.getenv('IS_CLOUD', ''):
        app.run('127.0.0.1', 8000, debug=True)

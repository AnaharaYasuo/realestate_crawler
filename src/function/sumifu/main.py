import asyncio
import datetime
import aiohttp
import os
import django
from django.conf import settings
import traceback

API_KEY_START = '/api/sumifu/mansion/start'
API_KEY_REGION = '/api/sumifu/mansion/region'
API_KEY_AREA = '/api/sumifu/mansion/area'
API_KEY_LIST = '/api/sumifu/mansion/list'
API_KEY_DETAIL = '/api/sumifu/mansion/detail'
API_KEY_LIST_DETAIL = '/api/sumifu/mansion/listdetail'

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
                # 'package.apps.SumifuappConfig'
                'main.SumifuappConfig'
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
from package.getsumifu import GetSumifu
from flask import jsonify

# from package.getsumifu import GetSumifu
# import requests
import json

headersJson = {
    'Content-Type': 'application/json',
}
# loop = asyncio.get_event_loop()

currentTime = datetime.datetime.now()
currentDay = datetime.date.today()


def _getListApiKey():
    # key = API_KEY_LIST#listとdetailを別の関数内で処理で行う
    key = API_KEY_LIST_DETAIL  # listとdetailを同じ関数内で処理で行う
    return key


def parseStartAsyncPubSub(event, context):
    parseStartAsync("")


def parseStartAsync(request):

    urlList = ["https://www.stepon.co.jp/mansion/tokai/"
    , "https://www.stepon.co.jp/mansion/shutoken/"
    , "https://www.stepon.co.jp/mansion/kansai/"
    , "https://www.stepon.co.jp/mansion/hokkaido/"
    , "https://www.stepon.co.jp/mansion/tohoku/"
    , "https://www.stepon.co.jp/mansion/chugoku/"
    , "https://www.stepon.co.jp/mansion/kyushu/"]
    urlList = ["https://www.stepon.co.jp/mansion/shutoken/"]

    def _getApiKey():
        key = API_KEY_REGION
        if os.getenv('IS_CLOUD', ''):
            key = key.replace('/api', '')
        return key

    async def _run(limit=1):
        tasks = []
        semaphore = asyncio.Semaphore(limit)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            for detailUrl in urlList:
                task = asyncio.ensure_future(_bound_fetch(semaphore=semaphore, session=session, apiUrl=apiUrl, detailUrl=detailUrl))
                tasks.append(task)
            responses = await asyncio.gather(*tasks)
            return responses

    apiUrl = getUrl() + _getApiKey()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    pararellLimit = 2
    if os.getenv('IS_CLOUD', ''):
        pararellLimit = 10
    futures = asyncio.gather(*[_run(pararellLimit)])
    loop.run_until_complete(futures)
    loop.close()
    return "no respons in parseRegionStart", 200;


def parseRegionFuncAsync(request):

    def _getApiKey():
        key = API_KEY_AREA
        if os.getenv('IS_CLOUD', ''):
            key = key.replace('/api', '')
        return key

    async def _run(url, limit=1):
        tasks = []
        semaphore = asyncio.Semaphore(limit)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async for detailUrl in sumifu.parseRegionPage(session, url):
                task = asyncio.ensure_future(_bound_fetch(semaphore=semaphore, session=session, apiUrl=apiUrl, detailUrl=detailUrl))
                tasks.append(task)
            responses = await asyncio.gather(*tasks)
            return responses

    request_json = json.loads(request.get_json())
    url = request_json['url']
    sumifu = GetSumifu("params")
    apiUrl = getUrl() + _getApiKey()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    pararellLimit = 2
    if os.getenv('IS_CLOUD', ''):
        pararellLimit = 10
    futures = asyncio.gather(*[_run(url, pararellLimit)])
    loop.run_until_complete(futures)
    loop.close()
    return "no respons in parseRegionFunc", 200;


def parseAreaFuncAsync(request):

    def _getApiKey():
        key = _getListApiKey()
        if os.getenv('IS_CLOUD', ''):
            key = key.replace('/api', '')
        return key

    async def _run(url, limit=1):
        tasks = []
        semaphore = asyncio.Semaphore(limit)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async for detailUrl in sumifu.parseAreaPage(session, url):
                task = asyncio.ensure_future(_bound_fetch(semaphore=semaphore, session=session, apiUrl=apiUrl, detailUrl=detailUrl))
                tasks.append(task)
            responses = await asyncio.gather(*tasks)
            return responses

    request_json = json.loads(request.get_json())
    url = request_json['url']
    sumifu = GetSumifu("params")
    apiUrl = getUrl() + _getApiKey()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    pararellLimit = 2
    if os.getenv('IS_CLOUD', ''):
        pararellLimit = 50
    futures = asyncio.gather(*[_run(url, pararellLimit)])
    loop.run_until_complete(futures)
    loop.close()
    return "no respons in parseAreaFuncAsync", 200;


def parseListFuncAsync(request):

    def _getApiKey():
        key = API_KEY_DETAIL
        if os.getenv('IS_CLOUD', ''):
            key = key.replace('/api', '')
        return key

    async def _run(url, limit=1):
        tasks = []
        semaphore = asyncio.Semaphore(limit)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async for detailUrl in sumifu.parsePropertyListPage(session, url):
                task = asyncio.ensure_future(_bound_fetch(semaphore=semaphore, session=session, apiUrl=apiUrl, detailUrl=detailUrl))
                tasks.append(task)
            responses = await asyncio.gather(*tasks)
            return responses

    # url = "https://www.stepon.co.jp/mansion/area_23/list_23_101/100_1/"
    request_json = json.loads(request.get_json())
    url = request_json['url']
    sumifu = GetSumifu("params")
    apiUrl = getUrl() + _getApiKey()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    pararellLimit = 2
    if os.getenv('IS_CLOUD', ''):
        pararellLimit = 10
    futures = asyncio.gather(*[_run(url, pararellLimit)])
    loop.run_until_complete(futures)
    loop.close()
    return "no respons in parseListFuncAsync", 200;


def parseDetailFuncAsync(request):

    async def _run(url):
        tasks = []
        # semaphore = asyncio.Semaphore(limit)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            task = asyncio.ensure_future(sumifu.parsePropertyDetailPage(session=session, url=url))
            tasks.append(task)
            responses = await asyncio.gather(*tasks)
            return responses

    request_json = json.loads(request.get_json())
    url = request_json['url']
    sumifu = GetSumifu("params")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    futures = asyncio.gather(*[_run(url)])
    itemLists = loop.run_until_complete(futures)
    loop.close()
    for itemList in itemLists:
        for item in itemList:
            if item is not None:
                item.inputDateTime = currentTime
                item.inputDate = currentDay
    
                # item.save(False, False, None, None)
                print(item.propertyName)
                print(item.pageUrl)
    return jsonify({'message': url}), 200;


def parseListDetailFuncAsync(request):

    async def _run(url, limit=1):
        tasks = []
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async for detailUrl in sumifu.parsePropertyListPage(session, url):
                task = asyncio.ensure_future(sumifu.parsePropertyDetailPage(session=session, url=detailUrl))
                tasks.append(task)
            responses = await asyncio.gather(*tasks)
        return responses
            
    async def _getNextPageUrl(url, limit=1):
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            nextPageUrlList = await sumifu.getPropertyListNextPageUrl(session, url)
        return nextPageUrlList

    def _getNextApiKey():
        key = _getListApiKey()        
        if os.getenv('IS_CLOUD', ''):
            key = key.replace('/api', '')
        return key
    
    async def _callNextPageProc(url, limit=1):
        semaphore = asyncio.Semaphore(limit)
        tasks = []
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            task = asyncio.ensure_future(_bound_fetch(semaphore=semaphore, session=session, apiUrl=nextApiUrl, detailUrl=url))
            tasks.append(task)
            responses = await asyncio.gather(*tasks)
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
        futuresGetUrl = asyncio.gather(*[_getNextPageUrl(url, pararellLimit)])
        nextPageUrlList = loopGetUrl.run_until_complete(futuresGetUrl)
    finally:
        loopGetUrl.close()

    # 次ページへの遷移
    if(not(len(nextPageUrlList) == 0 or nextPageUrlList[0] is None)):
        nextPageUrl = nextPageUrlList[0]
        try:
            loopCallNextPage = asyncio.new_event_loop()
            asyncio.set_event_loop(loopCallNextPage)
            futuresCall = asyncio.gather(*[_callNextPageProc(nextPageUrl, pararellLimit)])
            nextPageUrlList = loopCallNextPage.run_until_complete(futuresCall)
        finally:
            loopCallNextPage.close()

    # 自ページ内の処理
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        futures = asyncio.gather(*[_run(url, pararellLimit)])
        itemLists = loop.run_until_complete(futures)
    finally:
        loop.close()
    for itemList in itemLists:
        for item in itemList:
            if item is not None:
                item.inputDateTime = currentTime
                item.inputDate = currentDay
                # item.save(False, False, None, None)
                print(item.propertyName)
                print(item.pageUrl)

    return jsonify({'message': url}), 200;


async def _proc_response(url, response):
    return url, response.status, await response.text()


def getUrl():
    if os.getenv('IS_CLOUD', ''):
        return "https://us-central1-sumifu.cloudfunctions.net"
    return "http://localhost:8000"


async def _fetch(session, apiUrl, detailUrl):
    json_data = json.dumps('{"url":"' + detailUrl + '"}').encode("utf-8")
    try:
        try:
            response = await session.post(apiUrl, headers=headersJson, data=json_data)
        except asyncio.TimeoutError as e:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as reSession:
                response = await reSession.post(apiUrl, headers=headersJson, data=json_data)            

        return await _proc_response(detailUrl, response)
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        raise e


async def _bound_fetch(semaphore, session, apiUrl, detailUrl):
    # async with
    # __aenter__がasync with ブロックを呼んだ直後に呼ばれる
    # __aexit__がasync with ブロックを抜けた直後に呼ばれる
    async with semaphore:
        return await _fetch(session, apiUrl, detailUrl)


# #getsumifu.py
# -*- coding: utf-8 -*-
import sys
import importlib
importlib.reload(sys)
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

    @app.route(API_KEY_LIST_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
    def propertyListDetail():
        print("start propertyListDetail")
        result = parseListDetailFuncAsync(request)
        print("end propertyListDetail")
        return result

    app.run('127.0.0.1', 8000, debug=True)

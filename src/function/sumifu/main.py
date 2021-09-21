import os
import logging
from package.api.api import API_KEY_SUMIFU_DETAIL, API_KEY_SUMIFU_REGION, API_KEY_SUMIFU_AREA, API_KEY_SUMIFU_START, API_KEY_SUMIFU_LIST, \
    API_KEY_MITSUI_START, API_KEY_MITSUI_AREA, API_KEY_MITSUI_LIST, \
    API_KEY_MITSUI_DETAIL, API_KEY_MITSUI_DETAIL_TEST, API_KEY_TOKYU_START, \
    API_KEY_TOKYU_AREA, API_KEY_TOKYU_LIST, API_KEY_TOKYU_DETAIL, \
    API_KEY_TOKYU_DETAIL_TEST, API_KEY_ALL_START, API_KEY_SUMIFU_DETAIL_TEST, \
    API_KEY_KILL
import json
import realestateSettings
import traceback
from asyncio import AbstractEventLoop
#from _datetime import datetime
realestateSettings.configure()  # package.apiがインポートされる前に実施する。
from package.api.mitsui import ParseMitsuiStartAsync, ParseMitsuiAreaFuncAsync, ParseMitsuiListFuncAsync, ParseMitsuiDetailFuncAsync
from package.api.sumifu import ParseSumifuStartAsync, ParseSumifuRegionFuncAsync, ParseSumifuAreaFuncAsync, ParseSumifuListFuncAsync, ParseSumifuDetailFuncAsync
from package.api.tokyu import ParseTokyuStartAsync, ParseTokyuAreaFuncAsync, \
    ParseTokyuListFuncAsync, ParseTokyuDetailFuncAsync

from flask import Flask, request
app = Flask(__name__)

# cloud functionsとComputeEngineはサーバーレスVPCで接続

# デバッグ方法
# PythonRunよりデバッグを開始するとflaskが起動。
# そのうえで、http://127.0.0.1:8000/api/sumifu/mansion/startにアクセス


def parseMitsuiStartAsyncPubSub(event, context):
    return mitsuiStart()


def parseSumifuStartAsyncPubSub(event, context):
    return sumifuStart()


@app.route(API_KEY_ALL_START, methods=['OPTIONS', 'POST', 'GET'])
def allStart():
    mitsuiStart()
    sumifuStart()
    tokyuStart()


###################################################
# mitsui
###################################################
@app.route(API_KEY_MITSUI_START, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiStart():
    logging.info("start")
    obj = ParseMitsuiStartAsync()
    url = "https://www.rehouse.co.jp/sitemap/"
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end")
    return result


@app.route(API_KEY_MITSUI_AREA, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiAreaLocal():
    return mitsuiArea(request)


def mitsuiArea(request):
    logging.info("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end area")
    return result


@app.route(API_KEY_MITSUI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiPropertyListLocal():
    return mitsuiPropertyList(request)


def mitsuiPropertyList(request):
    logging.info("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyList")
    return result


@app.route(API_KEY_MITSUI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiPropertyDetailLocal():
    return mitsuiPropertyDetail(request)


def mitsuiPropertyDetail(request):
    logging.info("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    # url="https://www.rehouse.co.jp/mansion/bkdetail/FQQXGA22/"
    # url="https://www.rehouse.co.jp/mansion/bkdetail/FEPX7A12/"#バスあり
    obj = ParseMitsuiDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyDetail")
    return result


@app.route(API_KEY_MITSUI_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiPropertyDetailTest():
    logging.info("start propertyDetail")
    # request_json = json.loads(request.get_json())
    # url = request_json['url']
    # url="https://www.rehouse.co.jp/mansion/bkdetail/FQQXGA22/"
    url = "https://www.rehouse.co.jp/mansion/bkdetail/FEPX7A12/"  # バスあり
    # url="https://www.rehouse.co.jp/mansion/bkdetail/F69X7A19/"
    # url="https://www.rehouse.co.jp/mansion/bkdetail/FGPX5A1C/"#バス停留所のみあり
    obj = ParseMitsuiDetailFuncAsync()
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result


###################################################
# sumifu
###################################################
@app.route(API_KEY_SUMIFU_START, methods=['OPTIONS', 'POST', 'GET'])
def sumifuStart():
    logging.info("start")
    obj = ParseSumifuStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end")

    return result


@app.route(API_KEY_SUMIFU_REGION, methods=['OPTIONS', 'POST', 'GET'])
def sumifuRegionLocal():
    return sumifuRegion(request)


def sumifuRegion(request):
    logging.info("start region")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuRegionFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end region")
    return result


@app.route(API_KEY_SUMIFU_AREA, methods=['OPTIONS', 'POST', 'GET'])
def sumifuAreaLocal():
    return sumifuArea(request)


def sumifuArea(request):
    logging.info("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end area")
    return result


@app.route(API_KEY_SUMIFU_LIST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuPropertyListLocal():
    return sumifuPropertyList(request)


def sumifuPropertyList(request):
    logging.info("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyList")
    return result


@app.route(API_KEY_SUMIFU_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def sumifuPropertyDetailLocal():
    return sumifuPropertyDetail(request)


def sumifuPropertyDetail(request):
    logging.info("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyDetail")
    return result


@app.route(API_KEY_SUMIFU_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuPropertyDetailTest():
    logging.info("start propertyDetail")
    url = "https://www.stepon.co.jp/mansion/detail_19273047/"
    obj = ParseSumifuDetailFuncAsync()
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result


###################################################
# tokyu
###################################################
@app.route(API_KEY_TOKYU_START, methods=['OPTIONS', 'POST', 'GET'])
def tokyuStart():
    logging.info("start")
    obj = ParseTokyuStartAsync()
    url = "https://www.livable.co.jp/kounyu/chuko-mansion/select-area/"
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end")
    return result


@app.route(API_KEY_TOKYU_AREA, methods=['OPTIONS', 'POST', 'GET'])
def tokyuAreaLocal():
    return tokyuArea(request)


def tokyuArea(request):
    logging.info("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end area")
    return result


@app.route(API_KEY_TOKYU_LIST, methods=['OPTIONS', 'POST', 'GET'])
def tokyuPropertyListLocal():
    return tokyuPropertyList(request)


def tokyuPropertyList(request):
    logging.info("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyList")
    return result


@app.route(API_KEY_TOKYU_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def tokyuPropertyDetailLocal():
    return tokyuPropertyDetail(request)


def tokyuPropertyDetail(request):
    logging.info("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyDetail")
    return result


@app.route(API_KEY_TOKYU_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def tokyuPropertyDetailTest():
    logging.info("start propertyDetail")
    # request_json = json.loads(request.get_json())
    # url = request_json['url']
    obj = ParseTokyuDetailFuncAsync()
    #url = "https://www.livable.co.jp/mansion/CVI207001/"  # メゾネット
    #obj.main(url)
    #url = "https://www.livable.co.jp/mansion/C11207001/"
    #obj.main(url)
    #url = "https://www.livable.co.jp/mansion/CZW206A54/"  # バスあり
    #obj.main(url)
    #url = "https://www.livable.co.jp/mansion/CXW202010/"  # 内法
    url = "https://www.livable.co.jp/mansion/CZY219M09/"
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result


@app.route(API_KEY_KILL, methods=['OPTIONS', 'POST', 'GET'])
def seriouslykill():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return "Shutting down..."


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,filename="flask.log")
    #logging.basicConfig(filename='flask' + datetime.now().strftime('%Y%m%d_%H%M%S') + ".log", level=logging.INFO)
    if not os.getenv('IS_CLOUD', ''):
        app.run(host='0.0.0.0', port=8000, debug=True)

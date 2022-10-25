import os
import logging
from tokenize import String
from package.api.api import \
    API_KEY_SUMIFU_MANSION_DETAIL, API_KEY_SUMIFU_MANSION_REGION, API_KEY_SUMIFU_MANSION_AREA, API_KEY_SUMIFU_MANSION_START, API_KEY_SUMIFU_MANSION_LIST, API_KEY_SUMIFU_MANSION_DETAIL_TEST, \
    API_KEY_SUMIFU_TOCHI_DETAIL, API_KEY_SUMIFU_TOCHI_REGION, API_KEY_SUMIFU_TOCHI_AREA, API_KEY_SUMIFU_TOCHI_START, API_KEY_SUMIFU_TOCHI_LIST,API_KEY_SUMIFU_TOCHI_DETAIL_TEST, \
    API_KEY_SUMIFU_KODATE_DETAIL, API_KEY_SUMIFU_KODATE_REGION, API_KEY_SUMIFU_KODATE_AREA, API_KEY_SUMIFU_KODATE_START, API_KEY_SUMIFU_KODATE_LIST,API_KEY_SUMIFU_KODATE_DETAIL_TEST, \
    API_KEY_MITSUI_MANSION_START, API_KEY_MITSUI_MANSION_AREA, API_KEY_MITSUI_MANSION_LIST, API_KEY_MITSUI_MANSION_DETAIL, API_KEY_MITSUI_MANSION_DETAIL_TEST, \
    API_KEY_MITSUI_TOCHI_START, API_KEY_MITSUI_TOCHI_AREA, API_KEY_MITSUI_TOCHI_LIST, API_KEY_MITSUI_TOCHI_DETAIL, API_KEY_MITSUI_TOCHI_DETAIL_TEST, \
    API_KEY_MITSUI_KODATE_START, API_KEY_MITSUI_KODATE_AREA, API_KEY_MITSUI_KODATE_LIST, API_KEY_MITSUI_KODATE_DETAIL, API_KEY_MITSUI_KODATE_DETAIL_TEST, \
    API_KEY_TOKYU_MANSION_START, API_KEY_TOKYU_MANSION_AREA, API_KEY_TOKYU_MANSION_LIST, API_KEY_TOKYU_MANSION_DETAIL, API_KEY_TOKYU_MANSION_DETAIL_TEST, \
    API_KEY_MANSION_ALL_START, API_KEY_KILL
    
import json
import realestateSettings
import traceback
from asyncio import AbstractEventLoop
#from _datetime import datetime
realestateSettings.configure()  # package.apiがインポートされる前に実施する。
from package.api.mitsui import ParseMitsuiMansionStartAsync, ParseMitsuiMansionAreaFuncAsync, ParseMitsuiMansionListFuncAsync, ParseMitsuiMansionDetailFuncAsync
from package.api.mitsui import ParseMitsuiTochiStartAsync, ParseMitsuiTochiAreaFuncAsync, ParseMitsuiTochiListFuncAsync, ParseMitsuiTochiDetailFuncAsync
from package.api.mitsui import ParseMitsuiKodateStartAsync, ParseMitsuiKodateAreaFuncAsync, ParseMitsuiKodateListFuncAsync, ParseMitsuiKodateDetailFuncAsync
from package.api.sumifu import ParseSumifuMansionStartAsync, ParseSumifuMansionRegionFuncAsync, ParseSumifuMansionAreaFuncAsync, ParseSumifuMansionListFuncAsync, ParseSumifuMansionDetailFuncAsync
from package.api.sumifu import ParseSumifuTochiStartAsync, ParseSumifuTochiRegionFuncAsync, ParseSumifuTochiAreaFuncAsync, ParseSumifuTochiListFuncAsync, ParseSumifuTochiDetailFuncAsync
from package.api.sumifu import ParseSumifuKodateStartAsync, ParseSumifuKodateRegionFuncAsync, ParseSumifuKodateAreaFuncAsync, ParseSumifuKodateListFuncAsync, ParseSumifuKodateDetailFuncAsync
from package.api.tokyu import ParseTokyuMansionStartAsync, ParseTokyuMansionAreaFuncAsync, ParseTokyuMansionListFuncAsync, ParseTokyuMansionDetailFuncAsync

from flask import Flask, request
app = Flask(__name__)

# cloud functionsとComputeEngineはサーバーレスVPCで接続

# デバッグ方法
# PythonRunよりデバッグを開始するとflaskが起動。
# そのうえで、http://127.0.0.1:8000/api/sumifu/mansion/startにアクセス


def parseMitsuiStartMansionAsyncPubSub(event, context):
    return mitsuiMansionStart()


def parseSumifuStartMansionAsyncPubSub(event, context):
    return sumifuMansionStart()


@app.route(API_KEY_MANSION_ALL_START, methods=['OPTIONS', 'POST', 'GET'])
def allMansionStart():
    mitsuiMansionStart()
    sumifuMansionStart()
    tokyuMansionStart()

###################################################
# mitsui mansion
###################################################
@app.route(API_KEY_MITSUI_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiMansionStart():
    logging.info("start")
    obj = ParseMitsuiMansionStartAsync()
    url = "https://www.rehouse.co.jp/sitemap/"
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end")
    return result


@app.route(API_KEY_MITSUI_MANSION_AREA, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiMansionAreaLocal():
    return mitsuiMansionArea(request)


def mitsuiMansionArea(request):
    logging.info("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiMansionAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end area")
    return result


@app.route(API_KEY_MITSUI_MANSION_LIST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiMansionPropertyListLocal():
    return mitsuiMansionPropertyList(request)


def mitsuiMansionPropertyList(request):
    logging.info("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiMansionListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyList")
    return result


@app.route(API_KEY_MITSUI_MANSION_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiMansionPropertyDetailLocal():
    return mitsuiMansionPropertyDetail(request)


def mitsuiMansionPropertyDetail(request):
    logging.info("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiMansionDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyDetail")
    return result


@app.route(API_KEY_MITSUI_MANSION_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiMansionPropertyDetailTest():
    logging.info("start propertyDetail")
    # request_json = json.loads(request.get_json())
    # url = request_json['url']
    url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/FSFZ4A03/"
    obj = ParseMitsuiMansionDetailFuncAsync()
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result

###################################################
# mitsui tochi
###################################################
@app.route(API_KEY_MITSUI_TOCHI_START, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiTochiStart():
    logging.info("start")
    obj = ParseMitsuiTochiStartAsync()
    url = "https://www.rehouse.co.jp/sitemap/"
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end")
    return result


@app.route(API_KEY_MITSUI_TOCHI_AREA, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiTochiAreaLocal():
    return mitsuiTochiArea(request)


def mitsuiTochiArea(request):
    logging.info("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiTochiAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end area")
    return result


@app.route(API_KEY_MITSUI_TOCHI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiTochiPropertyListLocal():
    return mitsuiTochiPropertyList(request)


def mitsuiTochiPropertyList(request):
    logging.info("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiTochiListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyList")
    return result


@app.route(API_KEY_MITSUI_TOCHI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiTochiPropertyDetailLocal():
    return mitsuiTochiPropertyDetail(request)


def mitsuiTochiPropertyDetail(request):
    logging.info("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiTochiDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyDetail")
    return result


@app.route(API_KEY_MITSUI_TOCHI_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiTochiPropertyDetailTest():
    logging.info("start propertyDetail")
    # request_json = json.loads(request.get_json())
    # url = request_json['url']
    url = "https://www.rehouse.co.jp/buy/tochi/bkdetail/FBHZGA14/"
    obj = ParseMitsuiTochiDetailFuncAsync()
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result

###################################################
# mitsui kodate
###################################################
@app.route(API_KEY_MITSUI_KODATE_START, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiKodateStart():
    logging.info("start")
    obj:ParseMitsuiKodateStartAsync = ParseMitsuiKodateStartAsync()
    url = "https://www.rehouse.co.jp/sitemap/"
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end")
    return result


@app.route(API_KEY_MITSUI_KODATE_AREA, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiKodateAreaLocal():
    return mitsuiKodateArea(request)


def mitsuiKodateArea(request):
    logging.info("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiKodateAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end area")
    return result


@app.route(API_KEY_MITSUI_KODATE_LIST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiKodatePropertyListLocal():
    return mitsuiKodatePropertyList(request)


def mitsuiKodatePropertyList(request):
    logging.info("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj:ParseMitsuiKodateListFuncAsync = ParseMitsuiKodateListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyList")
    return result


@app.route(API_KEY_MITSUI_KODATE_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiKodatePropertyDetailLocal():
    return mitsuiKodatePropertyDetail(request)


def mitsuiKodatePropertyDetail(request):
    logging.info("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiKodateDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyDetail")
    return result


@app.route(API_KEY_MITSUI_KODATE_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiKodatePropertyDetailTest():
    logging.info("start propertyDetail")
    # request_json = json.loads(request.get_json())
    # url = request_json['url']
    url = "https://www.rehouse.co.jp/kodate/bkdetail/FLGZ4A09/"
    obj = ParseMitsuiKodateDetailFuncAsync()
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result

###################################################
# sumifu Mansion
###################################################
@app.route(API_KEY_SUMIFU_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def sumifuMansionStart():
    logging.info("start")
    obj = ParseSumifuMansionStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end")

    return result


@app.route(API_KEY_SUMIFU_MANSION_REGION, methods=['OPTIONS', 'POST', 'GET'])
def sumifuMansionRegionLocal():
    return sumifuMansionRegion(request)


def sumifuMansionRegion(request):
    logging.info("start region")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuMansionRegionFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end region")
    return result


@app.route(API_KEY_SUMIFU_MANSION_AREA, methods=['OPTIONS', 'POST', 'GET'])
def sumifuMansionAreaLocal():
    return sumifuMansionArea(request)


def sumifuMansionArea(request):
    logging.info("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuMansionAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end area")
    return result


@app.route(API_KEY_SUMIFU_MANSION_LIST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuMansionPropertyListLocal():
    return sumifuMansionPropertyList(request)


def sumifuMansionPropertyList(request):
    logging.info("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuMansionListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyList")
    return result


@app.route(API_KEY_SUMIFU_MANSION_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def sumifuMansionPropertyDetailLocal():
    return sumifuMansionPropertyDetail(request)


def sumifuMansionPropertyDetail(request):
    logging.info("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuMansionDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyDetail")
    return result


@app.route(API_KEY_SUMIFU_MANSION_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuMansionPropertyDetailTest():
    logging.info("start propertyDetail")
    url = "https://www.stepon.co.jp/mansion/detail_12583039/"
    obj = ParseSumifuMansionDetailFuncAsync()
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result

###################################################
# sumifu tochi
###################################################
@app.route(API_KEY_SUMIFU_TOCHI_START, methods=['OPTIONS', 'POST', 'GET'])
def sumifuTochiStart():
    logging.info("start")
    obj = ParseSumifuTochiStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end")

    return result


@app.route(API_KEY_SUMIFU_TOCHI_REGION, methods=['OPTIONS', 'POST', 'GET'])
def sumifuTochiRegionLocal():
    return sumifuTochiRegion(request)


def sumifuTochiRegion(request):
    logging.info("start region")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuTochiRegionFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end region")
    return result


@app.route(API_KEY_SUMIFU_TOCHI_AREA, methods=['OPTIONS', 'POST', 'GET'])
def sumifuTochiAreaLocal():
    return sumifuTochiArea(request)


def sumifuTochiArea(request):
    logging.info("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuTochiAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end area")
    return result


@app.route(API_KEY_SUMIFU_TOCHI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuTochiPropertyListLocal():
    return sumifuTochiPropertyList(request)


def sumifuTochiPropertyList(request):
    logging.info("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuTochiListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyList")
    return result


@app.route(API_KEY_SUMIFU_TOCHI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def sumifuTochiPropertyDetailLocal():
    return sumifuTochiPropertyDetail(request)


def sumifuTochiPropertyDetail(request):
    logging.info("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuTochiDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyDetail")
    return result


@app.route(API_KEY_SUMIFU_TOCHI_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuTochiPropertyDetailTest():
    logging.info("start propertyDetail")
    url = "https://www.stepon.co.jp/tochi/detail_12011023/"
    obj = ParseSumifuTochiDetailFuncAsync()
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result

###################################################
# sumifu kodate
###################################################
@app.route(API_KEY_SUMIFU_KODATE_START, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodateStart():
    logging.info("start")
    obj = ParseSumifuKodateStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end")

    return result


@app.route(API_KEY_SUMIFU_KODATE_REGION, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodateRegionLocal():
    return sumifuKodateRegion(request)


def sumifuKodateRegion(request):
    logging.info("start region")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuKodateRegionFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end region")
    return result


@app.route(API_KEY_SUMIFU_KODATE_AREA, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodateAreaLocal():
    return sumifuKodateArea(request)


def sumifuKodateArea(request):
    logging.info("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuKodateAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end area")
    return result


@app.route(API_KEY_SUMIFU_KODATE_LIST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodatePropertyListLocal():
    return sumifuKodatePropertyList(request)


def sumifuKodatePropertyList(request):
    logging.info("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuKodateListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyList")
    return result


@app.route(API_KEY_SUMIFU_KODATE_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodatePropertyDetailLocal():
    return sumifuKodatePropertyDetail(request)


def sumifuKodatePropertyDetail(request):
    logging.info("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuKodateDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyDetail")
    return result


@app.route(API_KEY_SUMIFU_KODATE_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodatePropertyDetailTest():
    logging.info("start propertyDetail")
    url:String = "https://www.stepon.co.jp/kodate/detail_12012003/"
    obj:ParseSumifuKodateDetailFuncAsync = ParseSumifuKodateDetailFuncAsync()
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result


###################################################
# tokyu mansion
###################################################
@app.route(API_KEY_TOKYU_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def tokyuMansionStart():
    logging.info("start")
    obj = ParseTokyuMansionStartAsync()
    url = "https://www.livable.co.jp/kounyu/chuko-mansion/select-area/"
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end")
    return result


@app.route(API_KEY_TOKYU_MANSION_AREA, methods=['OPTIONS', 'POST', 'GET'])
def tokyuMansionAreaLocal():
    return tokyuMansionArea(request)


def tokyuMansionArea(request):
    logging.info("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuMansionAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end area")
    return result


@app.route(API_KEY_TOKYU_MANSION_LIST, methods=['OPTIONS', 'POST', 'GET'])
def tokyuMansionPropertyListLocal():
    return tokyuMansionPropertyList(request)


def tokyuMansionPropertyList(request):
    logging.info("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuMansionListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyList")
    return result


@app.route(API_KEY_TOKYU_MANSION_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def tokyuMansionPropertyDetailLocal():
    return tokyuMansionPropertyDetail(request)


def tokyuMansionPropertyDetail(request):
    logging.info("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuMansionDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("end propertyDetail")
    return result


@app.route(API_KEY_TOKYU_MANSION_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def tokyuMansionPropertyDetailTest():
    logging.info("start propertyDetail")
    # request_json = json.loads(request.get_json())
    # url = request_json['url']
    obj = ParseTokyuMansionDetailFuncAsync()
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

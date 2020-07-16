import os
from package.api.api import API_KEY_SUMIFU_DETAIL, API_KEY_SUMIFU_REGION, API_KEY_SUMIFU_AREA, API_KEY_SUMIFU_START, API_KEY_SUMIFU_LIST, \
    API_KEY_MITSUI_START, API_KEY_MITSUI_AREA, API_KEY_MITSUI_LIST, \
    API_KEY_MITSUI_DETAIL, API_KEY_MITSUI_DETAIL_TEST
import json
import realestateSettings
realestateSettings.configure()  # package.apiがインポートされる前に実施する。
from package.api.mitsui import ParseMitsuiStartAsync, ParseMitsuiAreaFuncAsync, ParseMitsuiListFuncAsync, ParseMitsuiDetailFuncAsync
from package.api.sumifu import ParseSumifuStartAsync, ParseSumifuRegionFuncAsync, ParseSumifuAreaFuncAsync, ParseSumifuListFuncAsync, ParseSumifuDetailFuncAsync

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


###################################################
# mitsui
###################################################
@app.route(API_KEY_MITSUI_START, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiStart():
    print("start")
    obj = ParseMitsuiStartAsync()
    url = "https://www.rehouse.co.jp/sitemap/"
    result = obj.main(url)
    print("end")
    return result


@app.route(API_KEY_MITSUI_AREA, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiArea():
    print("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiAreaFuncAsync()
    result = obj.main(url)
    print("end area")
    return result


@app.route(API_KEY_MITSUI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiPropertyList():
    print("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiListFuncAsync()
    result = obj.main(url)
    print("end propertyList")
    return result


@app.route(API_KEY_MITSUI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiPropertyDetail():
    print("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    # url="https://www.rehouse.co.jp/mansion/bkdetail/FQQXGA22/"
    # url="https://www.rehouse.co.jp/mansion/bkdetail/FEPX7A12/"#バスあり
    obj = ParseMitsuiDetailFuncAsync()
    result = obj.main(url)
    print("end propertyDetail")
    return result


@app.route(API_KEY_MITSUI_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiPropertyDetailTest():
    print("start propertyDetail")
    # request_json = json.loads(request.get_json())
    # url = request_json['url']
    # url="https://www.rehouse.co.jp/mansion/bkdetail/FQQXGA22/"
    url = "https://www.rehouse.co.jp/mansion/bkdetail/FEPX7A12/"  # バスあり
    # url="https://www.rehouse.co.jp/mansion/bkdetail/F69X7A19/"
    # url="https://www.rehouse.co.jp/mansion/bkdetail/FGPX5A1C/"#バス停留所のみあり
    obj = ParseMitsuiDetailFuncAsync()
    result = obj.main(url)
    print("end propertyDetail")
    return result


###################################################
# sumifu
###################################################
@app.route(API_KEY_SUMIFU_START, methods=['OPTIONS', 'POST', 'GET'])
def sumifuStart():
    print("start")
    obj = ParseSumifuStartAsync()
    url = "dammy"
    result = obj.main(url)
    print("end")
    
    return result


@app.route(API_KEY_SUMIFU_REGION, methods=['OPTIONS', 'POST', 'GET'])
def sumifuRegion():
    print("start region")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuRegionFuncAsync()
    result = obj.main(url)
    print("end region")
    return result


@app.route(API_KEY_SUMIFU_AREA, methods=['OPTIONS', 'POST', 'GET'])
def sumifuArea():
    print("start area")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuAreaFuncAsync()
    result = obj.main(url)
    print("end area")
    return result


@app.route(API_KEY_SUMIFU_LIST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuPropertyList():
    print("start propertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuListFuncAsync()
    result = obj.main(url)
    print("end propertyList")
    return result


@app.route(API_KEY_SUMIFU_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def sumifuPropertyDetail():
    print("start propertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseSumifuDetailFuncAsync()
    result = obj.main(url)
    print("end propertyDetail")
    return result

###################################################
# tokyu
###################################################


if __name__ == "__main__":
    if not os.getenv('IS_CLOUD', ''):
        app.run('127.0.0.1', 8000, debug=True)

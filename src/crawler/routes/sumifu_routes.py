import logging
import traceback
import json
from flask import Blueprint, request
from package.api.api import (
    API_KEY_SUMIFU_MANSION_DETAIL, API_KEY_SUMIFU_MANSION_REGION, API_KEY_SUMIFU_MANSION_AREA, API_KEY_SUMIFU_MANSION_START, API_KEY_SUMIFU_MANSION_LIST, API_KEY_SUMIFU_MANSION_DETAIL_TEST,
    API_KEY_SUMIFU_TOCHI_DETAIL, API_KEY_SUMIFU_TOCHI_REGION, API_KEY_SUMIFU_TOCHI_AREA, API_KEY_SUMIFU_TOCHI_START, API_KEY_SUMIFU_TOCHI_LIST,API_KEY_SUMIFU_TOCHI_DETAIL_TEST,
    API_KEY_SUMIFU_KODATE_DETAIL, API_KEY_SUMIFU_KODATE_REGION, API_KEY_SUMIFU_KODATE_AREA, API_KEY_SUMIFU_KODATE_START, API_KEY_SUMIFU_KODATE_LIST,API_KEY_SUMIFU_KODATE_DETAIL_TEST
)
from package.api.sumifu import (
    ParseSumifuMansionStartAsync, ParseSumifuMansionRegionFuncAsync, ParseSumifuMansionAreaFuncAsync, ParseSumifuMansionListFuncAsync, ParseSumifuMansionDetailFuncAsync,
    ParseSumifuTochiStartAsync, ParseSumifuTochiRegionFuncAsync, ParseSumifuTochiAreaFuncAsync, ParseSumifuTochiListFuncAsync, ParseSumifuTochiDetailFuncAsync,
    ParseSumifuKodateStartAsync, ParseSumifuKodateRegionFuncAsync, ParseSumifuKodateAreaFuncAsync, ParseSumifuKodateListFuncAsync, ParseSumifuKodateDetailFuncAsync
)

sumifu_bp = Blueprint('sumifu', __name__)

# Cloud Functions entry point (optional, depends on how it's used)
def parseSumifuStartMansionAsyncPubSub(event, context):
    return sumifuMansionStart()

###################################################
# sumifu Mansion
###################################################
@sumifu_bp.route(API_KEY_SUMIFU_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def sumifuMansionStart():
    logging.info("Start sumifuMansionStart")
    obj = ParseSumifuMansionStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except Exception:
        logging.error("Failed sumifuMansionStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuMansionStart")

    return result


@sumifu_bp.route(API_KEY_SUMIFU_MANSION_REGION, methods=['OPTIONS', 'POST', 'GET'])
def sumifuMansionRegionLocal():
    sumifuMansionRegion(request)
    return "finish", 200


def sumifuMansionRegion(request):
    logging.info("Start sumifuMansionRegion")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuMansionRegionFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuMansionRegion")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuMansionRegion")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_MANSION_AREA, methods=['OPTIONS', 'POST', 'GET'])
def sumifuMansionAreaLocal():
    sumifuMansionArea(request)
    return "finish", 200


def sumifuMansionArea(request):
    logging.info("Start sumifuMansionArea")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuMansionAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuMansionArea")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuMansionArea")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_MANSION_LIST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuMansionPropertyListLocal():
    sumifuMansionPropertyList(request)
    return "finish", 200


def sumifuMansionPropertyList(request):
    logging.info("Start sumifuMansionPropertyList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuMansionListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuMansionPropertyList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuMansionPropertyList")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_MANSION_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def sumifuMansionPropertyDetailLocal():
    sumifuMansionPropertyDetail(request)
    return "finish", 200


def sumifuMansionPropertyDetail(request):
    logging.info("Start sumifuMansionPropertyDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuMansionDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuMansionPropertyDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuMansionPropertyDetail")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_MANSION_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
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
@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_START, methods=['OPTIONS', 'POST', 'GET'])
def sumifuTochiStart():
    logging.info("Start sumifuTochiStart")
    obj = ParseSumifuTochiStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except Exception:
        logging.error("Failed sumifuTochiStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuTochiStart")

    return result


@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_REGION, methods=['OPTIONS', 'POST', 'GET'])
def sumifuTochiRegionLocal():
    sumifuTochiRegion(request)
    return "finish", 200


def sumifuTochiRegion(request):
    logging.info("Start sumifuTochiRegion")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuTochiRegionFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuTochiRegion")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuTochiRegion")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_AREA, methods=['OPTIONS', 'POST', 'GET'])
def sumifuTochiAreaLocal():
    sumifuTochiArea(request)
    return "finish", 200


def sumifuTochiArea(request):
    logging.info("Start sumifuTochiArea")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuTochiAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuTochiArea")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuTochiArea")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuTochiPropertyListLocal():
    sumifuTochiPropertyList(request)
    return "finish", 200


def sumifuTochiPropertyList(request):
    logging.info("Start sumifuTochiPropertyList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuTochiListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuTochiPropertyList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuTochiPropertyList")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def sumifuTochiPropertyDetailLocal():
    sumifuTochiPropertyDetail(request)
    return "finish", 200


def sumifuTochiPropertyDetail(request):
    logging.info("Start sumifuTochiPropertyDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuTochiDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuTochiPropertyDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuTochiPropertyDetail")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
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
@sumifu_bp.route(API_KEY_SUMIFU_KODATE_START, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodateStart():
    logging.info("Start sumifuKodateStart")
    obj = ParseSumifuKodateStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except Exception:
        logging.error("Failed sumifuKodateStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuKodateStart")

    return result


@sumifu_bp.route(API_KEY_SUMIFU_KODATE_REGION, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodateRegionLocal():
    sumifuKodateRegion(request)
    return "finish", 200


def sumifuKodateRegion(request):
    logging.info("Start sumifuKodateRegion")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuKodateRegionFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuKodateRegion")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuKodateRegion")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_KODATE_AREA, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodateAreaLocal():
    sumifuKodateArea(request)
    return "finish", 200


def sumifuKodateArea(request):
    logging.info("Start sumifuKodateArea")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuKodateAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuKodateArea")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuKodateArea")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_KODATE_LIST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodatePropertyListLocal():
    sumifuKodatePropertyList(request)
    return "finish", 200


def sumifuKodatePropertyList(request):
    logging.info("Start sumifuKodatePropertyList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuKodateListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuKodatePropertyList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuKodatePropertyList")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_KODATE_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodatePropertyDetailLocal():
    sumifuKodatePropertyDetail(request)
    return "finish", 200


def sumifuKodatePropertyDetail(request):
    logging.info("Start sumifuKodatePropertyDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuKodateDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.error("Failed sumifuKodatePropertyDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success sumifuKodatePropertyDetail")
    return "finish", 200


@sumifu_bp.route(API_KEY_SUMIFU_KODATE_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def sumifuKodatePropertyDetailTest():
    logging.info("start propertyDetail")
    url = "https://www.stepon.co.jp/kodate/detail_12012003/"
    obj = ParseSumifuKodateDetailFuncAsync()
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result

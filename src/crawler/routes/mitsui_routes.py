import logging
import traceback
import json
from flask import Blueprint, request
from package.api.api import (
    API_KEY_MITSUI_MANSION_START, API_KEY_MITSUI_MANSION_AREA, API_KEY_MITSUI_MANSION_LIST, API_KEY_MITSUI_MANSION_DETAIL, API_KEY_MITSUI_MANSION_DETAIL_TEST,
    API_KEY_MITSUI_TOCHI_START, API_KEY_MITSUI_TOCHI_AREA, API_KEY_MITSUI_TOCHI_LIST, API_KEY_MITSUI_TOCHI_DETAIL, API_KEY_MITSUI_TOCHI_DETAIL_TEST,
    API_KEY_MITSUI_KODATE_START, API_KEY_MITSUI_KODATE_AREA, API_KEY_MITSUI_KODATE_LIST, API_KEY_MITSUI_KODATE_DETAIL, API_KEY_MITSUI_KODATE_DETAIL_TEST
)
from package.api.mitsui import (
    ParseMitsuiMansionStartAsync, ParseMitsuiMansionAreaFuncAsync, ParseMitsuiMansionListFuncAsync, ParseMitsuiMansionDetailFuncAsync,
    ParseMitsuiTochiStartAsync, ParseMitsuiTochiAreaFuncAsync, ParseMitsuiTochiListFuncAsync, ParseMitsuiTochiDetailFuncAsync,
    ParseMitsuiKodateStartAsync, ParseMitsuiKodateAreaFuncAsync, ParseMitsuiKodateListFuncAsync, ParseMitsuiKodateDetailFuncAsync
)

mitsui_bp = Blueprint('mitsui', __name__)

# Cloud Functions entry point (optional, depends on how it's used)
def parseMitsuiStartMansionAsyncPubSub(event, context):
    return mitsuiMansionStart()

###################################################
# mitsui mansion
###################################################
@mitsui_bp.route(API_KEY_MITSUI_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiMansionStart():
    logging.info("Start mitsuiMansionStart")
    obj = ParseMitsuiMansionStartAsync()
    url = "https://www.rehouse.co.jp/sitemap/"
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiMansionStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiMansionStart")
    return result


@mitsui_bp.route(API_KEY_MITSUI_MANSION_AREA, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiMansionAreaLocal():
    return mitsuiMansionArea(request)


def mitsuiMansionArea(request):
    logging.info("Start mitsuiMansionArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiMansionAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiMansionArea")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiMansionArea")
    return result


@mitsui_bp.route(API_KEY_MITSUI_MANSION_LIST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiMansionPropertyListLocal():
    return mitsuiMansionPropertyList(request)


def mitsuiMansionPropertyList(request):
    logging.info("Start mitsuiMansionPropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiMansionListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiMansionPropertyList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiMansionPropertyList")
    return result


@mitsui_bp.route(API_KEY_MITSUI_MANSION_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiMansionPropertyDetailLocal():
    return mitsuiMansionPropertyDetail(request)


def mitsuiMansionPropertyDetail(request):
    logging.info("Start mitsuiMansionPropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiMansionDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiMansionPropertyDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiMansionPropertyDetail")
    return result


@mitsui_bp.route(API_KEY_MITSUI_MANSION_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
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
@mitsui_bp.route(API_KEY_MITSUI_TOCHI_START, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiTochiStart():
    logging.info("Start mitsuiTochiStart")
    obj = ParseMitsuiTochiStartAsync()
    url = "https://www.rehouse.co.jp/sitemap/"
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiTochiStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiTochiStart")
    return result


@mitsui_bp.route(API_KEY_MITSUI_TOCHI_AREA, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiTochiAreaLocal():
    return mitsuiTochiArea(request)


def mitsuiTochiArea(request):
    logging.info("Start mitsuiTochiArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiTochiAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiTochiArea")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiTochiArea")
    return result


@mitsui_bp.route(API_KEY_MITSUI_TOCHI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiTochiPropertyListLocal():
    return mitsuiTochiPropertyList(request)


def mitsuiTochiPropertyList(request):
    logging.info("Start mitsuiTochiPropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiTochiListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiTochiPropertyList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiTochiPropertyList")
    return result


@mitsui_bp.route(API_KEY_MITSUI_TOCHI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiTochiPropertyDetailLocal():
    return mitsuiTochiPropertyDetail(request)


def mitsuiTochiPropertyDetail(request):
    logging.info("Start mitsuiTochiPropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiTochiDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiTochiPropertyDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiTochiPropertyDetail")
    return result


@mitsui_bp.route(API_KEY_MITSUI_TOCHI_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
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
@mitsui_bp.route(API_KEY_MITSUI_KODATE_START, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiKodateStart():
    logging.info("Start mitsuiKodateStart")
    obj = ParseMitsuiKodateStartAsync()
    url = "https://www.rehouse.co.jp/sitemap/"
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiKodateStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiKodateStart")
    return result


@mitsui_bp.route(API_KEY_MITSUI_KODATE_AREA, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiKodateAreaLocal():
    return mitsuiKodateArea(request)


def mitsuiKodateArea(request):
    logging.info("Start mitsuiKodateArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiKodateAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiKodateArea")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiKodateArea")
    return result


@mitsui_bp.route(API_KEY_MITSUI_KODATE_LIST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiKodatePropertyListLocal():
    return mitsuiKodatePropertyList(request)


def mitsuiKodatePropertyList(request):
    logging.info("Start mitsuiKodatePropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiKodateListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiKodatePropertyList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiKodatePropertyList")
    return result


@mitsui_bp.route(API_KEY_MITSUI_KODATE_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiKodatePropertyDetailLocal():
    return mitsuiKodatePropertyDetail(request)


def mitsuiKodatePropertyDetail(request):
    logging.info("Start mitsuiKodatePropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiKodateDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed mitsuiKodatePropertyDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success mitsuiKodatePropertyDetail")
    return result


@mitsui_bp.route(API_KEY_MITSUI_KODATE_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def mitsuiKodatePropertyDetailTest():
    logging.info("start propertyDetail")
    # request_json = json.loads(request.get_json())
    # url = request_json['url']
    url = "https://www.rehouse.co.jp/kodate/bkdetail/FLGZ4A09/"
    obj = ParseMitsuiKodateDetailFuncAsync()
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result

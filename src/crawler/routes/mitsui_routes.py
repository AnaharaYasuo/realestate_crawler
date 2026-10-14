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

ERROR_END = "error end"
START_PROPERTY_DETAIL = "start propertyDetail"
END_PROPERTY_DETAIL = "end propertyDetail"

# Cloud Functions entry point (optional, depends on how it's used)
def parse_mitsui_start_mansion_async_pub_sub(event, context):
    return mitsuiMansionStart()

parseMitsuiStartMansionAsyncPubSub = parse_mitsui_start_mansion_async_pub_sub

###################################################
# mitsui mansion
###################################################
@mitsui_bp.route(API_KEY_MITSUI_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_mansion_start():
    logging.info("Start mitsuiMansionStart")
    obj = ParseMitsuiMansionStartAsync()
    url = "https://www.rehouse.co.jp/buy/mansion/"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiMansionStart")
        return ERROR_END, 500
    logging.info("Success mitsuiMansionStart")
    return result

mitsuiMansionStart = mitsui_mansion_start


@mitsui_bp.route(API_KEY_MITSUI_MANSION_AREA, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_mansion_area_local():
    mitsuiMansionArea(request)
    return "finish", 200

mitsuiMansionAreaLocal = mitsui_mansion_area_local


def mitsui_mansion_area(request):
    logging.info("Start mitsuiMansionArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiMansionAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiMansionArea")
        return ERROR_END, 500
    logging.info("Success mitsuiMansionArea")
    return "finish", 200

mitsuiMansionArea = mitsui_mansion_area


@mitsui_bp.route(API_KEY_MITSUI_MANSION_LIST, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_mansion_property_list_local():
    mitsuiMansionPropertyList(request)
    return "finish", 200

mitsuiMansionPropertyListLocal = mitsui_mansion_property_list_local


def mitsui_mansion_property_list(request):
    logging.info("Start mitsuiMansionPropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiMansionListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiMansionPropertyList")
        return ERROR_END, 500
    logging.info("Success mitsuiMansionPropertyList")
    return "finish", 200

mitsuiMansionPropertyList = mitsui_mansion_property_list


@mitsui_bp.route(API_KEY_MITSUI_MANSION_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_mansion_property_detail_local():
    mitsuiMansionPropertyDetail(request)
    return "finish", 200

mitsuiMansionPropertyDetailLocal = mitsui_mansion_property_detail_local


def mitsui_mansion_property_detail(request):
    logging.info("Start mitsuiMansionPropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiMansionDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiMansionPropertyDetail")
        return ERROR_END, 500
    logging.info("Success mitsuiMansionPropertyDetail")
    return "finish", 200

mitsuiMansionPropertyDetail = mitsui_mansion_property_detail


@mitsui_bp.route(API_KEY_MITSUI_MANSION_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_mansion_property_detail_test():
    logging.info(START_PROPERTY_DETAIL)
    url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKPBAA05/"
    obj = ParseMitsuiMansionDetailFuncAsync()
    result = obj.main(url)
    logging.info(END_PROPERTY_DETAIL)
    return result

mitsuiMansionPropertyDetailTest = mitsui_mansion_property_detail_test

###################################################
# mitsui tochi
###################################################
@mitsui_bp.route(API_KEY_MITSUI_TOCHI_START, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_tochi_start():
    logging.info("Start mitsuiTochiStart")
    obj = ParseMitsuiTochiStartAsync()
    url = "https://www.rehouse.co.jp/buy/tochi/"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiTochiStart")
        return ERROR_END, 500
    logging.info("Success mitsuiTochiStart")
    return result

mitsuiTochiStart = mitsui_tochi_start


@mitsui_bp.route(API_KEY_MITSUI_TOCHI_AREA, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_tochi_area_local():
    mitsuiTochiArea(request)
    return "finish", 200

mitsuiTochiAreaLocal = mitsui_tochi_area_local


def mitsui_tochi_area(request):
    logging.info("Start mitsuiTochiArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiTochiAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiTochiArea")
        return ERROR_END, 500
    logging.info("Success mitsuiTochiArea")
    return "finish", 200

mitsuiTochiArea = mitsui_tochi_area


@mitsui_bp.route(API_KEY_MITSUI_TOCHI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_tochi_property_list_local():
    mitsuiTochiPropertyList(request)
    return "finish", 200

mitsuiTochiPropertyListLocal = mitsui_tochi_property_list_local


def mitsui_tochi_property_list(request):
    logging.info("Start mitsuiTochiPropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiTochiListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiTochiPropertyList")
        return ERROR_END, 500
    logging.info("Success mitsuiTochiPropertyList")
    return "finish", 200

mitsuiTochiPropertyList = mitsui_tochi_property_list


@mitsui_bp.route(API_KEY_MITSUI_TOCHI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_tochi_property_detail_local():
    mitsuiTochiPropertyDetail(request)
    return "finish", 200

mitsuiTochiPropertyDetailLocal = mitsui_tochi_property_detail_local


def mitsui_tochi_property_detail(request):
    logging.info("Start mitsuiTochiPropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiTochiDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiTochiPropertyDetail")
        return ERROR_END, 500
    logging.info("Success mitsuiTochiPropertyDetail")
    return "finish", 200

mitsuiTochiPropertyDetail = mitsui_tochi_property_detail


@mitsui_bp.route(API_KEY_MITSUI_TOCHI_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_tochi_property_detail_test():
    logging.info(START_PROPERTY_DETAIL)
    url = "https://www.rehouse.co.jp/buy/tochi/bkdetail/FBHZGA14/"
    obj = ParseMitsuiTochiDetailFuncAsync()
    result = obj.main(url)
    logging.info(END_PROPERTY_DETAIL)
    return result

mitsuiTochiPropertyDetailTest = mitsui_tochi_property_detail_test

###################################################
# mitsui kodate
###################################################
@mitsui_bp.route(API_KEY_MITSUI_KODATE_START, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_kodate_start():
    logging.info("Start mitsuiKodateStart")
    obj = ParseMitsuiKodateStartAsync()
    url = "https://www.rehouse.co.jp/buy/kodate/"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiKodateStart")
        return ERROR_END, 500
    logging.info("Success mitsuiKodateStart")
    return result

mitsuiKodateStart = mitsui_kodate_start


@mitsui_bp.route(API_KEY_MITSUI_KODATE_AREA, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_kodate_area_local():
    mitsuiKodateArea(request)
    return "finish", 200

mitsuiKodateAreaLocal = mitsui_kodate_area_local


def mitsui_kodate_area(request):
    logging.info("Start mitsuiKodateArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiKodateAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiKodateArea")
        return ERROR_END, 500
    logging.info("Success mitsuiKodateArea")
    return "finish", 200

mitsuiKodateArea = mitsui_kodate_area


@mitsui_bp.route(API_KEY_MITSUI_KODATE_LIST, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_kodate_property_list_local():
    mitsuiKodatePropertyList(request)
    return "finish", 200

mitsuiKodatePropertyListLocal = mitsui_kodate_property_list_local


def mitsui_kodate_property_list(request):
    logging.info("Start mitsuiKodatePropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiKodateListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiKodatePropertyList")
        return ERROR_END, 500
    logging.info("Success mitsuiKodatePropertyList")
    return "finish", 200

mitsuiKodatePropertyList = mitsui_kodate_property_list


@mitsui_bp.route(API_KEY_MITSUI_KODATE_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_kodate_property_detail_local():
    mitsuiKodatePropertyDetail(request)
    return "finish", 200

mitsuiKodatePropertyDetailLocal = mitsui_kodate_property_detail_local


def mitsui_kodate_property_detail(request):
    logging.info("Start mitsuiKodatePropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseMitsuiKodateDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed mitsuiKodatePropertyDetail")
        return ERROR_END, 500
    logging.info("Success mitsuiKodatePropertyDetail")
    return "finish", 200

mitsuiKodatePropertyDetail = mitsui_kodate_property_detail


@mitsui_bp.route(API_KEY_MITSUI_KODATE_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def mitsui_kodate_property_detail_test():
    logging.info(START_PROPERTY_DETAIL)
    url = "https://www.rehouse.co.jp/kodate/bkdetail/FLGZ4A09/"
    obj = ParseMitsuiKodateDetailFuncAsync()
    result = obj.main(url)
    logging.info(END_PROPERTY_DETAIL)
    return result

mitsuiKodatePropertyDetailTest = mitsui_kodate_property_detail_test

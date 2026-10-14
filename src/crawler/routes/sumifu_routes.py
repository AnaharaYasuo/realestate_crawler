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

ERROR_END = "error end"
START_PROPERTY_DETAIL = "start propertyDetail"
END_PROPERTY_DETAIL = "end propertyDetail"

# Cloud Functions entry point (optional, depends on how it's used)
def parse_sumifu_start_mansion_async_pub_sub(event, context):
    return sumifuMansionStart()

parseSumifuStartMansionAsyncPubSub = parse_sumifu_start_mansion_async_pub_sub

###################################################
# sumifu Mansion
###################################################
@sumifu_bp.route(API_KEY_SUMIFU_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_mansion_start():
    logging.info("Start sumifuMansionStart")
    obj = ParseSumifuMansionStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed sumifuMansionStart")
        return ERROR_END, 500
    logging.info("Success sumifuMansionStart")

    return result

sumifuMansionStart = sumifu_mansion_start


@sumifu_bp.route(API_KEY_SUMIFU_MANSION_REGION, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_mansion_region_local():
    sumifuMansionRegion(request)
    return "finish", 200

sumifuMansionRegionLocal = sumifu_mansion_region_local


def sumifu_mansion_region(request):
    logging.info("Start sumifuMansionRegion")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuMansionRegionFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuMansionRegion")
        return ERROR_END, 500
    logging.info("Success sumifuMansionRegion")
    return "finish", 200

sumifuMansionRegion = sumifu_mansion_region


@sumifu_bp.route(API_KEY_SUMIFU_MANSION_AREA, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_mansion_area_local():
    sumifuMansionArea(request)
    return "finish", 200

sumifuMansionAreaLocal = sumifu_mansion_area_local


def sumifu_mansion_area(request):
    logging.info("Start sumifuMansionArea")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuMansionAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuMansionArea")
        return ERROR_END, 500
    logging.info("Success sumifuMansionArea")
    return "finish", 200

sumifuMansionArea = sumifu_mansion_area


@sumifu_bp.route(API_KEY_SUMIFU_MANSION_LIST, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_mansion_property_list_local():
    sumifuMansionPropertyList(request)
    return "finish", 200

sumifuMansionPropertyListLocal = sumifu_mansion_property_list_local


def sumifu_mansion_property_list(request):
    logging.info("Start sumifuMansionPropertyList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuMansionListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuMansionPropertyList")
        return ERROR_END, 500
    logging.info("Success sumifuMansionPropertyList")
    return "finish", 200

sumifuMansionPropertyList = sumifu_mansion_property_list


@sumifu_bp.route(API_KEY_SUMIFU_MANSION_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_mansion_property_detail_local():
    sumifuMansionPropertyDetail(request)
    return "finish", 200

sumifuMansionPropertyDetailLocal = sumifu_mansion_property_detail_local


def sumifu_mansion_property_detail(request):
    logging.info("Start sumifuMansionPropertyDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuMansionDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuMansionPropertyDetail")
        return ERROR_END, 500
    logging.info("Success sumifuMansionPropertyDetail")
    return "finish", 200

sumifuMansionPropertyDetail = sumifu_mansion_property_detail


@sumifu_bp.route(API_KEY_SUMIFU_MANSION_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_mansion_property_detail_test():
    logging.info(START_PROPERTY_DETAIL)
    url = "https://www.stepon.co.jp/mansion/detail_12583039/"
    obj = ParseSumifuMansionDetailFuncAsync()
    result = obj.main(url)
    logging.info(END_PROPERTY_DETAIL)
    return result

sumifuMansionPropertyDetailTest = sumifu_mansion_property_detail_test

###################################################
# sumifu tochi
###################################################
@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_START, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_tochi_start():
    logging.info("Start sumifuTochiStart")
    obj = ParseSumifuTochiStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed sumifuTochiStart")
        return ERROR_END, 500
    logging.info("Success sumifuTochiStart")

    return result

sumifuTochiStart = sumifu_tochi_start


@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_REGION, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_tochi_region_local():
    sumifuTochiRegion(request)
    return "finish", 200

sumifuTochiRegionLocal = sumifu_tochi_region_local


def sumifu_tochi_region(request):
    logging.info("Start sumifuTochiRegion")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuTochiRegionFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuTochiRegion")
        return ERROR_END, 500
    logging.info("Success sumifuTochiRegion")
    return "finish", 200

sumifuTochiRegion = sumifu_tochi_region


@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_AREA, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_tochi_area_local():
    sumifuTochiArea(request)
    return "finish", 200

sumifuTochiAreaLocal = sumifu_tochi_area_local


def sumifu_tochi_area(request):
    logging.info("Start sumifuTochiArea")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuTochiAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuTochiArea")
        return ERROR_END, 500
    logging.info("Success sumifuTochiArea")
    return "finish", 200

sumifuTochiArea = sumifu_tochi_area


@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_tochi_property_list_local():
    sumifuTochiPropertyList(request)
    return "finish", 200

sumifuTochiPropertyListLocal = sumifu_tochi_property_list_local


def sumifu_tochi_property_list(request):
    logging.info("Start sumifuTochiPropertyList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuTochiListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuTochiPropertyList")
        return ERROR_END, 500
    logging.info("Success sumifuTochiPropertyList")
    return "finish", 200

sumifuTochiPropertyList = sumifu_tochi_property_list


@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_tochi_property_detail_local():
    sumifuTochiPropertyDetail(request)
    return "finish", 200

sumifuTochiPropertyDetailLocal = sumifu_tochi_property_detail_local


def sumifu_tochi_property_detail(request):
    logging.info("Start sumifuTochiPropertyDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuTochiDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuTochiPropertyDetail")
        return ERROR_END, 500
    logging.info("Success sumifuTochiPropertyDetail")
    return "finish", 200

sumifuTochiPropertyDetail = sumifu_tochi_property_detail


@sumifu_bp.route(API_KEY_SUMIFU_TOCHI_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_tochi_property_detail_test():
    logging.info(START_PROPERTY_DETAIL)
    url = "https://www.stepon.co.jp/tochi/detail_12011023/"
    obj = ParseSumifuTochiDetailFuncAsync()
    result = obj.main(url)
    logging.info(END_PROPERTY_DETAIL)
    return result

sumifuTochiPropertyDetailTest = sumifu_tochi_property_detail_test

###################################################
# sumifu kodate
###################################################
@sumifu_bp.route(API_KEY_SUMIFU_KODATE_START, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_kodate_start():
    logging.info("Start sumifuKodateStart")
    obj = ParseSumifuKodateStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed sumifuKodateStart")
        return ERROR_END, 500
    logging.info("Success sumifuKodateStart")

    return result

sumifuKodateStart = sumifu_kodate_start


@sumifu_bp.route(API_KEY_SUMIFU_KODATE_REGION, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_kodate_region_local():
    sumifuKodateRegion(request)
    return "finish", 200

sumifuKodateRegionLocal = sumifu_kodate_region_local


def sumifu_kodate_region(request):
    logging.info("Start sumifuKodateRegion")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuKodateRegionFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuKodateRegion")
        return ERROR_END, 500
    logging.info("Success sumifuKodateRegion")
    return "finish", 200

sumifuKodateRegion = sumifu_kodate_region


@sumifu_bp.route(API_KEY_SUMIFU_KODATE_AREA, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_kodate_area_local():
    sumifuKodateArea(request)
    return "finish", 200

sumifuKodateAreaLocal = sumifu_kodate_area_local


def sumifu_kodate_area(request):
    logging.info("Start sumifuKodateArea")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuKodateAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuKodateArea")
        return ERROR_END, 500
    logging.info("Success sumifuKodateArea")
    return "finish", 200

sumifuKodateArea = sumifu_kodate_area


@sumifu_bp.route(API_KEY_SUMIFU_KODATE_LIST, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_kodate_property_list_local():
    sumifuKodatePropertyList(request)
    return "finish", 200

sumifuKodatePropertyListLocal = sumifu_kodate_property_list_local


def sumifu_kodate_property_list(request):
    logging.info("Start sumifuKodatePropertyList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuKodateListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuKodatePropertyList")
        return ERROR_END, 500
    logging.info("Success sumifuKodatePropertyList")
    return "finish", 200

sumifuKodatePropertyList = sumifu_kodate_property_list


@sumifu_bp.route(API_KEY_SUMIFU_KODATE_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_kodate_property_detail_local():
    sumifuKodatePropertyDetail(request)
    return "finish", 200

sumifuKodatePropertyDetailLocal = sumifu_kodate_property_detail_local


def sumifu_kodate_property_detail(request):
    logging.info("Start sumifuKodatePropertyDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseSumifuKodateDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed sumifuKodatePropertyDetail")
        return ERROR_END, 500
    logging.info("Success sumifuKodatePropertyDetail")
    return "finish", 200

sumifuKodatePropertyDetail = sumifu_kodate_property_detail


@sumifu_bp.route(API_KEY_SUMIFU_KODATE_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def sumifu_kodate_property_detail_test():
    logging.info(START_PROPERTY_DETAIL)
    url = "https://www.stepon.co.jp/kodate/detail_12012003/"
    obj = ParseSumifuKodateDetailFuncAsync()
    result = obj.main(url)
    logging.info(END_PROPERTY_DETAIL)
    return result

sumifuKodatePropertyDetailTest = sumifu_kodate_property_detail_test

import logging
import traceback
import json
from flask import Blueprint, request
from package.api.api import (
    API_KEY_TOKYU_MANSION_START, API_KEY_TOKYU_MANSION_AREA, API_KEY_TOKYU_MANSION_LIST, API_KEY_TOKYU_MANSION_DETAIL, API_KEY_TOKYU_MANSION_DETAIL_TEST,
    API_KEY_TOKYU_TOCHI_START, API_KEY_TOKYU_TOCHI_AREA, API_KEY_TOKYU_TOCHI_LIST, API_KEY_TOKYU_TOCHI_DETAIL,
    API_KEY_TOKYU_KODATE_START, API_KEY_TOKYU_KODATE_AREA, API_KEY_TOKYU_KODATE_LIST, API_KEY_TOKYU_KODATE_DETAIL
)
from package.api.tokyu import (
    ParseTokyuMansionStartAsync, ParseTokyuMansionAreaFuncAsync, ParseTokyuMansionListFuncAsync, ParseTokyuMansionDetailFuncAsync,
    ParseTokyuTochiStartAsync, ParseTokyuTochiAreaFuncAsync, ParseTokyuTochiListFuncAsync, ParseTokyuTochiDetailFuncAsync,
    ParseTokyuKodateStartAsync, ParseTokyuKodateAreaFuncAsync, ParseTokyuKodateListFuncAsync, ParseTokyuKodateDetailFuncAsync
)

tokyu_bp = Blueprint('tokyu', __name__)

ERROR_END = "error end"

###################################################
# tokyu mansion
###################################################
@tokyu_bp.route(API_KEY_TOKYU_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_mansion_start():
    logging.info("Start tokyuMansionStart")
    obj = ParseTokyuMansionStartAsync()
    url = "https://www.livable.co.jp/kounyu/chuko-mansion/select-area/"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed tokyuMansionStart")
        return ERROR_END, 500
    logging.info("Success tokyuMansionStart")
    return result

tokyuMansionStart = tokyu_mansion_start


@tokyu_bp.route(API_KEY_TOKYU_MANSION_AREA, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_mansion_area_local():
    tokyuMansionArea(request)
    return "finish", 200

tokyuMansionAreaLocal = tokyu_mansion_area_local


def tokyu_mansion_area(request):
    logging.info("Start tokyuMansionArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuMansionAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed tokyuMansionArea")
        return ERROR_END, 500
    logging.info("Success tokyuMansionArea")
    return "finish", 200

tokyuMansionArea = tokyu_mansion_area


@tokyu_bp.route(API_KEY_TOKYU_MANSION_LIST, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_mansion_property_list_local():
    tokyuMansionPropertyList(request)
    return "finish", 200

tokyuMansionPropertyListLocal = tokyu_mansion_property_list_local


def tokyu_mansion_property_list(request):
    logging.info("Start tokyuMansionPropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuMansionListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed tokyuMansionPropertyList")
        return ERROR_END, 500
    logging.info("Success tokyuMansionPropertyList")
    return "finish", 200

tokyuMansionPropertyList = tokyu_mansion_property_list


@tokyu_bp.route(API_KEY_TOKYU_MANSION_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_mansion_property_detail_local():
    tokyuMansionPropertyDetail(request)
    return "finish", 200

tokyuMansionPropertyDetailLocal = tokyu_mansion_property_detail_local


def tokyu_mansion_property_detail(request):
    logging.info("Start tokyuMansionPropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuMansionDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed tokyuMansionPropertyDetail")
        return ERROR_END, 500
    logging.info("Success tokyuMansionPropertyDetail")
    return "finish", 200

tokyuMansionPropertyDetail = tokyu_mansion_property_detail


@tokyu_bp.route(API_KEY_TOKYU_MANSION_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_mansion_property_detail_test():
    logging.info("start propertyDetail")
    obj = ParseTokyuMansionDetailFuncAsync()
    url = "https://www.livable.co.jp/mansion/C13261K62/"
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result

tokyuMansionPropertyDetailTest = tokyu_mansion_property_detail_test

###################################################
# tokyu tochi
###################################################
@tokyu_bp.route(API_KEY_TOKYU_TOCHI_START, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_tochi_start():
    logging.info("Start tokyuTochiStart")
    obj = ParseTokyuTochiStartAsync()
    url = "https://www.livable.co.jp/kounyu/tochi/select-area/"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed tokyuTochiStart")
        return ERROR_END, 500
    logging.info("Success tokyuTochiStart")
    return result

tokyuTochiStart = tokyu_tochi_start

@tokyu_bp.route(API_KEY_TOKYU_TOCHI_AREA, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_tochi_area_local():
    tokyuTochiArea(request)
    return "finish", 200

tokyuTochiAreaLocal = tokyu_tochi_area_local

def tokyu_tochi_area(request):
    logging.info("Start tokyuTochiArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuTochiAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed tokyuTochiArea")
        return ERROR_END, 500
    logging.info("Success tokyuTochiArea")
    return "finish", 200

tokyuTochiArea = tokyu_tochi_area

@tokyu_bp.route(API_KEY_TOKYU_TOCHI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_tochi_property_list_local():
    tokyuTochiPropertyList(request)
    return "finish", 200

tokyuTochiPropertyListLocal = tokyu_tochi_property_list_local

def tokyu_tochi_property_list(request):
    logging.info("Start tokyuTochiPropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuTochiListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed tokyuTochiPropertyList")
        return ERROR_END, 500
    logging.info("Success tokyuTochiPropertyList")
    return "finish", 200

tokyuTochiPropertyList = tokyu_tochi_property_list

@tokyu_bp.route(API_KEY_TOKYU_TOCHI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_tochi_property_detail_local():
    tokyuTochiPropertyDetail(request)
    return "finish", 200

tokyuTochiPropertyDetailLocal = tokyu_tochi_property_detail_local

def tokyu_tochi_property_detail(request):
    logging.info("Start tokyuTochiPropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuTochiDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed tokyuTochiPropertyDetail")
        return ERROR_END, 500
    logging.info("Success tokyuTochiPropertyDetail")
    return "finish", 200

tokyuTochiPropertyDetail = tokyu_tochi_property_detail


###################################################
# tokyu kodate
###################################################
@tokyu_bp.route(API_KEY_TOKYU_KODATE_START, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_kodate_start():
    logging.info("Start tokyuKodateStart")
    obj = ParseTokyuKodateStartAsync()
    url = "https://www.livable.co.jp/kounyu/kodate/select-area/"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed tokyuKodateStart")
        return ERROR_END, 500
    logging.info("Success tokyuKodateStart")
    return result

tokyuKodateStart = tokyu_kodate_start

@tokyu_bp.route(API_KEY_TOKYU_KODATE_AREA, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_kodate_area_local():
    tokyuKodateArea(request)
    return "finish", 200

tokyuKodateAreaLocal = tokyu_kodate_area_local

def tokyu_kodate_area(request):
    logging.info("Start tokyuKodateArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuKodateAreaFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed tokyuKodateArea")
        return ERROR_END, 500
    logging.info("Success tokyuKodateArea")
    return "finish", 200

tokyuKodateArea = tokyu_kodate_area

@tokyu_bp.route(API_KEY_TOKYU_KODATE_LIST, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_kodate_property_list_local():
    tokyuKodatePropertyList(request)
    return "finish", 200

tokyuKodatePropertyListLocal = tokyu_kodate_property_list_local

def tokyu_kodate_property_list(request):
    logging.info("Start tokyuKodatePropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuKodateListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed tokyuKodatePropertyList")
        return ERROR_END, 500
    logging.info("Success tokyuKodatePropertyList")
    return "finish", 200

tokyuKodatePropertyList = tokyu_kodate_property_list

@tokyu_bp.route(API_KEY_TOKYU_KODATE_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def tokyu_kodate_property_detail_local():
    tokyuKodatePropertyDetail(request)
    return "finish", 200

tokyuKodatePropertyDetailLocal = tokyu_kodate_property_detail_local

def tokyu_kodate_property_detail(request):
    logging.info("Start tokyuKodatePropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuKodateDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed tokyuKodatePropertyDetail")
        return ERROR_END, 500
    logging.info("Success tokyuKodatePropertyDetail")
    return "finish", 200

tokyuKodatePropertyDetail = tokyu_kodate_property_detail

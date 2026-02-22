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

###################################################
# tokyu mansion
###################################################
@tokyu_bp.route(API_KEY_TOKYU_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def tokyuMansionStart():
    logging.info("Start tokyuMansionStart")
    obj = ParseTokyuMansionStartAsync()
    url = "https://www.livable.co.jp/kounyu/chuko-mansion/select-area/"
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuMansionStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuMansionStart")
    return result


@tokyu_bp.route(API_KEY_TOKYU_MANSION_AREA, methods=['OPTIONS', 'POST', 'GET'])
def tokyuMansionAreaLocal():
    return tokyuMansionArea(request)


def tokyuMansionArea(request):
    logging.info("Start tokyuMansionArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuMansionAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuMansionArea")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuMansionArea")
    return result


@tokyu_bp.route(API_KEY_TOKYU_MANSION_LIST, methods=['OPTIONS', 'POST', 'GET'])
def tokyuMansionPropertyListLocal():
    return tokyuMansionPropertyList(request)


def tokyuMansionPropertyList(request):
    logging.info("Start tokyuMansionPropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuMansionListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuMansionPropertyList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuMansionPropertyList")
    return result


@tokyu_bp.route(API_KEY_TOKYU_MANSION_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def tokyuMansionPropertyDetailLocal():
    return tokyuMansionPropertyDetail(request)


def tokyuMansionPropertyDetail(request):
    logging.info("Start tokyuMansionPropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuMansionDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuMansionPropertyDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuMansionPropertyDetail")
    return result


@tokyu_bp.route(API_KEY_TOKYU_MANSION_DETAIL_TEST, methods=['OPTIONS', 'POST', 'GET'])
def tokyuMansionPropertyDetailTest():
    logging.info("start propertyDetail")
    # request_json = json.loads(request.get_json())
    # url = request_json['url']
    obj = ParseTokyuMansionDetailFuncAsync()
    url = "https://www.livable.co.jp/mansion/C13261K62/"
    result = obj.main(url)
    logging.info("end propertyDetail")
    return result

###################################################
# tokyu tochi
###################################################
@tokyu_bp.route(API_KEY_TOKYU_TOCHI_START, methods=['OPTIONS', 'POST', 'GET'])
def tokyuTochiStart():
    logging.info("Start tokyuTochiStart")
    obj = ParseTokyuTochiStartAsync()
    url = "https://www.livable.co.jp/kounyu/tochi/select-area/"
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuTochiStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuTochiStart")
    return result

@tokyu_bp.route(API_KEY_TOKYU_TOCHI_AREA, methods=['OPTIONS', 'POST', 'GET'])
def tokyuTochiAreaLocal():
    return tokyuTochiArea(request)

def tokyuTochiArea(request):
    logging.info("Start tokyuTochiArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuTochiAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuTochiArea")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuTochiArea")
    return result

@tokyu_bp.route(API_KEY_TOKYU_TOCHI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def tokyuTochiPropertyListLocal():
    return tokyuTochiPropertyList(request)

def tokyuTochiPropertyList(request):
    logging.info("Start tokyuTochiPropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuTochiListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuTochiPropertyList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuTochiPropertyList")
    return result

@tokyu_bp.route(API_KEY_TOKYU_TOCHI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def tokyuTochiPropertyDetailLocal():
    return tokyuTochiPropertyDetail(request)

def tokyuTochiPropertyDetail(request):
    logging.info("Start tokyuTochiPropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuTochiDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuTochiPropertyDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuTochiPropertyDetail")
    return result


###################################################
# tokyu kodate
###################################################
@tokyu_bp.route(API_KEY_TOKYU_KODATE_START, methods=['OPTIONS', 'POST', 'GET'])
def tokyuKodateStart():
    logging.info("Start tokyuKodateStart")
    obj = ParseTokyuKodateStartAsync()
    url = "https://www.livable.co.jp/kounyu/kodate/select-area/"
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuKodateStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuKodateStart")
    return result

@tokyu_bp.route(API_KEY_TOKYU_KODATE_AREA, methods=['OPTIONS', 'POST', 'GET'])
def tokyuKodateAreaLocal():
    return tokyuKodateArea(request)

def tokyuKodateArea(request):
    logging.info("Start tokyuKodateArea")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuKodateAreaFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuKodateArea")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuKodateArea")
    return result

@tokyu_bp.route(API_KEY_TOKYU_KODATE_LIST, methods=['OPTIONS', 'POST', 'GET'])
def tokyuKodatePropertyListLocal():
    return tokyuKodatePropertyList(request)

def tokyuKodatePropertyList(request):
    logging.info("Start tokyuKodatePropertyList")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuKodateListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuKodatePropertyList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuKodatePropertyList")
    return result

@tokyu_bp.route(API_KEY_TOKYU_KODATE_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def tokyuKodatePropertyDetailLocal():
    return tokyuKodatePropertyDetail(request)

def tokyuKodatePropertyDetail(request):
    logging.info("Start tokyuKodatePropertyDetail")
    request_json = json.loads(request.get_json())
    url = request_json['url']
    obj = ParseTokyuKodateDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed tokyuKodatePropertyDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success tokyuKodatePropertyDetail")
    return result

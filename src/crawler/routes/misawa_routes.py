
import logging
import traceback
import json
from flask import Blueprint, request
from package.api.api import (
    API_KEY_MISAWA_MANSION_START, API_KEY_MISAWA_MANSION_LIST, API_KEY_MISAWA_MANSION_DETAIL,
    API_KEY_MISAWA_KODATE_START, API_KEY_MISAWA_KODATE_LIST, API_KEY_MISAWA_KODATE_DETAIL,
    API_KEY_MISAWA_TOCHI_START, API_KEY_MISAWA_TOCHI_LIST, API_KEY_MISAWA_TOCHI_DETAIL
)
from package.api.misawa import (
    ParseMisawaMansionStartAsync, ParseMisawaMansionListFuncAsync, ParseMisawaMansionDetailFuncAsync,
    ParseMisawaKodateStartAsync, ParseMisawaKodateListFuncAsync, ParseMisawaKodateDetailFuncAsync,
    ParseMisawaTochiStartAsync, ParseMisawaTochiListFuncAsync, ParseMisawaTochiDetailFuncAsync
)

misawa_bp = Blueprint('misawa', __name__)

ERROR_END = "error end"

# ==========================================
# Mansion
# ==========================================

@misawa_bp.route(API_KEY_MISAWA_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def misawa_mansion_start():
    logging.info("Start misawaMansionStart")
    obj = ParseMisawaMansionStartAsync()
    url = "https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=3"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed misawaMansionStart")
        return ERROR_END, 500
    logging.info("Success misawaMansionStart")
    return result

misawaMansionStart = misawa_mansion_start

@misawa_bp.route(API_KEY_MISAWA_MANSION_LIST, methods=['OPTIONS', 'POST', 'GET'])
def misawa_mansion_list():
    logging.info("Start misawaMansionList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaMansionListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed misawaMansionList")
        return ERROR_END, 500
    logging.info("Success misawaMansionList")
    return "finish", 200

misawaMansionList = misawa_mansion_list

@misawa_bp.route(API_KEY_MISAWA_MANSION_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def misawa_mansion_detail():
    logging.info("Start misawaMansionDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaMansionDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed misawaMansionDetail")
        return ERROR_END, 500
    logging.info("Success misawaMansionDetail")
    return "finish", 200

misawaMansionDetail = misawa_mansion_detail

# ==========================================
# Kodate
# ==========================================

@misawa_bp.route(API_KEY_MISAWA_KODATE_START, methods=['OPTIONS', 'POST', 'GET'])
def misawa_kodate_start():
    logging.info("Start misawaKodateStart")
    obj = ParseMisawaKodateStartAsync()
    url = "https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=2"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed misawaKodateStart")
        return ERROR_END, 500
    logging.info("Success misawaKodateStart")
    return result

misawaKodateStart = misawa_kodate_start

@misawa_bp.route(API_KEY_MISAWA_KODATE_LIST, methods=['OPTIONS', 'POST', 'GET'])
def misawa_kodate_list():
    logging.info("Start misawaKodateList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaKodateListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed misawaKodateList")
        return ERROR_END, 500
    logging.info("Success misawaKodateList")
    return "finish", 200

misawaKodateList = misawa_kodate_list

@misawa_bp.route(API_KEY_MISAWA_KODATE_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def misawa_kodate_detail():
    logging.info("Start misawaKodateDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaKodateDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed misawaKodateDetail")
        return ERROR_END, 500
    logging.info("Success misawaKodateDetail")
    return "finish", 200

misawaKodateDetail = misawa_kodate_detail

# ==========================================
# Tochi
# ==========================================

@misawa_bp.route(API_KEY_MISAWA_TOCHI_START, methods=['OPTIONS', 'POST', 'GET'])
def misawa_tochi_start():
    logging.info("Start misawaTochiStart")
    obj = ParseMisawaTochiStartAsync()
    url = "https://realestate.misawa.co.jp/search/sale/list/?bukken_type%5B%5D=1"
    try:
        result = obj.main(url)
    except Exception:
        logging.exception("Failed misawaTochiStart")
        return ERROR_END, 500
    logging.info("Success misawaTochiStart")
    return result

misawaTochiStart = misawa_tochi_start

@misawa_bp.route(API_KEY_MISAWA_TOCHI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def misawa_tochi_list():
    logging.info("Start misawaTochiList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaTochiListFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed misawaTochiList")
        return ERROR_END, 500
    logging.info("Success misawaTochiList")
    return "finish", 200

misawaTochiList = misawa_tochi_list

@misawa_bp.route(API_KEY_MISAWA_TOCHI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def misawa_tochi_detail():
    logging.info("Start misawaTochiDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaTochiDetailFuncAsync()
    try:
        obj.main(url)
    except Exception:
        logging.exception("Failed misawaTochiDetail")
        return ERROR_END, 500
    logging.info("Success misawaTochiDetail")
    return "finish", 200

misawaTochiDetail = misawa_tochi_detail

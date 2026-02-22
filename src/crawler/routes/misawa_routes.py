
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

# ==========================================
# Mansion
# ==========================================

@misawa_bp.route(API_KEY_MISAWA_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def misawaMansionStart():
    logging.info("Start misawaMansionStart")
    obj = ParseMisawaMansionStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except:
        logging.error("Failed misawaMansionStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaMansionStart")
    return result

@misawa_bp.route(API_KEY_MISAWA_MANSION_LIST, methods=['OPTIONS', 'POST', 'GET'])
def misawaMansionList():
    logging.info("Start misawaMansionList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaMansionListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed misawaMansionList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaMansionList")
    return result

@misawa_bp.route(API_KEY_MISAWA_MANSION_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def misawaMansionDetail():
    logging.info("Start misawaMansionDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaMansionDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed misawaMansionDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaMansionDetail")
    return result

# ==========================================
# Kodate
# ==========================================

@misawa_bp.route(API_KEY_MISAWA_KODATE_START, methods=['OPTIONS', 'POST', 'GET'])
def misawaKodateStart():
    logging.info("Start misawaKodateStart")
    obj = ParseMisawaKodateStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except:
        logging.error("Failed misawaKodateStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaKodateStart")
    return result

@misawa_bp.route(API_KEY_MISAWA_KODATE_LIST, methods=['OPTIONS', 'POST', 'GET'])
def misawaKodateList():
    logging.info("Start misawaKodateList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaKodateListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed misawaKodateList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaKodateList")
    return result

@misawa_bp.route(API_KEY_MISAWA_KODATE_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def misawaKodateDetail():
    logging.info("Start misawaKodateDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaKodateDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed misawaKodateDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaKodateDetail")
    return result

# ==========================================
# Tochi
# ==========================================

@misawa_bp.route(API_KEY_MISAWA_TOCHI_START, methods=['OPTIONS', 'POST', 'GET'])
def misawaTochiStart():
    logging.info("Start misawaTochiStart")
    obj = ParseMisawaTochiStartAsync()
    url = "dammy"
    try:
        result = obj.main(url)
    except:
        logging.error("Failed misawaTochiStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaTochiStart")
    return result

@misawa_bp.route(API_KEY_MISAWA_TOCHI_LIST, methods=['OPTIONS', 'POST', 'GET'])
def misawaTochiList():
    logging.info("Start misawaTochiList")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaTochiListFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed misawaTochiList")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaTochiList")
    return result

@misawa_bp.route(API_KEY_MISAWA_TOCHI_DETAIL, methods=['OPTIONS', 'POST', 'GET'])
def misawaTochiDetail():
    logging.info("Start misawaTochiDetail")
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    obj = ParseMisawaTochiDetailFuncAsync()
    try:
        result = obj.main(url)
    except:
        logging.error("Failed misawaTochiDetail")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaTochiDetail")
    return result

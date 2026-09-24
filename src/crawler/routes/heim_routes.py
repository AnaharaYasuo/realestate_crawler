# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_HEIM_MANSION_START, API_KEY_HEIM_MANSION_DETAIL,
    API_KEY_HEIM_KODATE_START, API_KEY_HEIM_KODATE_DETAIL,
    API_KEY_HEIM_TOCHI_START, API_KEY_HEIM_TOCHI_DETAIL
)
from package.api.heim import (
    ParseHeimMansionStartAsync, ParseHeimMansionDetailFuncAsync,
    ParseHeimKodateStartAsync, ParseHeimKodateDetailFuncAsync,
    ParseHeimTochiStartAsync, ParseHeimTochiDetailFuncAsync
)

heim_bp = Blueprint('heim', __name__)

HEIM_TOKYO_SEARCH_URL = "https://www.tokyo816.jp/bunjou/search_area?all_pref=1&pref_check%5B%5D=13"

@heim_bp.route(API_KEY_HEIM_MANSION_START, methods=['POST', 'GET'])
def heim_mansion_start():
    # 東京都全体の中古マンション・分譲住宅
    return ParseHeimMansionStartAsync().main(HEIM_TOKYO_SEARCH_URL)

heimMansionStart = heim_mansion_start

@heim_bp.route(API_KEY_HEIM_MANSION_DETAIL, methods=['POST', 'GET'])
def heim_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseHeimMansionDetailFuncAsync().main(url)
    return "finish", 200

heimMansionDetail = heim_mansion_detail

@heim_bp.route(API_KEY_HEIM_KODATE_START, methods=['POST', 'GET'])
def heim_kodate_start():
    # 東京都全体の中古戸建て・分譲住宅
    return ParseHeimKodateStartAsync().main(HEIM_TOKYO_SEARCH_URL)

heimKodateStart = heim_kodate_start

@heim_bp.route(API_KEY_HEIM_KODATE_DETAIL, methods=['POST', 'GET'])
def heim_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseHeimKodateDetailFuncAsync().main(url)
    return "finish", 200

heimKodateDetail = heim_kodate_detail

@heim_bp.route(API_KEY_HEIM_TOCHI_START, methods=['POST', 'GET'])
def heim_tochi_start():
    # 東京都全体の土地
    return ParseHeimTochiStartAsync().main(HEIM_TOKYO_SEARCH_URL)

heimTochiStart = heim_tochi_start


@heim_bp.route(API_KEY_HEIM_TOCHI_DETAIL, methods=['POST', 'GET'])
def heim_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseHeimTochiDetailFuncAsync().main(url)
    return "finish", 200

heimTochiDetail = heim_tochi_detail

# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_DAIWA_MANSION_START, API_KEY_DAIWA_MANSION_DETAIL,
    API_KEY_DAIWA_KODATE_START, API_KEY_DAIWA_KODATE_DETAIL,
    API_KEY_DAIWA_TOCHI_START, API_KEY_DAIWA_TOCHI_DETAIL
)
from package.api.daiwa import (
    ParseDaiwaMansionStartAsync, ParseDaiwaMansionDetailFuncAsync,
    ParseDaiwaKodateStartAsync, ParseDaiwaKodateDetailFuncAsync,
    ParseDaiwaTochiStartAsync, ParseDaiwaTochiDetailFuncAsync
)

daiwa_bp = Blueprint('daiwa', __name__)

def get_start_url(property_type='2'):
    # 全国対象の検索一覧スタートURL
    return f"https://www.dh-realestate.co.jp/buy/search/alist?property_type[]={property_type}"

@daiwa_bp.route(API_KEY_DAIWA_MANSION_START, methods=['POST', 'GET'])
def daiwa_mansion_start():
    return ParseDaiwaMansionStartAsync().main(get_start_url('2'))

daiwaMansionStart = daiwa_mansion_start

@daiwa_bp.route(API_KEY_DAIWA_MANSION_DETAIL, methods=['POST', 'GET'])
def daiwa_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseDaiwaMansionDetailFuncAsync().main(url)
    return "finish", 200

daiwaMansionDetail = daiwa_mansion_detail

@daiwa_bp.route(API_KEY_DAIWA_KODATE_START, methods=['POST', 'GET'])
def daiwa_kodate_start():
    return ParseDaiwaKodateStartAsync().main(get_start_url('1'))

daiwaKodateStart = daiwa_kodate_start

@daiwa_bp.route(API_KEY_DAIWA_KODATE_DETAIL, methods=['POST', 'GET'])
def daiwa_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseDaiwaKodateDetailFuncAsync().main(url)
    return "finish", 200

daiwaKodateDetail = daiwa_kodate_detail

@daiwa_bp.route(API_KEY_DAIWA_TOCHI_START, methods=['POST', 'GET'])
def daiwa_tochi_start():
    return ParseDaiwaTochiStartAsync().main(get_start_url('0'))

daiwaTochiStart = daiwa_tochi_start

@daiwa_bp.route(API_KEY_DAIWA_TOCHI_DETAIL, methods=['POST', 'GET'])
def daiwa_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseDaiwaTochiDetailFuncAsync().main(url)
    return "finish", 200

daiwaTochiDetail = daiwa_tochi_detail

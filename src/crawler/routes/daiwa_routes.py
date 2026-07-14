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
    # 東京都 (prefecture_code=13) をデフォルトのスタートとする
    return f"https://www.dh-realestate.co.jp/buy/search/alist?prefecture_code=13&property_type[]={property_type}"

@daiwa_bp.route(API_KEY_DAIWA_MANSION_START, methods=['POST', 'GET'])
def daiwaMansionStart():
    return ParseDaiwaMansionStartAsync().main(get_start_url('2'))

@daiwa_bp.route(API_KEY_DAIWA_MANSION_DETAIL, methods=['POST', 'GET'])
def daiwaMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseDaiwaMansionDetailFuncAsync().main(url)

@daiwa_bp.route(API_KEY_DAIWA_KODATE_START, methods=['POST', 'GET'])
def daiwaKodateStart():
    return ParseDaiwaKodateStartAsync().main(get_start_url('1'))

@daiwa_bp.route(API_KEY_DAIWA_KODATE_DETAIL, methods=['POST', 'GET'])
def daiwaKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseDaiwaKodateDetailFuncAsync().main(url)

@daiwa_bp.route(API_KEY_DAIWA_TOCHI_START, methods=['POST', 'GET'])
def daiwaTochiStart():
    return ParseDaiwaTochiStartAsync().main(get_start_url('0'))

@daiwa_bp.route(API_KEY_DAIWA_TOCHI_DETAIL, methods=['POST', 'GET'])
def daiwaTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseDaiwaTochiDetailFuncAsync().main(url)

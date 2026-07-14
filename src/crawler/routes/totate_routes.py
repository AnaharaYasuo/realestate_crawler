# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_TOTATE_MANSION_START, API_KEY_TOTATE_MANSION_DETAIL,
    API_KEY_TOTATE_KODATE_START, API_KEY_TOTATE_KODATE_DETAIL,
    API_KEY_TOTATE_TOCHI_START, API_KEY_TOTATE_TOCHI_DETAIL
)
from package.api.totate import (
    ParseTotateMansionStartAsync, ParseTotateMansionDetailFuncAsync,
    ParseTotateKodateStartAsync, ParseTotateKodateDetailFuncAsync,
    ParseTotateTochiStartAsync, ParseTotateTochiDetailFuncAsync
)

totate_bp = Blueprint('totate', __name__)

def get_start_url(property_type='mansion'):
    # 東京都世田谷区 (city[]=13112) をデフォルトのスタートとする
    return f"https://sumikae.ttfuhan.co.jp/buy/search/result/detail_search/{property_type}/kanto/?city[]=13112&limit=100"

@totate_bp.route(API_KEY_TOTATE_MANSION_START, methods=['POST', 'GET'])
def totateMansionStart():
    return ParseTotateMansionStartAsync().main(get_start_url('mansion'))

@totate_bp.route(API_KEY_TOTATE_MANSION_DETAIL, methods=['POST', 'GET'])
def totateMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseTotateMansionDetailFuncAsync().main(url)

@totate_bp.route(API_KEY_TOTATE_KODATE_START, methods=['POST', 'GET'])
def totateKodateStart():
    return ParseTotateKodateStartAsync().main(get_start_url('kodate'))

@totate_bp.route(API_KEY_TOTATE_KODATE_DETAIL, methods=['POST', 'GET'])
def totateKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseTotateKodateDetailFuncAsync().main(url)

@totate_bp.route(API_KEY_TOTATE_TOCHI_START, methods=['POST', 'GET'])
def totateTochiStart():
    return ParseTotateTochiStartAsync().main(get_start_url('tochi'))

@totate_bp.route(API_KEY_TOTATE_TOCHI_DETAIL, methods=['POST', 'GET'])
def totateTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseTotateTochiDetailFuncAsync().main(url)

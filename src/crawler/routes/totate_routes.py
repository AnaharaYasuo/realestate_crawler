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
def totate_mansion_start():
    return ParseTotateMansionStartAsync().main(get_start_url('mansion'))

totateMansionStart = totate_mansion_start

@totate_bp.route(API_KEY_TOTATE_MANSION_DETAIL, methods=['POST', 'GET'])
def totate_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseTotateMansionDetailFuncAsync().main(url)
    return "finish", 200

totateMansionDetail = totate_mansion_detail

@totate_bp.route(API_KEY_TOTATE_KODATE_START, methods=['POST', 'GET'])
def totate_kodate_start():
    return ParseTotateKodateStartAsync().main(get_start_url('kodate'))

totateKodateStart = totate_kodate_start

@totate_bp.route(API_KEY_TOTATE_KODATE_DETAIL, methods=['POST', 'GET'])
def totate_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseTotateKodateDetailFuncAsync().main(url)
    return "finish", 200

totateKodateDetail = totate_kodate_detail

@totate_bp.route(API_KEY_TOTATE_TOCHI_START, methods=['POST', 'GET'])
def totate_tochi_start():
    return ParseTotateTochiStartAsync().main(get_start_url('tochi'))

totateTochiStart = totate_tochi_start

@totate_bp.route(API_KEY_TOTATE_TOCHI_DETAIL, methods=['POST', 'GET'])
def totate_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseTotateTochiDetailFuncAsync().main(url)
    return "finish", 200

totateTochiDetail = totate_tochi_detail

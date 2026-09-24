# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_ODAKYU_MANSION_START, API_KEY_ODAKYU_MANSION_DETAIL,
    API_KEY_ODAKYU_KODATE_START, API_KEY_ODAKYU_KODATE_DETAIL,
    API_KEY_ODAKYU_TOCHI_START, API_KEY_ODAKYU_TOCHI_DETAIL,
    API_KEY_ODAKYU_INVESTMENT_START, API_KEY_ODAKYU_INVESTMENT_DETAIL
)
from package.api.odakyu import (
    ParseOdakyuMansionStartAsync, ParseOdakyuMansionDetailFuncAsync,
    ParseOdakyuKodateStartAsync, ParseOdakyuKodateDetailFuncAsync,
    ParseOdakyuTochiStartAsync, ParseOdakyuTochiDetailFuncAsync,
    ParseOdakyuInvestmentStartAsync, ParseOdakyuInvestmentDetailFuncAsync
)

odakyu_bp = Blueprint('odakyu', __name__)

def get_start_url(property_type='mansion'):
    # 全エリア（東京・神奈川・小田急沿線全域）一覧URLをスタートURLとする
    type_map = {'kodate': 'house', 'tochi': 'land'}
    url_type = type_map.get(property_type, property_type)
    return f"https://www.odakyu-chukai.com/{url_type}/list/"

@odakyu_bp.route(API_KEY_ODAKYU_MANSION_START, methods=['POST', 'GET'])
def odakyu_mansion_start():
    return ParseOdakyuMansionStartAsync().main(get_start_url('mansion'))

odakyuMansionStart = odakyu_mansion_start

@odakyu_bp.route(API_KEY_ODAKYU_MANSION_DETAIL, methods=['POST', 'GET'])
def odakyu_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseOdakyuMansionDetailFuncAsync().main(url)
    return "finish", 200

odakyuMansionDetail = odakyu_mansion_detail

@odakyu_bp.route(API_KEY_ODAKYU_KODATE_START, methods=['POST', 'GET'])
def odakyu_kodate_start():
    return ParseOdakyuKodateStartAsync().main(get_start_url('kodate'))

odakyuKodateStart = odakyu_kodate_start

@odakyu_bp.route(API_KEY_ODAKYU_KODATE_DETAIL, methods=['POST', 'GET'])
def odakyu_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseOdakyuKodateDetailFuncAsync().main(url)
    return "finish", 200

odakyuKodateDetail = odakyu_kodate_detail

@odakyu_bp.route(API_KEY_ODAKYU_TOCHI_START, methods=['POST', 'GET'])
def odakyu_tochi_start():
    return ParseOdakyuTochiStartAsync().main(get_start_url('tochi'))

odakyuTochiStart = odakyu_tochi_start

@odakyu_bp.route(API_KEY_ODAKYU_TOCHI_DETAIL, methods=['POST', 'GET'])
def odakyu_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseOdakyuTochiDetailFuncAsync().main(url)
    return "finish", 200

odakyuTochiDetail = odakyu_tochi_detail

@odakyu_bp.route(API_KEY_ODAKYU_INVESTMENT_START, methods=['POST', 'GET'])
def odakyu_investment_start():
    return ParseOdakyuInvestmentStartAsync().main("https://www.odakyu-chukai.com/invest/list/")

odakyuInvestmentStart = odakyu_investment_start

@odakyu_bp.route(API_KEY_ODAKYU_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def odakyu_investment_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseOdakyuInvestmentDetailFuncAsync().main(url)
    return "finish", 200

odakyuInvestmentDetail = odakyu_investment_detail


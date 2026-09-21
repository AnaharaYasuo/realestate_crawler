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
    url_type = 'house' if property_type == 'kodate' else ('land' if property_type == 'tochi' else property_type)
    return f"https://www.odakyu-chukai.com/{url_type}/list/"

@odakyu_bp.route(API_KEY_ODAKYU_MANSION_START, methods=['POST', 'GET'])
def odakyuMansionStart():
    return ParseOdakyuMansionStartAsync().main(get_start_url('mansion'))

@odakyu_bp.route(API_KEY_ODAKYU_MANSION_DETAIL, methods=['POST', 'GET'])
def odakyuMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseOdakyuMansionDetailFuncAsync().main(url)
    return "finish", 200

@odakyu_bp.route(API_KEY_ODAKYU_KODATE_START, methods=['POST', 'GET'])
def odakyuKodateStart():
    return ParseOdakyuKodateStartAsync().main(get_start_url('kodate'))

@odakyu_bp.route(API_KEY_ODAKYU_KODATE_DETAIL, methods=['POST', 'GET'])
def odakyuKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseOdakyuKodateDetailFuncAsync().main(url)
    return "finish", 200

@odakyu_bp.route(API_KEY_ODAKYU_TOCHI_START, methods=['POST', 'GET'])
def odakyuTochiStart():
    return ParseOdakyuTochiStartAsync().main(get_start_url('tochi'))

@odakyu_bp.route(API_KEY_ODAKYU_TOCHI_DETAIL, methods=['POST', 'GET'])
def odakyuTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseOdakyuTochiDetailFuncAsync().main(url)
    return "finish", 200

@odakyu_bp.route(API_KEY_ODAKYU_INVESTMENT_START, methods=['POST', 'GET'])
def odakyuInvestmentStart():
    return ParseOdakyuInvestmentStartAsync().main("https://www.odakyu-chukai.com/invest/list/")

@odakyu_bp.route(API_KEY_ODAKYU_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def odakyuInvestmentDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseOdakyuInvestmentDetailFuncAsync().main(url)
    return "finish", 200


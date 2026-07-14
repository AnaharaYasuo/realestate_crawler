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
    # 東京都世田谷区 (JIS: 13112) エリアをデフォルトのスタートURLとする
    return f"https://www.odakyu-chukai.com/{property_type}/list/a=13112/"

@odakyu_bp.route(API_KEY_ODAKYU_MANSION_START, methods=['POST', 'GET'])
def odakyuMansionStart():
    return ParseOdakyuMansionStartAsync().main(get_start_url('mansion'))

@odakyu_bp.route(API_KEY_ODAKYU_MANSION_DETAIL, methods=['POST', 'GET'])
def odakyuMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseOdakyuMansionDetailFuncAsync().main(url)

@odakyu_bp.route(API_KEY_ODAKYU_KODATE_START, methods=['POST', 'GET'])
def odakyuKodateStart():
    return ParseOdakyuKodateStartAsync().main(get_start_url('kodate'))

@odakyu_bp.route(API_KEY_ODAKYU_KODATE_DETAIL, methods=['POST', 'GET'])
def odakyuKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseOdakyuKodateDetailFuncAsync().main(url)

@odakyu_bp.route(API_KEY_ODAKYU_TOCHI_START, methods=['POST', 'GET'])
def odakyuTochiStart():
    return ParseOdakyuTochiStartAsync().main(get_start_url('tochi'))

@odakyu_bp.route(API_KEY_ODAKYU_TOCHI_DETAIL, methods=['POST', 'GET'])
def odakyuTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseOdakyuTochiDetailFuncAsync().main(url)

@odakyu_bp.route(API_KEY_ODAKYU_INVESTMENT_START, methods=['POST', 'GET'])
def odakyuInvestmentStart():
    return ParseOdakyuInvestmentStartAsync().main("https://www.odakyu-chukai.com/invest/list/a=13112/")

@odakyu_bp.route(API_KEY_ODAKYU_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def odakyuInvestmentDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseOdakyuInvestmentDetailFuncAsync().main(url)


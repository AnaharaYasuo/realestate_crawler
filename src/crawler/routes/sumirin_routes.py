# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_SUMIRIN_MANSION_START, API_KEY_SUMIRIN_MANSION_DETAIL,
    API_KEY_SUMIRIN_KODATE_START, API_KEY_SUMIRIN_KODATE_DETAIL,
    API_KEY_SUMIRIN_TOCHI_START, API_KEY_SUMIRIN_TOCHI_DETAIL,
    API_KEY_SUMIRIN_INVESTMENT_START, API_KEY_SUMIRIN_INVESTMENT_DETAIL
)
from package.api.sumirin import (
    ParseSumirinMansionStartAsync, ParseSumirinMansionDetailFuncAsync,
    ParseSumirinKodateStartAsync, ParseSumirinKodateDetailFuncAsync,
    ParseSumirinTochiStartAsync, ParseSumirinTochiDetailFuncAsync,
    ParseSumirinInvestmentStartAsync, ParseSumirinInvestmentDetailFuncAsync
)

sumirin_bp = Blueprint('sumirin', __name__)

@sumirin_bp.route(API_KEY_SUMIRIN_MANSION_START, methods=['POST', 'GET'])
def sumirin_mansion_start():
    return ParseSumirinMansionStartAsync().main("https://www.suminavi.com/buy/mansion/")

sumirinMansionStart = sumirin_mansion_start

@sumirin_bp.route(API_KEY_SUMIRIN_MANSION_DETAIL, methods=['POST', 'GET'])
def sumirin_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSumirinMansionDetailFuncAsync().main(url)
    return "finish", 200

sumirinMansionDetail = sumirin_mansion_detail

@sumirin_bp.route(API_KEY_SUMIRIN_KODATE_START, methods=['POST', 'GET'])
def sumirin_kodate_start():
    return ParseSumirinKodateStartAsync().main("https://www.suminavi.com/buy/house/")

sumirinKodateStart = sumirin_kodate_start

@sumirin_bp.route(API_KEY_SUMIRIN_KODATE_DETAIL, methods=['POST', 'GET'])
def sumirin_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSumirinKodateDetailFuncAsync().main(url)
    return "finish", 200

sumirinKodateDetail = sumirin_kodate_detail

@sumirin_bp.route(API_KEY_SUMIRIN_TOCHI_START, methods=['POST', 'GET'])
def sumirin_tochi_start():
    return ParseSumirinTochiStartAsync().main("https://www.suminavi.com/buy/land/")

sumirinTochiStart = sumirin_tochi_start

@sumirin_bp.route(API_KEY_SUMIRIN_TOCHI_DETAIL, methods=['POST', 'GET'])
def sumirin_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSumirinTochiDetailFuncAsync().main(url)
    return "finish", 200

sumirinTochiDetail = sumirin_tochi_detail

@sumirin_bp.route(API_KEY_SUMIRIN_INVESTMENT_START, methods=['POST', 'GET'])
def sumirin_investment_start():
    return ParseSumirinInvestmentStartAsync().main("https://www.suminavi.com/buy/estate/searchList?r_seq=9&ec_cd=3&s_mode=1")

sumirinInvestmentStart = sumirin_investment_start

@sumirin_bp.route(API_KEY_SUMIRIN_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def sumirin_investment_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSumirinInvestmentDetailFuncAsync().main(url)
    return "finish", 200

sumirinInvestmentDetail = sumirin_investment_detail

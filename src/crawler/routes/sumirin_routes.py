# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
import logging
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
def sumirinMansionStart():
    return ParseSumirinMansionStartAsync().main("https://www.suminavi.com/buy/estate/searchList?r_seq=1&ec_cd=1&ed_cd=01&p_cd=13&c_cd=13111&s_mode=1")

@sumirin_bp.route(API_KEY_SUMIRIN_MANSION_DETAIL, methods=['POST', 'GET'])
def sumirinMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSumirinMansionDetailFuncAsync().main(url)

@sumirin_bp.route(API_KEY_SUMIRIN_KODATE_START, methods=['POST', 'GET'])
def sumirinKodateStart():
    return ParseSumirinKodateStartAsync().main("https://www.suminavi.com/buy/estate/searchList?r_seq=1&ec_cd=1&ed_cd=02&p_cd=13&c_cd=13111&s_mode=1")

@sumirin_bp.route(API_KEY_SUMIRIN_KODATE_DETAIL, methods=['POST', 'GET'])
def sumirinKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSumirinKodateDetailFuncAsync().main(url)

@sumirin_bp.route(API_KEY_SUMIRIN_TOCHI_START, methods=['POST', 'GET'])
def sumirinTochiStart():
    return ParseSumirinTochiStartAsync().main("https://www.suminavi.com/buy/estate/searchList?r_seq=1&ec_cd=1&ed_cd=03&p_cd=13&c_cd=13111&s_mode=1")

@sumirin_bp.route(API_KEY_SUMIRIN_TOCHI_DETAIL, methods=['POST', 'GET'])
def sumirinTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSumirinTochiDetailFuncAsync().main(url)

@sumirin_bp.route(API_KEY_SUMIRIN_INVESTMENT_START, methods=['POST', 'GET'])
def sumirinInvestmentStart():
    return ParseSumirinInvestmentStartAsync().main("https://www.suminavi.com/buy/estate/searchList?r_seq=1&ec_cd=3&p_cd=13&c_cd=13111&s_mode=1")

@sumirin_bp.route(API_KEY_SUMIRIN_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def sumirinInvestmentDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSumirinInvestmentDetailFuncAsync().main(url)

# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_SUMAI1_MANSION_START, API_KEY_SUMAI1_MANSION_DETAIL,
    API_KEY_SUMAI1_KODATE_START, API_KEY_SUMAI1_KODATE_DETAIL,
    API_KEY_SUMAI1_TOCHI_START, API_KEY_SUMAI1_TOCHI_DETAIL,
    API_KEY_SUMAI1_INVESTMENT_START, API_KEY_SUMAI1_INVESTMENT_DETAIL
)
from package.api.sumai1 import (
    ParseSumai1MansionStartAsync, ParseSumai1MansionDetailFuncAsync,
    ParseSumai1KodateStartAsync, ParseSumai1KodateDetailFuncAsync,
    ParseSumai1TochiStartAsync, ParseSumai1TochiDetailFuncAsync,
    ParseSumai1InvestmentStartAsync, ParseSumai1InvestmentDetailFuncAsync
)

sumai1_bp = Blueprint('sumai1', __name__)

@sumai1_bp.route(API_KEY_SUMAI1_MANSION_START, methods=['POST', 'GET'])
def sumai1_mansion_start():
    return ParseSumai1MansionStartAsync().main("https://www.sumai1.com/buyers/mansion/tod_13/")

sumai1MansionStart = sumai1_mansion_start

@sumai1_bp.route(API_KEY_SUMAI1_MANSION_DETAIL, methods=['POST', 'GET'])
def sumai1_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSumai1MansionDetailFuncAsync().main(url)
    return "finish", 200

sumai1MansionDetail = sumai1_mansion_detail

@sumai1_bp.route(API_KEY_SUMAI1_KODATE_START, methods=['POST', 'GET'])
def sumai1_kodate_start():
    return ParseSumai1KodateStartAsync().main("https://www.sumai1.com/buyers/kodate/tod_13/")

sumai1KodateStart = sumai1_kodate_start

@sumai1_bp.route(API_KEY_SUMAI1_KODATE_DETAIL, methods=['POST', 'GET'])
def sumai1_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSumai1KodateDetailFuncAsync().main(url)
    return "finish", 200

sumai1KodateDetail = sumai1_kodate_detail

@sumai1_bp.route(API_KEY_SUMAI1_TOCHI_START, methods=['POST', 'GET'])
def sumai1_tochi_start():
    return ParseSumai1TochiStartAsync().main("https://www.sumai1.com/buyers/tochi/tod_13/")

sumai1TochiStart = sumai1_tochi_start

@sumai1_bp.route(API_KEY_SUMAI1_TOCHI_DETAIL, methods=['POST', 'GET'])
def sumai1_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSumai1TochiDetailFuncAsync().main(url)
    return "finish", 200

sumai1TochiDetail = sumai1_tochi_detail

@sumai1_bp.route(API_KEY_SUMAI1_INVESTMENT_START, methods=['POST', 'GET'])
def sumai1_investment_start():
    return ParseSumai1InvestmentStartAsync().main("https://www.sumai1.com/buyers/investor/tod_13/bukshu_2/")

sumai1InvestmentStart = sumai1_investment_start

@sumai1_bp.route(API_KEY_SUMAI1_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def sumai1_investment_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSumai1InvestmentDetailFuncAsync().main(url)
    return "finish", 200

sumai1InvestmentDetail = sumai1_investment_detail


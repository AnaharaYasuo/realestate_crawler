# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
import logging
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
def sumai1MansionStart():
    return ParseSumai1MansionStartAsync().main("https://www.sumai1.com/buyers/mansion/tod_13/")

@sumai1_bp.route(API_KEY_SUMAI1_MANSION_DETAIL, methods=['POST', 'GET'])
def sumai1MansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSumai1MansionDetailFuncAsync().main(url)

@sumai1_bp.route(API_KEY_SUMAI1_KODATE_START, methods=['POST', 'GET'])
def sumai1KodateStart():
    return ParseSumai1KodateStartAsync().main("https://www.sumai1.com/buyers/kodate/tod_13/")

@sumai1_bp.route(API_KEY_SUMAI1_KODATE_DETAIL, methods=['POST', 'GET'])
def sumai1KodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSumai1KodateDetailFuncAsync().main(url)

@sumai1_bp.route(API_KEY_SUMAI1_TOCHI_START, methods=['POST', 'GET'])
def sumai1TochiStart():
    return ParseSumai1TochiStartAsync().main("https://www.sumai1.com/buyers/tochi/tod_13/")

@sumai1_bp.route(API_KEY_SUMAI1_TOCHI_DETAIL, methods=['POST', 'GET'])
def sumai1TochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSumai1TochiDetailFuncAsync().main(url)

@sumai1_bp.route(API_KEY_SUMAI1_INVESTMENT_START, methods=['POST', 'GET'])
def sumai1InvestmentStart():
    return ParseSumai1InvestmentStartAsync().main("https://www.sumai1.com/buyers/investor/tod_13/bukshu_2/")

@sumai1_bp.route(API_KEY_SUMAI1_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def sumai1InvestmentDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSumai1InvestmentDetailFuncAsync().main(url)


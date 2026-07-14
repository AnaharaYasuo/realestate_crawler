# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_ATHOME_INVEST_APARTMENT_START, API_KEY_ATHOME_INVEST_APARTMENT_DETAIL,
    API_KEY_ATHOME_MANSION_START, API_KEY_ATHOME_MANSION_DETAIL,
    API_KEY_ATHOME_KODATE_START, API_KEY_ATHOME_KODATE_DETAIL,
    API_KEY_ATHOME_TOCHI_START, API_KEY_ATHOME_TOCHI_DETAIL
)
from package.api.athome import (
    ParseAthomeMansionStartAsync, ParseAthomeMansionDetailFuncAsync,
    ParseAthomeKodateStartAsync, ParseAthomeKodateDetailFuncAsync,
    ParseAthomeInvestApartmentStartAsync, ParseAthomeInvestApartmentDetailFuncAsync,
    ParseAthomeTochiStartAsync, ParseAthomeTochiDetailFuncAsync
)

athome_bp = Blueprint('athome', __name__)

@athome_bp.route(API_KEY_ATHOME_MANSION_START, methods=['POST', 'GET'])
def athomeMansionStart():
    return ParseAthomeMansionStartAsync().main("https://www.athome.co.jp/mansion/")

@athome_bp.route(API_KEY_ATHOME_MANSION_DETAIL, methods=['POST', 'GET'])
def athomeMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseAthomeMansionDetailFuncAsync().main(url)

@athome_bp.route(API_KEY_ATHOME_KODATE_START, methods=['POST', 'GET'])
def athomeKodateStart():
    return ParseAthomeKodateStartAsync().main("https://www.athome.co.jp/kodate/")

@athome_bp.route(API_KEY_ATHOME_KODATE_DETAIL, methods=['POST', 'GET'])
def athomeKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseAthomeKodateDetailFuncAsync().main(url)

@athome_bp.route(API_KEY_ATHOME_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def athomeInvestApartmentStart():
    return ParseAthomeInvestApartmentStartAsync().main("https://www.athome.co.jp/toushi/")

@athome_bp.route(API_KEY_ATHOME_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def athomeInvestApartmentDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseAthomeInvestApartmentDetailFuncAsync().main(url)

@athome_bp.route(API_KEY_ATHOME_TOCHI_START, methods=['POST', 'GET'])
def athomeTochiStart():
    return ParseAthomeTochiStartAsync().main("https://www.athome.co.jp/tochi/")

@athome_bp.route(API_KEY_ATHOME_TOCHI_DETAIL, methods=['POST', 'GET'])
def athomeTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseAthomeTochiDetailFuncAsync().main(url)


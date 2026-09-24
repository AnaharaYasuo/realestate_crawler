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
def athome_mansion_start():
    return ParseAthomeMansionStartAsync().main("https://www.athome.co.jp/mansion/chuko/tokyo/city/")

athomeMansionStart = athome_mansion_start

@athome_bp.route(API_KEY_ATHOME_MANSION_DETAIL, methods=['POST', 'GET'])
def athome_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseAthomeMansionDetailFuncAsync().main(url)
    return "finish", 200

athomeMansionDetail = athome_mansion_detail

@athome_bp.route(API_KEY_ATHOME_KODATE_START, methods=['POST', 'GET'])
def athome_kodate_start():
    return ParseAthomeKodateStartAsync().main("https://www.athome.co.jp/kodate/chuko/tokyo/city/")

athomeKodateStart = athome_kodate_start

@athome_bp.route(API_KEY_ATHOME_KODATE_DETAIL, methods=['POST', 'GET'])
def athome_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseAthomeKodateDetailFuncAsync().main(url)
    return "finish", 200

athomeKodateDetail = athome_kodate_detail

@athome_bp.route(API_KEY_ATHOME_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def athome_invest_apartment_start():
    return ParseAthomeInvestApartmentStartAsync().main("https://www.athome.co.jp/buy_other/tokyo/city/")

athomeInvestApartmentStart = athome_invest_apartment_start

@athome_bp.route(API_KEY_ATHOME_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def athome_invest_apartment_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseAthomeInvestApartmentDetailFuncAsync().main(url)
    return "finish", 200

athomeInvestApartmentDetail = athome_invest_apartment_detail

@athome_bp.route(API_KEY_ATHOME_TOCHI_START, methods=['POST', 'GET'])
def athome_tochi_start():
    return ParseAthomeTochiStartAsync().main("https://www.athome.co.jp/tochi/tokyo/city/")

athomeTochiStart = athome_tochi_start

@athome_bp.route(API_KEY_ATHOME_TOCHI_DETAIL, methods=['POST', 'GET'])
def athome_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseAthomeTochiDetailFuncAsync().main(url)
    return "finish", 200

athomeTochiDetail = athome_tochi_detail



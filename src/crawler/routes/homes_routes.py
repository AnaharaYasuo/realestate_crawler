# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_HOMES_INVEST_APARTMENT_START, API_KEY_HOMES_INVEST_APARTMENT_DETAIL,
    API_KEY_HOMES_MANSION_START, API_KEY_HOMES_MANSION_DETAIL,
    API_KEY_HOMES_KODATE_START, API_KEY_HOMES_KODATE_DETAIL,
    API_KEY_HOMES_TOCHI_START, API_KEY_HOMES_TOCHI_DETAIL
)
from package.api.homes import (
    ParseHomesMansionStartAsync, ParseHomesMansionDetailFuncAsync,
    ParseHomesKodateStartAsync, ParseHomesKodateDetailFuncAsync,
    ParseHomesInvestApartmentStartAsync, ParseHomesInvestApartmentDetailFuncAsync,
    ParseHomesTochiStartAsync, ParseHomesTochiDetailFuncAsync
)

homes_bp = Blueprint('homes', __name__)

@homes_bp.route(API_KEY_HOMES_MANSION_START, methods=['POST', 'GET'])
def homes_mansion_start():
    return ParseHomesMansionStartAsync().main("https://toushi.homes.co.jp/bukkensearch/?tbg[]=2")

homesMansionStart = homes_mansion_start

@homes_bp.route(API_KEY_HOMES_MANSION_DETAIL, methods=['POST', 'GET'])
def homes_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseHomesMansionDetailFuncAsync().main(url)
    return "finish", 200

homesMansionDetail = homes_mansion_detail

@homes_bp.route(API_KEY_HOMES_KODATE_START, methods=['POST', 'GET'])
def homes_kodate_start():
    return ParseHomesKodateStartAsync().main("https://toushi.homes.co.jp/bukkensearch/?tbg[]=4")

homesKodateStart = homes_kodate_start

@homes_bp.route(API_KEY_HOMES_KODATE_DETAIL, methods=['POST', 'GET'])
def homes_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseHomesKodateDetailFuncAsync().main(url)
    return "finish", 200

homesKodateDetail = homes_kodate_detail

@homes_bp.route(API_KEY_HOMES_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def homes_invest_apartment_start():
    return ParseHomesInvestApartmentStartAsync().main("https://toushi.homes.co.jp/bukkensearch/?tbg[]=1")

homesInvestApartmentStart = homes_invest_apartment_start

@homes_bp.route(API_KEY_HOMES_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def homes_invest_apartment_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseHomesInvestApartmentDetailFuncAsync().main(url)
    return "finish", 200

homesInvestApartmentDetail = homes_invest_apartment_detail

@homes_bp.route(API_KEY_HOMES_TOCHI_START, methods=['POST', 'GET'])
def homes_tochi_start():
    return ParseHomesTochiStartAsync().main("https://toushi.homes.co.jp/bukkensearch/?tbg[]=5")

homesTochiStart = homes_tochi_start

@homes_bp.route(API_KEY_HOMES_TOCHI_DETAIL, methods=['POST', 'GET'])
def homes_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseHomesTochiDetailFuncAsync().main(url)
    return "finish", 200

homesTochiDetail = homes_tochi_detail



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
def homesMansionStart():
    return ParseHomesMansionStartAsync().main("https://toushi.homes.co.jp/bukkensearch/tbg[]=2/")

@homes_bp.route(API_KEY_HOMES_MANSION_DETAIL, methods=['POST', 'GET'])
def homesMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseHomesMansionDetailFuncAsync().main(url)

@homes_bp.route(API_KEY_HOMES_KODATE_START, methods=['POST', 'GET'])
def homesKodateStart():
    return ParseHomesKodateStartAsync().main("https://toushi.homes.co.jp/bukkensearch/tbg[]=4/")

@homes_bp.route(API_KEY_HOMES_KODATE_DETAIL, methods=['POST', 'GET'])
def homesKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseHomesKodateDetailFuncAsync().main(url)

@homes_bp.route(API_KEY_HOMES_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def homesInvestApartmentStart():
    return ParseHomesInvestApartmentStartAsync().main("https://toushi.homes.co.jp/bukkensearch/tbg[]=1/")

@homes_bp.route(API_KEY_HOMES_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def homesInvestApartmentDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseHomesInvestApartmentDetailFuncAsync().main(url)

@homes_bp.route(API_KEY_HOMES_TOCHI_START, methods=['POST', 'GET'])
def homesTochiStart():
    return ParseHomesTochiStartAsync().main("https://toushi.homes.co.jp/bukkensearch/tbg[]=5/")

@homes_bp.route(API_KEY_HOMES_TOCHI_DETAIL, methods=['POST', 'GET'])
def homesTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseHomesTochiDetailFuncAsync().main(url)


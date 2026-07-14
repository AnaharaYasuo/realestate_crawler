# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
import logging
from package.api.api import (
    API_KEY_MIZUHO_MANSION_START, API_KEY_MIZUHO_MANSION_DETAIL,
    API_KEY_MIZUHO_KODATE_START, API_KEY_MIZUHO_KODATE_DETAIL,
    API_KEY_MIZUHO_TOCHI_START, API_KEY_MIZUHO_TOCHI_DETAIL,
    API_KEY_MIZUHO_INVESTMENT_START, API_KEY_MIZUHO_INVESTMENT_DETAIL
)
from package.api.mizuho import (
    ParseMizuhoMansionStartAsync, ParseMizuhoMansionDetailFuncAsync,
    ParseMizuhoKodateStartAsync, ParseMizuhoKodateDetailFuncAsync,
    ParseMizuhoTochiStartAsync, ParseMizuhoTochiDetailFuncAsync,
    ParseMizuhoInvestmentStartAsync, ParseMizuhoInvestmentDetailFuncAsync
)

mizuho_bp = Blueprint('mizuho', __name__)

# 東京都中央区 (pref_13 / city_13102) をデフォルトの巡回スタート地点にする
def get_start_url(property_type='Mansion'):
    return f"https://www.mizuho-re.co.jp/buyers/search/area/type_{property_type}/pref_13/city_13102/list/"

@mizuho_bp.route(API_KEY_MIZUHO_MANSION_START, methods=['POST', 'GET'])
def mizuhoMansionStart():
    return ParseMizuhoMansionStartAsync().main(get_start_url('Mansion'))

@mizuho_bp.route(API_KEY_MIZUHO_MANSION_DETAIL, methods=['POST', 'GET'])
def mizuhoMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseMizuhoMansionDetailFuncAsync().main(url)

@mizuho_bp.route(API_KEY_MIZUHO_KODATE_START, methods=['POST', 'GET'])
def mizuhoKodateStart():
    return ParseMizuhoKodateStartAsync().main(get_start_url('House'))

@mizuho_bp.route(API_KEY_MIZUHO_KODATE_DETAIL, methods=['POST', 'GET'])
def mizuhoKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseMizuhoKodateDetailFuncAsync().main(url)

@mizuho_bp.route(API_KEY_MIZUHO_TOCHI_START, methods=['POST', 'GET'])
def mizuhoTochiStart():
    return ParseMizuhoTochiStartAsync().main(get_start_url('Land'))

@mizuho_bp.route(API_KEY_MIZUHO_TOCHI_DETAIL, methods=['POST', 'GET'])
def mizuhoTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseMizuhoTochiDetailFuncAsync().main(url)

@mizuho_bp.route(API_KEY_MIZUHO_INVESTMENT_START, methods=['POST', 'GET'])
def mizuhoInvestmentStart():
    return ParseMizuhoInvestmentStartAsync().main("https://www.mizuho-re.co.jp/investors/search/area/all_apartment-building-dormitory-office-store-warehouse-factory-land-other/pref_13/list/")

@mizuho_bp.route(API_KEY_MIZUHO_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def mizuhoInvestmentDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseMizuhoInvestmentDetailFuncAsync().main(url)


# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_KEIKYU_MANSION_START, API_KEY_KEIKYU_MANSION_DETAIL,
    API_KEY_KEIKYU_KODATE_START, API_KEY_KEIKYU_KODATE_DETAIL,
    API_KEY_KEIKYU_TOCHI_START, API_KEY_KEIKYU_TOCHI_DETAIL
)
from package.api.keikyu import (
    ParseKeikyuMansionStartAsync, ParseKeikyuMansionDetailFuncAsync,
    ParseKeikyuStartAsync, ParseKeikyuKodateDetailFuncAsync,
    ParseKeikyuTochiStartAsync, ParseKeikyuTochiDetailFuncAsync
)

keikyu_bp = Blueprint('keikyu', __name__)

@keikyu_bp.route(API_KEY_KEIKYU_MANSION_START, methods=['POST', 'GET'])
def keikyuMansionStart():
    # 東京都の中古マンション
    return ParseKeikyuMansionStartAsync().main("https://www.keikyu-sumai.com/contents/code/search_result?pref_page=13&sltype=1&r_type=3&pref=13&all_pref=1&change_r_type=&sltype=1&mb_myareas=&mb_myareasC=&pref_check%5B%5D=13&r_type=3&mb_cost_min=&mb_cost_max=&inv_rate=&mb_land_min=&mb_land_max=&mb_floor_min=&mb_floor_max=&new_arrivals=&by=area&mode=list")

@keikyu_bp.route(API_KEY_KEIKYU_MANSION_DETAIL, methods=['POST', 'GET'])
def keikyuMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseKeikyuMansionDetailFuncAsync().main(url)

@keikyu_bp.route(API_KEY_KEIKYU_KODATE_START, methods=['POST', 'GET'])
def keikyuKodateStart():
    # 東京都の中古戸建
    return ParseKeikyuStartAsync().main("https://www.keikyu-sumai.com/contents/code/search_result?pref_page=13&sltype=1&r_type=2&pref=13&all_pref=1&change_r_type=&sltype=1&mb_myareas=&mb_myareasC=&pref_check%5B%5D=13&pl_13%5B%5D=13111&r_type=2&mb_cost_min=&mb_cost_max=&inv_rate=&mb_land_min=&mb_land_max=&mb_floor_min=&mb_floor_max=&new_arrivals=&by=area&mode=list")

@keikyu_bp.route(API_KEY_KEIKYU_KODATE_DETAIL, methods=['POST', 'GET'])
def keikyuKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseKeikyuKodateDetailFuncAsync().main(url)

@keikyu_bp.route(API_KEY_KEIKYU_TOCHI_START, methods=['POST', 'GET'])
def keikyuTochiStart():
    # 東京都の土地
    return ParseKeikyuTochiStartAsync().main("https://www.keikyu-sumai.com/contents/code/search_result?pref_page=13&sltype=1&r_type=1&pref=13&all_pref=1&change_r_type=&sltype=1&mb_myareas=&mb_myareasC=&pref_check%5B%5D=13&pl_13%5B%5D=13109&pl_13%5B%5D=13111&pl_13%5B%5D=13209&r_type=1&mb_cost_min=&mb_cost_max=&inv_rate=&mb_land_min=&mb_land_max=&mb_floor_min=&mb_floor_max=&new_arrivals=&by=area&mode=list")

@keikyu_bp.route(API_KEY_KEIKYU_TOCHI_DETAIL, methods=['POST', 'GET'])
def keikyuTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseKeikyuTochiDetailFuncAsync().main(url)

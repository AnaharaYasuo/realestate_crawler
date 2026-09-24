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
    ParseKeikyuKodateStartAsync, ParseKeikyuKodateDetailFuncAsync,
    ParseKeikyuTochiStartAsync, ParseKeikyuTochiDetailFuncAsync
)

keikyu_bp = Blueprint('keikyu', __name__)

@keikyu_bp.route(API_KEY_KEIKYU_MANSION_START, methods=['POST', 'GET'])
def keikyu_mansion_start():
    # 東京都の中古マンション
    return ParseKeikyuMansionStartAsync().main("https://www.keikyu-sumai.com/contents/code/search_result?pref_page=13&sltype=1&r_type=3&pref=13&all_pref=1&change_r_type=&sltype=1&mb_myareas=&mb_myareasC=&pref_check%5B%5D=13&r_type=3&mb_cost_min=&mb_cost_max=&inv_rate=&mb_land_min=&mb_land_max=&mb_floor_min=&mb_floor_max=&new_arrivals=&by=area&mode=list")

keikyuMansionStart = keikyu_mansion_start

@keikyu_bp.route(API_KEY_KEIKYU_MANSION_DETAIL, methods=['POST', 'GET'])
def keikyu_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseKeikyuMansionDetailFuncAsync().main(url)
    return "finish", 200

keikyuMansionDetail = keikyu_mansion_detail

@keikyu_bp.route(API_KEY_KEIKYU_KODATE_START, methods=['POST', 'GET'])
def keikyu_kodate_start():
    # 東京都の中古戸建
    return ParseKeikyuKodateStartAsync().main("https://www.keikyu-sumai.com/contents/code/search_result?pref_page=13&sltype=1&r_type=2&pref=13&all_pref=1&change_r_type=&sltype=1&mb_myareas=&mb_myareasC=&pref_check%5B%5D=13&pl_13%5B%5D=13111&r_type=2&mb_cost_min=&mb_cost_max=&inv_rate=&mb_land_min=&mb_land_max=&mb_floor_min=&mb_floor_max=&new_arrivals=&by=area&mode=list")

keikyuKodateStart = keikyu_kodate_start

@keikyu_bp.route(API_KEY_KEIKYU_KODATE_DETAIL, methods=['POST', 'GET'])
def keikyu_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseKeikyuKodateDetailFuncAsync().main(url)
    return "finish", 200

keikyuKodateDetail = keikyu_kodate_detail

@keikyu_bp.route(API_KEY_KEIKYU_TOCHI_START, methods=['POST', 'GET'])
def keikyu_tochi_start():
    # 東京都の土地
    return ParseKeikyuTochiStartAsync().main("https://www.keikyu-sumai.com/contents/code/search_result?pref_page=13&sltype=1&r_type=1&pref=13&all_pref=1&change_r_type=&sltype=1&mb_myareas=&mb_myareasC=&pref_check%5B%5D=13&pl_13%5B%5D=13109&pl_13%5B%5D=13111&pl_13%5B%5D=13209&r_type=1&mb_cost_min=&mb_cost_max=&inv_rate=&mb_land_min=&mb_land_max=&mb_floor_min=&mb_floor_max=&new_arrivals=&by=area&mode=list")

keikyuTochiStart = keikyu_tochi_start

@keikyu_bp.route(API_KEY_KEIKYU_TOCHI_DETAIL, methods=['POST', 'GET'])
def keikyu_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseKeikyuTochiDetailFuncAsync().main(url)
    return "finish", 200

keikyuTochiDetail = keikyu_tochi_detail

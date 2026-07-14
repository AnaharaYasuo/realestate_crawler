# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_KEISEI_MANSION_START, API_KEY_KEISEI_MANSION_DETAIL,
    API_KEY_KEISEI_KODATE_START, API_KEY_KEISEI_KODATE_DETAIL,
    API_KEY_KEISEI_TOCHI_START, API_KEY_KEISEI_TOCHI_DETAIL
)
from package.api.keisei import (
    ParseKeiseiMansionStartAsync, ParseKeiseiMansionDetailFuncAsync,
    ParseKeiseiKodateStartAsync, ParseKeiseiKodateDetailFuncAsync,
    ParseKeiseiTochiStartAsync, ParseKeiseiTochiDetailFuncAsync
)

keisei_bp = Blueprint('keisei', __name__)

@keisei_bp.route(API_KEY_KEISEI_MANSION_START, methods=['POST', 'GET'])
def keiseiMansionStart():
    # 東京都の中古マンション（ダイレクト検索結果）
    return ParseKeiseiMansionStartAsync().main("https://www.keisei-land.co.jp/contents/code/search_result?mode=none&all_pref=1&pref_check%5B%5D=13&change_r_type=&mb_myareas=&mb_myareasC=&pref_check%5B%5D=13&pl_13%5B%5D=13106&pl_13%5B%5D=13107&pl_13%5B%5D=13121&pl_13%5B%5D=13122&r_type=3&mb_cost_min=&mb_cost_max=&inv_rate=&mb_land_min=&mb_land_max=&mb_floor_min=&mb_floor_max=&new_arrivals=&by=area&mode=list")

@keisei_bp.route(API_KEY_KEISEI_MANSION_DETAIL, methods=['POST', 'GET'])
def keiseiMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseKeiseiMansionDetailFuncAsync().main(url)

@keisei_bp.route(API_KEY_KEISEI_KODATE_START, methods=['POST', 'GET'])
def keiseiKodateStart():
    # 東京都の中古戸建（ダイレクト検索結果）
    return ParseKeiseiKodateStartAsync().main("https://www.keisei-land.co.jp/contents/code/search_result?mode=none&all_pref=1&pref_check%5B%5D=13&change_r_type=&mb_myareas=&mb_myareasC=&pref_check%5B%5D=13&pl_13%5B%5D=13106&pl_13%5B%5D=13107&pl_13%5B%5D=13121&pl_13%5B%5D=13122&r_type=2&mb_cost_min=&mb_cost_max=&inv_rate=&mb_land_min=&mb_land_max=&mb_floor_min=&mb_floor_max=&new_arrivals=&by=area&mode=list")

@keisei_bp.route(API_KEY_KEISEI_KODATE_DETAIL, methods=['POST', 'GET'])
def keiseiKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseKeiseiKodateDetailFuncAsync().main(url)

@keisei_bp.route(API_KEY_KEISEI_TOCHI_START, methods=['POST', 'GET'])
def keiseiTochiStart():
    # 東京都の土地（ダイレクト検索結果）
    return ParseKeiseiTochiStartAsync().main("https://www.keisei-land.co.jp/contents/code/search_result?mode=none&all_pref=1&pref_check%5B%5D=13&change_r_type=&mb_myareas=&mb_myareasC=&pref_check%5B%5D=13&pl_13%5B%5D=13106&pl_13%5B%5D=13107&pl_13%5B%5D=13121&pl_13%5B%5D=13122&r_type=1&mb_cost_min=&mb_cost_max=&inv_rate=&mb_land_min=&mb_land_max=&mb_floor_min=&mb_floor_max=&new_arrivals=&by=area&mode=list")

@keisei_bp.route(API_KEY_KEISEI_TOCHI_DETAIL, methods=['POST', 'GET'])
def keiseiTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseKeiseiTochiDetailFuncAsync().main(url)

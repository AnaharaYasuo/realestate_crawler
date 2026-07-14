# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_DAIKYO_MANSION_START, API_KEY_DAIKYO_MANSION_DETAIL,
    API_KEY_DAIKYO_KODATE_START, API_KEY_DAIKYO_KODATE_DETAIL,
    API_KEY_DAIKYO_TOCHI_START, API_KEY_DAIKYO_TOCHI_DETAIL
)
from package.api.daikyo import (
    ParseDaikyoMansionStartAsync, ParseDaikyoMansionDetailFuncAsync,
    ParseDaikyoKodateStartAsync, ParseDaikyoKodateDetailFuncAsync,
    ParseDaikyoTochiStartAsync, ParseDaikyoTochiDetailFuncAsync
)

daikyo_bp = Blueprint('daikyo', __name__)

@daikyo_bp.route(API_KEY_DAIKYO_MANSION_START, methods=['POST', 'GET'])
def daikyoMansionStart():
    # 東京都の中古マンション（エリア別一覧）
    return ParseDaikyoMansionStartAsync().main("https://www.daikyo-anabuki.co.jp/buy/mansion/p13/")

@daikyo_bp.route(API_KEY_DAIKYO_MANSION_DETAIL, methods=['POST', 'GET'])
def daikyoMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseDaikyoMansionDetailFuncAsync().main(url)

@daikyo_bp.route(API_KEY_DAIKYO_KODATE_START, methods=['POST', 'GET'])
def daikyoKodateStart():
    # 東京都の中古戸建（エリア別一覧）
    return ParseDaikyoKodateStartAsync().main("https://www.daikyo-anabuki.co.jp/buy/kodate/p13/")

@daikyo_bp.route(API_KEY_DAIKYO_KODATE_DETAIL, methods=['POST', 'GET'])
def daikyoKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseDaikyoKodateDetailFuncAsync().main(url)

@daikyo_bp.route(API_KEY_DAIKYO_TOCHI_START, methods=['POST', 'GET'])
def daikyoTochiStart():
    # 東京都の土地（エリア別一覧）
    return ParseDaikyoTochiStartAsync().main("https://www.daikyo-anabuki.co.jp/buy/tochi/p13/")

@daikyo_bp.route(API_KEY_DAIKYO_TOCHI_DETAIL, methods=['POST', 'GET'])
def daikyoTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseDaikyoTochiDetailFuncAsync().main(url)

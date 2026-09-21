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
    # 全国の中古マンション
    return ParseDaikyoMansionStartAsync().main("https://www.daikyo-anabuki.co.jp/buy/mansion/")

@daikyo_bp.route(API_KEY_DAIKYO_MANSION_DETAIL, methods=['POST', 'GET'])
def daikyoMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseDaikyoMansionDetailFuncAsync().main(url)
    return "finish", 200

@daikyo_bp.route(API_KEY_DAIKYO_KODATE_START, methods=['POST', 'GET'])
def daikyoKodateStart():
    # 全国の中古戸建
    return ParseDaikyoKodateStartAsync().main("https://www.daikyo-anabuki.co.jp/buy/house/")

@daikyo_bp.route(API_KEY_DAIKYO_KODATE_DETAIL, methods=['POST', 'GET'])
def daikyoKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseDaikyoKodateDetailFuncAsync().main(url)
    return "finish", 200

@daikyo_bp.route(API_KEY_DAIKYO_TOCHI_START, methods=['POST', 'GET'])
def daikyoTochiStart():
    # 全国の土地
    return ParseDaikyoTochiStartAsync().main("https://www.daikyo-anabuki.co.jp/buy/land/")


@daikyo_bp.route(API_KEY_DAIKYO_TOCHI_DETAIL, methods=['POST', 'GET'])
def daikyoTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseDaikyoTochiDetailFuncAsync().main(url)
    return "finish", 200

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
def daikyo_mansion_start():
    # 全国の中古マンション
    return ParseDaikyoMansionStartAsync().main("https://www.daikyo-anabuki.co.jp/buy/mansion/")

daikyoMansionStart = daikyo_mansion_start

@daikyo_bp.route(API_KEY_DAIKYO_MANSION_DETAIL, methods=['POST', 'GET'])
def daikyo_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseDaikyoMansionDetailFuncAsync().main(url)
    return "finish", 200

daikyoMansionDetail = daikyo_mansion_detail

@daikyo_bp.route(API_KEY_DAIKYO_KODATE_START, methods=['POST', 'GET'])
def daikyo_kodate_start():
    # 全国の中古戸建
    return ParseDaikyoKodateStartAsync().main("https://www.daikyo-anabuki.co.jp/buy/house/")

daikyoKodateStart = daikyo_kodate_start

@daikyo_bp.route(API_KEY_DAIKYO_KODATE_DETAIL, methods=['POST', 'GET'])
def daikyo_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseDaikyoKodateDetailFuncAsync().main(url)
    return "finish", 200

daikyoKodateDetail = daikyo_kodate_detail

@daikyo_bp.route(API_KEY_DAIKYO_TOCHI_START, methods=['POST', 'GET'])
def daikyo_tochi_start():
    # 全国の土地
    return ParseDaikyoTochiStartAsync().main("https://www.daikyo-anabuki.co.jp/buy/land/")

daikyoTochiStart = daikyo_tochi_start


@daikyo_bp.route(API_KEY_DAIKYO_TOCHI_DETAIL, methods=['POST', 'GET'])
def daikyo_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseDaikyoTochiDetailFuncAsync().main(url)
    return "finish", 200

daikyoTochiDetail = daikyo_tochi_detail

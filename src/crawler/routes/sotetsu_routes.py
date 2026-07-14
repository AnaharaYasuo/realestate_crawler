# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_SOTETSU_MANSION_START, API_KEY_SOTETSU_MANSION_DETAIL,
    API_KEY_SOTETSU_KODATE_START, API_KEY_SOTETSU_KODATE_DETAIL,
    API_KEY_SOTETSU_TOCHI_START, API_KEY_SOTETSU_TOCHI_DETAIL
)
from package.api.sotetsu import (
    ParseSotetsuMansionStartAsync, ParseSotetsuMansionDetailFuncAsync,
    ParseSotetsuKodateStartAsync, ParseSotetsuKodateDetailFuncAsync,
    ParseSotetsuTochiStartAsync, ParseSotetsuTochiDetailFuncAsync
)

sotetsu_bp = Blueprint('sotetsu', __name__)

@sotetsu_bp.route(API_KEY_SOTETSU_MANSION_START, methods=['POST', 'GET'])
def sotetsuMansionStart():
    # 東京都の中古マンション（相鉄沿線など）
    return ParseSotetsuMansionStartAsync().main("https://www.sotetsu-re.co.jp/buy/res/area/?a5%5B%5D=13108&a5%5B%5D=13116&a5%5B%5D=13209&t%5B%5D=1")

@sotetsu_bp.route(API_KEY_SOTETSU_MANSION_DETAIL, methods=['POST', 'GET'])
def sotetsuMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSotetsuMansionDetailFuncAsync().main(url)

@sotetsu_bp.route(API_KEY_SOTETSU_KODATE_START, methods=['POST', 'GET'])
def sotetsuKodateStart():
    # 東京都の中古戸建
    return ParseSotetsuKodateStartAsync().main("https://www.sotetsu-re.co.jp/buy/res/area/1?t%5B%5D=2&t%5B%5D=3&a5%5B%5D=13209&s=new&o=desc")

@sotetsu_bp.route(API_KEY_SOTETSU_KODATE_DETAIL, methods=['POST', 'GET'])
def sotetsuKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSotetsuKodateDetailFuncAsync().main(url)

@sotetsu_bp.route(API_KEY_SOTETSU_TOCHI_START, methods=['POST', 'GET'])
def sotetsuTochiStart():
    # 東京都の土地
    return ParseSotetsuTochiStartAsync().main("https://www.sotetsu-re.co.jp/buy/res/area/1?t%5B%5D=4&a5%5B%5D=13209&s=new&o=desc")

@sotetsu_bp.route(API_KEY_SOTETSU_TOCHI_DETAIL, methods=['POST', 'GET'])
def sotetsuTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSotetsuTochiDetailFuncAsync().main(url)

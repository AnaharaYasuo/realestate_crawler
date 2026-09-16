# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_HEIM_MANSION_START, API_KEY_HEIM_MANSION_DETAIL,
    API_KEY_HEIM_KODATE_START, API_KEY_HEIM_KODATE_DETAIL,
    API_KEY_HEIM_TOCHI_START, API_KEY_HEIM_TOCHI_DETAIL
)
from package.api.heim import (
    ParseHeimMansionStartAsync, ParseHeimMansionDetailFuncAsync,
    ParseHeimKodateStartAsync, ParseHeimKodateDetailFuncAsync,
    ParseHeimTochiStartAsync, ParseHeimTochiDetailFuncAsync
)

heim_bp = Blueprint('heim', __name__)

@heim_bp.route(API_KEY_HEIM_MANSION_START, methods=['POST', 'GET'])
def heimMansionStart():
    # 東京都全体の中古マンション・分譲住宅
    return ParseHeimMansionStartAsync().main("https://www.tokyo816.jp/bunjou/search_area?all_pref=1&pref_check%5B%5D=13")

@heim_bp.route(API_KEY_HEIM_MANSION_DETAIL, methods=['POST', 'GET'])
def heimMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseHeimMansionDetailFuncAsync().main(url)

@heim_bp.route(API_KEY_HEIM_KODATE_START, methods=['POST', 'GET'])
def heimKodateStart():
    # 東京都全体の中古戸建て・分譲住宅
    return ParseHeimKodateStartAsync().main("https://www.tokyo816.jp/bunjou/search_area?all_pref=1&pref_check%5B%5D=13")

@heim_bp.route(API_KEY_HEIM_KODATE_DETAIL, methods=['POST', 'GET'])
def heimKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseHeimKodateDetailFuncAsync().main(url)

@heim_bp.route(API_KEY_HEIM_TOCHI_START, methods=['POST', 'GET'])
def heimTochiStart():
    # 東京都全体の土地
    return ParseHeimTochiStartAsync().main("https://www.tokyo816.jp/bunjou/search_area?all_pref=1&pref_check%5B%5D=13")


@heim_bp.route(API_KEY_HEIM_TOCHI_DETAIL, methods=['POST', 'GET'])
def heimTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseHeimTochiDetailFuncAsync().main(url)

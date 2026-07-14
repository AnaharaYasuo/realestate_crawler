# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
import logging
from package.api.api import (
    API_KEY_KEIO_MANSION_START, API_KEY_KEIO_MANSION_DETAIL,
    API_KEY_KEIO_KODATE_START, API_KEY_KEIO_KODATE_DETAIL,
    API_KEY_KEIO_TOCHI_START, API_KEY_KEIO_TOCHI_DETAIL
)
from package.api.keio import (
    ParseKeioMansionStartAsync, ParseKeioMansionDetailFuncAsync,
    ParseKeioKodateStartAsync, ParseKeioKodateDetailFuncAsync,
    ParseKeioTochiStartAsync, ParseKeioTochiDetailFuncAsync
)

keio_bp = Blueprint('keio', __name__)

@keio_bp.route(API_KEY_KEIO_MANSION_START, methods=['POST', 'GET'])
def keioMansionStart():
    # 東京都の中古マンション
    return ParseKeioMansionStartAsync().main("https://chukai.keiofudosan.co.jp/sale/search/area/pref_13/?boshu_kind_summary_code%5B%5D=1")

@keio_bp.route(API_KEY_KEIO_MANSION_DETAIL, methods=['POST', 'GET'])
def keioMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseKeioMansionDetailFuncAsync().main(url)

@keio_bp.route(API_KEY_KEIO_KODATE_START, methods=['POST', 'GET'])
def keioKodateStart():
    # 東京都の中古戸建て
    return ParseKeioKodateStartAsync().main("https://chukai.keiofudosan.co.jp/sale/search/area/pref_13/?boshu_kind_summary_code%5B%5D=3")

@keio_bp.route(API_KEY_KEIO_KODATE_DETAIL, methods=['POST', 'GET'])
def keioKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseKeioKodateDetailFuncAsync().main(url)

@keio_bp.route(API_KEY_KEIO_TOCHI_START, methods=['POST', 'GET'])
def keioTochiStart():
    # 東京都の土地
    return ParseKeioTochiStartAsync().main("https://chukai.keiofudosan.co.jp/sale/search/area/pref_13/?boshu_kind_summary_code%5B%5D=4")

@keio_bp.route(API_KEY_KEIO_TOCHI_DETAIL, methods=['POST', 'GET'])
def keioTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseKeioTochiDetailFuncAsync().main(url)

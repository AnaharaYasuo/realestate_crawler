# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
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
def keio_mansion_start():
    # 東京都の中古マンション (WP REST API)
    return ParseKeioMansionStartAsync().main("https://chukai.keiofudosan.co.jp/wp-json/wp/v2/get_search_result_sale?rent_or_sale=sale&area_or_line=area&item_per_page=30&page_num=1&pref=13&boshu_kind_summary_code%5B%5D=1")

keioMansionStart = keio_mansion_start

@keio_bp.route(API_KEY_KEIO_MANSION_DETAIL, methods=['POST', 'GET'])
def keio_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseKeioMansionDetailFuncAsync().main(url)
    return "finish", 200

keioMansionDetail = keio_mansion_detail

@keio_bp.route(API_KEY_KEIO_KODATE_START, methods=['POST', 'GET'])
def keio_kodate_start():
    # 東京都の中古戸建て (WP REST API)
    return ParseKeioKodateStartAsync().main("https://chukai.keiofudosan.co.jp/wp-json/wp/v2/get_search_result_sale?rent_or_sale=sale&area_or_line=area&item_per_page=30&page_num=1&pref=13&boshu_kind_summary_code%5B%5D=3")

keioKodateStart = keio_kodate_start

@keio_bp.route(API_KEY_KEIO_KODATE_DETAIL, methods=['POST', 'GET'])
def keio_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseKeioKodateDetailFuncAsync().main(url)
    return "finish", 200

keioKodateDetail = keio_kodate_detail

@keio_bp.route(API_KEY_KEIO_TOCHI_START, methods=['POST', 'GET'])
def keio_tochi_start():
    # 東京都の土地 (WP REST API)
    return ParseKeioTochiStartAsync().main("https://chukai.keiofudosan.co.jp/wp-json/wp/v2/get_search_result_sale?rent_or_sale=sale&area_or_line=area&item_per_page=30&page_num=1&pref=13&boshu_kind_summary_code%5B%5D=4")

keioTochiStart = keio_tochi_start

@keio_bp.route(API_KEY_KEIO_TOCHI_DETAIL, methods=['POST', 'GET'])
def keio_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseKeioTochiDetailFuncAsync().main(url)
    return "finish", 200

keioTochiDetail = keio_tochi_detail

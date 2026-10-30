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
def keisei_mansion_start():
    # 全国の中古マンション（r_type=3）。mode は list のみ。
    return ParseKeiseiMansionStartAsync().main(
        "https://www.keisei-land.co.jp/contents/code/search_result?mode=list&all_pref=1&r_type=3&by=area"
    )

keiseiMansionStart = keisei_mansion_start

@keisei_bp.route(API_KEY_KEISEI_MANSION_DETAIL, methods=['POST', 'GET'])
def keisei_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseKeiseiMansionDetailFuncAsync().main(url)
    return "finish", 200

keiseiMansionDetail = keisei_mansion_detail

@keisei_bp.route(API_KEY_KEISEI_KODATE_START, methods=['POST', 'GET'])
def keisei_kodate_start():
    # 全国の中古戸建（r_type=2）。mode は list のみ。
    return ParseKeiseiKodateStartAsync().main(
        "https://www.keisei-land.co.jp/contents/code/search_result?mode=list&all_pref=1&r_type=2&by=area"
    )

keiseiKodateStart = keisei_kodate_start

@keisei_bp.route(API_KEY_KEISEI_KODATE_DETAIL, methods=['POST', 'GET'])
def keisei_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseKeiseiKodateDetailFuncAsync().main(url)
    return "finish", 200

keiseiKodateDetail = keisei_kodate_detail

@keisei_bp.route(API_KEY_KEISEI_TOCHI_START, methods=['POST', 'GET'])
def keisei_tochi_start():
    # 全国の土地（r_type=1）。mode は list のみ。
    return ParseKeiseiTochiStartAsync().main(
        "https://www.keisei-land.co.jp/contents/code/search_result?mode=list&all_pref=1&r_type=1&by=area"
    )

keiseiTochiStart = keisei_tochi_start

@keisei_bp.route(API_KEY_KEISEI_TOCHI_DETAIL, methods=['POST', 'GET'])
def keisei_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseKeiseiTochiDetailFuncAsync().main(url)
    return "finish", 200

keiseiTochiDetail = keisei_tochi_detail

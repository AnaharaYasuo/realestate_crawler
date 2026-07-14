# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_SEIBU_MANSION_START, API_KEY_SEIBU_MANSION_DETAIL,
    API_KEY_SEIBU_KODATE_START, API_KEY_SEIBU_KODATE_DETAIL,
    API_KEY_SEIBU_TOCHI_START, API_KEY_SEIBU_TOCHI_DETAIL
)
from package.api.seibu import (
    ParseSeibuMansionStartAsync, ParseSeibuMansionDetailFuncAsync,
    ParseSeibuKodateStartAsync, ParseSeibuKodateDetailFuncAsync,
    ParseSeibuTochiStartAsync, ParseSeibuTochiDetailFuncAsync
)

seibu_bp = Blueprint('seibu', __name__)

@seibu_bp.route(API_KEY_SEIBU_MANSION_START, methods=['POST', 'GET'])
def seibuMansionStart():
    # 東京都の中古マンション
    return ParseSeibuMansionStartAsync().main("https://sumai.seiburealestate-pm.co.jp/service/property/?type[]=1&pref[]=13")

@seibu_bp.route(API_KEY_SEIBU_MANSION_DETAIL, methods=['POST', 'GET'])
def seibuMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSeibuMansionDetailFuncAsync().main(url)

@seibu_bp.route(API_KEY_SEIBU_KODATE_START, methods=['POST', 'GET'])
def seibuKodateStart():
    # 東京都の中古戸建
    return ParseSeibuKodateStartAsync().main("https://sumai.seiburealestate-pm.co.jp/service/property/?type[]=2&pref[]=13")

@seibu_bp.route(API_KEY_SEIBU_KODATE_DETAIL, methods=['POST', 'GET'])
def seibuKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSeibuKodateDetailFuncAsync().main(url)

@seibu_bp.route(API_KEY_SEIBU_TOCHI_START, methods=['POST', 'GET'])
def seibuTochiStart():
    # 東京都の土地
    return ParseSeibuTochiStartAsync().main("https://sumai.seiburealestate-pm.co.jp/service/property/?type[]=3&pref[]=13")

@seibu_bp.route(API_KEY_SEIBU_TOCHI_DETAIL, methods=['POST', 'GET'])
def seibuTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSeibuTochiDetailFuncAsync().main(url)

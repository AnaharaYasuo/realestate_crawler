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
def seibu_mansion_start():
    # 全国の中古マンション（在庫が薄いため pref 絞り込みなし）
    return ParseSeibuMansionStartAsync().main("https://sumai.seiburealestate-pm.co.jp/service/property/?type[]=1")

seibuMansionStart = seibu_mansion_start

@seibu_bp.route(API_KEY_SEIBU_MANSION_DETAIL, methods=['POST', 'GET'])
def seibu_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSeibuMansionDetailFuncAsync().main(url)
    return "finish", 200

seibuMansionDetail = seibu_mansion_detail

@seibu_bp.route(API_KEY_SEIBU_KODATE_START, methods=['POST', 'GET'])
def seibu_kodate_start():
    # 東京都の中古戸建
    return ParseSeibuKodateStartAsync().main("https://sumai.seiburealestate-pm.co.jp/service/property/?type[]=2&pref[]=13")

seibuKodateStart = seibu_kodate_start

@seibu_bp.route(API_KEY_SEIBU_KODATE_DETAIL, methods=['POST', 'GET'])
def seibu_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSeibuKodateDetailFuncAsync().main(url)
    return "finish", 200

seibuKodateDetail = seibu_kodate_detail

@seibu_bp.route(API_KEY_SEIBU_TOCHI_START, methods=['POST', 'GET'])
def seibu_tochi_start():
    # 東京都の土地
    return ParseSeibuTochiStartAsync().main("https://sumai.seiburealestate-pm.co.jp/service/property/?type[]=3&pref[]=13")

seibuTochiStart = seibu_tochi_start

@seibu_bp.route(API_KEY_SEIBU_TOCHI_DETAIL, methods=['POST', 'GET'])
def seibu_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSeibuTochiDetailFuncAsync().main(url)
    return "finish", 200

seibuTochiDetail = seibu_tochi_detail

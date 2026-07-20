# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_AFR_MANSION_START, API_KEY_AFR_MANSION_DETAIL,
    API_KEY_AFR_KODATE_START, API_KEY_AFR_KODATE_DETAIL,
    API_KEY_AFR_TOCHI_START, API_KEY_AFR_TOCHI_DETAIL
)
from package.api.afr import (
    ParseAfrMansionStartAsync, ParseAfrMansionDetailFuncAsync,
    ParseAfrKodateStartAsync, ParseAfrKodateDetailFuncAsync,
    ParseAfrTochiStartAsync, ParseAfrTochiDetailFuncAsync
)

afr_bp = Blueprint('afr', __name__)

# 都道府県パラメータを含むURL。関東の主要1都3県+周辺を指定。
# searchlist.html は GET で都道府県パラメータを 47 個組み立てる必要がある。
# 都道府県パラメータを含むURL。関東の主要1都3県+周辺を指定。
# searchlist.html は GET で都道府県パラメータを 47 個組み立てる必要がある。
def get_start_url(use_type='forhome'):
    import urllib.parse
    prefs = ["東京都", "神奈川県", "埼玉県", "千葉県"]
    params = []
    for i in range(1, 48):
        if i <= len(prefs):
            val = prefs[i-1]
        else:
            val = " "
        params.append(f"pref{i}={urllib.parse.quote(val)}")
    pref_str = "&".join(params)
    return f"https://www.hebel-haus.com/stockhebel/purchase/{use_type}/searchlist.html/?shn=d&{pref_str}"

@afr_bp.route(API_KEY_AFR_MANSION_START, methods=['POST', 'GET'])
def afrMansionStart():
    return ParseAfrMansionStartAsync().main(get_start_url('forhome'))

@afr_bp.route(API_KEY_AFR_MANSION_DETAIL, methods=['POST', 'GET'])
def afrMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseAfrMansionDetailFuncAsync().main(url)

@afr_bp.route(API_KEY_AFR_KODATE_START, methods=['POST', 'GET'])
def afrKodateStart():
    return ParseAfrKodateStartAsync().main(get_start_url('forhome'))

@afr_bp.route(API_KEY_AFR_KODATE_DETAIL, methods=['POST', 'GET'])
def afrKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseAfrKodateDetailFuncAsync().main(url)

@afr_bp.route(API_KEY_AFR_TOCHI_START, methods=['POST', 'GET'])
def afrTochiStart():
    return ParseAfrTochiStartAsync().main(get_start_url('forhome'))

@afr_bp.route(API_KEY_AFR_TOCHI_DETAIL, methods=['POST', 'GET'])
def afrTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseAfrTochiDetailFuncAsync().main(url)

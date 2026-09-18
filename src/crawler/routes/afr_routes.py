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
    prefs = [
        "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", 
        "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県", 
        "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", 
        "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", 
        "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県", 
        "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県", 
        "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
    ]
    params = [f"pref{i+1}={urllib.parse.quote(p)}" for i, p in enumerate(prefs)]
    pref_str = "&".join(params)
    return f"https://www.hebel-haus.com/stockhebel/purchase/{use_type}/searchlist.html/?shn=d&{pref_str}"

@afr_bp.route(API_KEY_AFR_MANSION_START, methods=['POST', 'GET'])
def afrMansionStart():
    return ParseAfrMansionStartAsync().main(get_start_url('forhome'))

@afr_bp.route(API_KEY_AFR_MANSION_DETAIL, methods=['POST', 'GET'])
def afrMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseAfrMansionDetailFuncAsync().main(url)
    return "finish", 200

@afr_bp.route(API_KEY_AFR_KODATE_START, methods=['POST', 'GET'])
def afrKodateStart():
    return ParseAfrKodateStartAsync().main(get_start_url('forhome'))

@afr_bp.route(API_KEY_AFR_KODATE_DETAIL, methods=['POST', 'GET'])
def afrKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseAfrKodateDetailFuncAsync().main(url)
    return "finish", 200

@afr_bp.route(API_KEY_AFR_TOCHI_START, methods=['POST', 'GET'])
def afrTochiStart():
    return ParseAfrTochiStartAsync().main(get_start_url('forhome'))

@afr_bp.route(API_KEY_AFR_TOCHI_DETAIL, methods=['POST', 'GET'])
def afrTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseAfrTochiDetailFuncAsync().main(url)
    return "finish", 200

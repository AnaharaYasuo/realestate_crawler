# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_SEKISUI_MANSION_START, API_KEY_SEKISUI_MANSION_DETAIL,
    API_KEY_SEKISUI_KODATE_START, API_KEY_SEKISUI_KODATE_DETAIL,
    API_KEY_SEKISUI_TOCHI_START, API_KEY_SEKISUI_TOCHI_DETAIL
)
from package.api.sekisui import (
    ParseSekisuiMansionStartAsync, ParseSekisuiMansionDetailFuncAsync,
    ParseSekisuiKodateStartAsync, ParseSekisuiKodateDetailFuncAsync,
    ParseSekisuiTochiStartAsync, ParseSekisuiTochiDetailFuncAsync
)

sekisui_bp = Blueprint('sekisui', __name__)

@sekisui_bp.route(API_KEY_SEKISUI_MANSION_START, methods=['POST', 'GET'])
def sekisui_mansion_start():
    return ParseSekisuiMansionStartAsync().main("https://sumusite.sekisuihouse.co.jp/kanto/mansion/area-tokyo/list/")

sekisuiMansionStart = sekisui_mansion_start

@sekisui_bp.route(API_KEY_SEKISUI_MANSION_DETAIL, methods=['POST', 'GET'])
def sekisui_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSekisuiMansionDetailFuncAsync().main(url)
    return "finish", 200

sekisuiMansionDetail = sekisui_mansion_detail

@sekisui_bp.route(API_KEY_SEKISUI_KODATE_START, methods=['POST', 'GET'])
def sekisui_kodate_start():
    return ParseSekisuiKodateStartAsync().main("https://sumusite.sekisuihouse.co.jp/kanto/kodate/area-tokyo/list/")

sekisuiKodateStart = sekisui_kodate_start

@sekisui_bp.route(API_KEY_SEKISUI_KODATE_DETAIL, methods=['POST', 'GET'])
def sekisui_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSekisuiKodateDetailFuncAsync().main(url)
    return "finish", 200

sekisuiKodateDetail = sekisui_kodate_detail

@sekisui_bp.route(API_KEY_SEKISUI_TOCHI_START, methods=['POST', 'GET'])
def sekisui_tochi_start():
    return ParseSekisuiTochiStartAsync().main("https://sumusite.sekisuihouse.co.jp/kanto/tochi/area-tokyo/list/")

sekisuiTochiStart = sekisui_tochi_start

@sekisui_bp.route(API_KEY_SEKISUI_TOCHI_DETAIL, methods=['POST', 'GET'])
def sekisui_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSekisuiTochiDetailFuncAsync().main(url)
    return "finish", 200

sekisuiTochiDetail = sekisui_tochi_detail

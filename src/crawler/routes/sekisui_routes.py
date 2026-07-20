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
def sekisuiMansionStart():
    return ParseSekisuiMansionStartAsync().main("https://sumusite.sekisuihouse.co.jp/kanto/mansion/area-tokyo/list/")

@sekisui_bp.route(API_KEY_SEKISUI_MANSION_DETAIL, methods=['POST', 'GET'])
def sekisuiMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSekisuiMansionDetailFuncAsync().main(url)

@sekisui_bp.route(API_KEY_SEKISUI_KODATE_START, methods=['POST', 'GET'])
def sekisuiKodateStart():
    return ParseSekisuiKodateStartAsync().main("https://sumusite.sekisuihouse.co.jp/kanto/kodate/area-tokyo/list/")

@sekisui_bp.route(API_KEY_SEKISUI_KODATE_DETAIL, methods=['POST', 'GET'])
def sekisuiKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSekisuiKodateDetailFuncAsync().main(url)

@sekisui_bp.route(API_KEY_SEKISUI_TOCHI_START, methods=['POST', 'GET'])
def sekisuiTochiStart():
    return ParseSekisuiTochiStartAsync().main("https://sumusite.sekisuihouse.co.jp/kanto/tochi/area-tokyo/list/")

@sekisui_bp.route(API_KEY_SEKISUI_TOCHI_DETAIL, methods=['POST', 'GET'])
def sekisuiTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSekisuiTochiDetailFuncAsync().main(url)

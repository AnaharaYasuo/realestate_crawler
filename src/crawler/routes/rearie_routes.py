# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_REARIE_MANSION_START, API_KEY_REARIE_MANSION_DETAIL,
    API_KEY_REARIE_KODATE_START, API_KEY_REARIE_KODATE_DETAIL,
    API_KEY_REARIE_TOCHI_START, API_KEY_REARIE_TOCHI_DETAIL
)
from package.api.rearie import (
    ParseRearieMansionStartAsync, ParseRearieMansionDetailFuncAsync,
    ParseRearieKodateStartAsync, ParseRearieKodateDetailFuncAsync,
    ParseRearieTochiStartAsync, ParseRearieTochiDetailFuncAsync
)

rearie_bp = Blueprint('rearie', __name__)

@rearie_bp.route(API_KEY_REARIE_MANSION_START, methods=['POST', 'GET'])
def rearieMansionStart():
    # 中古マンション (Repros REST API)
    return ParseRearieMansionStartAsync().main("https://phfudousan.repros.jp/api/v2/kubunList/?key=32df8d8a-58fb-5d59-ab6a-6e6c09239add")

@rearie_bp.route(API_KEY_REARIE_MANSION_DETAIL, methods=['POST', 'GET'])
def rearieMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseRearieMansionDetailFuncAsync().main(url)
    return "finish", 200

@rearie_bp.route(API_KEY_REARIE_KODATE_START, methods=['POST', 'GET'])
def rearieKodateStart():
    # 中古戸建て (Repros REST API)
    return ParseRearieKodateStartAsync().main("https://phfudousan.repros.jp/api/v2/kodateList/?key=32df8d8a-58fb-5d59-ab6a-6e6c09239add")

@rearie_bp.route(API_KEY_REARIE_KODATE_DETAIL, methods=['POST', 'GET'])
def rearieKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseRearieKodateDetailFuncAsync().main(url)
    return "finish", 200

@rearie_bp.route(API_KEY_REARIE_TOCHI_START, methods=['POST', 'GET'])
def rearieTochiStart():
    # 土地 (Repros REST API)
    return ParseRearieTochiStartAsync().main("https://phfudousan.repros.jp/api/v2/tochiList/?key=32df8d8a-58fb-5d59-ab6a-6e6c09239add")

@rearie_bp.route(API_KEY_REARIE_TOCHI_DETAIL, methods=['POST', 'GET'])
def rearieTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseRearieTochiDetailFuncAsync().main(url)
    return "finish", 200

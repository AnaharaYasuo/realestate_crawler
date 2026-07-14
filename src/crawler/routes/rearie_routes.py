# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
import logging
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
    # 東京都全体の中古マンション
    return ParseRearieMansionStartAsync().main("https://homes.panasonic.com/rearie/buy/property/mansion/list.html?pref=13")

@rearie_bp.route(API_KEY_REARIE_MANSION_DETAIL, methods=['POST', 'GET'])
def rearieMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseRearieMansionDetailFuncAsync().main(url)

@rearie_bp.route(API_KEY_REARIE_KODATE_START, methods=['POST', 'GET'])
def rearieKodateStart():
    # 東京都全体の中古戸建て
    return ParseRearieKodateStartAsync().main("https://homes.panasonic.com/rearie/buy/property/house/list.html?pref=13")

@rearie_bp.route(API_KEY_REARIE_KODATE_DETAIL, methods=['POST', 'GET'])
def rearieKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseRearieKodateDetailFuncAsync().main(url)

@rearie_bp.route(API_KEY_REARIE_TOCHI_START, methods=['POST', 'GET'])
def rearieTochiStart():
    # 東京都全体の土地
    return ParseRearieTochiStartAsync().main("https://homes.panasonic.com/rearie/buy/property/land/list.html?pref=13")

@rearie_bp.route(API_KEY_REARIE_TOCHI_DETAIL, methods=['POST', 'GET'])
def rearieTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseRearieTochiDetailFuncAsync().main(url)

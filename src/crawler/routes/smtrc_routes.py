# -*- coding: utf-8 -*-
from flask import Blueprint, request
import json
from package.api.api import (
    API_KEY_SMTRC_MANSION_START, API_KEY_SMTRC_MANSION_DETAIL,
    API_KEY_SMTRC_KODATE_START, API_KEY_SMTRC_KODATE_DETAIL,
    API_KEY_SMTRC_TOCHI_START, API_KEY_SMTRC_TOCHI_DETAIL,
    API_KEY_SMTRC_INVESTMENT_START, API_KEY_SMTRC_INVESTMENT_DETAIL
)
from package.api.smtrc import (
    ParseSmtrcMansionStartAsync, ParseSmtrcMansionDetailFuncAsync,
    ParseSmtrcKodateStartAsync, ParseSmtrcKodateDetailFuncAsync,
    ParseSmtrcTochiStartAsync, ParseSmtrcTochiDetailFuncAsync,
    ParseSmtrcInvestmentStartAsync, ParseSmtrcInvestmentDetailFuncAsync
)

smtrc_bp = Blueprint('smtrc', __name__)

@smtrc_bp.route(API_KEY_SMTRC_MANSION_START, methods=['POST', 'GET'])
def smtrcMansionStart():
    return ParseSmtrcMansionStartAsync().main("https://smtrc.jp/list/listViewLive/index?search=city&prefcode=13&bukenkind=1")

@smtrc_bp.route(API_KEY_SMTRC_MANSION_DETAIL, methods=['POST', 'GET'])
def smtrcMansionDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSmtrcMansionDetailFuncAsync().main(url)

@smtrc_bp.route(API_KEY_SMTRC_KODATE_START, methods=['POST', 'GET'])
def smtrcKodateStart():
    return ParseSmtrcKodateStartAsync().main("https://smtrc.jp/list/listViewLive/index?search=city&prefcode=13&bukenkind=2")

@smtrc_bp.route(API_KEY_SMTRC_KODATE_DETAIL, methods=['POST', 'GET'])
def smtrcKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSmtrcKodateDetailFuncAsync().main(url)

@smtrc_bp.route(API_KEY_SMTRC_TOCHI_START, methods=['POST', 'GET'])
def smtrcTochiStart():
    return ParseSmtrcTochiStartAsync().main("https://smtrc.jp/list/listViewLive/index?search=city&prefcode=13&bukenkind=3")

@smtrc_bp.route(API_KEY_SMTRC_TOCHI_DETAIL, methods=['POST', 'GET'])
def smtrcTochiDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSmtrcTochiDetailFuncAsync().main(url)

@smtrc_bp.route(API_KEY_SMTRC_INVESTMENT_START, methods=['POST', 'GET'])
def smtrcInvestmentStart():
    return ParseSmtrcInvestmentStartAsync().main("https://smtrc.jp/list/Listviewinvest/index?proptype=33&prefcode=13")

@smtrc_bp.route(API_KEY_SMTRC_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def smtrcInvestmentDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    return ParseSmtrcInvestmentDetailFuncAsync().main(url)


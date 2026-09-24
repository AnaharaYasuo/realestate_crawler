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
def smtrc_mansion_start():
    return ParseSmtrcMansionStartAsync().main("https://smtrc.jp/list/listViewLive/index?search=city&prefcode=13&bukenkind=1")

smtrcMansionStart = smtrc_mansion_start

@smtrc_bp.route(API_KEY_SMTRC_MANSION_DETAIL, methods=['POST', 'GET'])
def smtrc_mansion_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSmtrcMansionDetailFuncAsync().main(url)
    return "finish", 200

smtrcMansionDetail = smtrc_mansion_detail

@smtrc_bp.route(API_KEY_SMTRC_KODATE_START, methods=['POST', 'GET'])
def smtrc_kodate_start():
    return ParseSmtrcKodateStartAsync().main("https://smtrc.jp/list/listViewLive/index?search=city&prefcode=13&bukenkind=2")

smtrcKodateStart = smtrc_kodate_start

@smtrc_bp.route(API_KEY_SMTRC_KODATE_DETAIL, methods=['POST', 'GET'])
def smtrc_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSmtrcKodateDetailFuncAsync().main(url)
    return "finish", 200

smtrcKodateDetail = smtrc_kodate_detail

@smtrc_bp.route(API_KEY_SMTRC_TOCHI_START, methods=['POST', 'GET'])
def smtrc_tochi_start():
    return ParseSmtrcTochiStartAsync().main("https://smtrc.jp/list/listViewLive/index?search=city&prefcode=13&bukenkind=3")

smtrcTochiStart = smtrc_tochi_start

@smtrc_bp.route(API_KEY_SMTRC_TOCHI_DETAIL, methods=['POST', 'GET'])
def smtrc_tochi_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSmtrcTochiDetailFuncAsync().main(url)
    return "finish", 200

smtrcTochiDetail = smtrc_tochi_detail

@smtrc_bp.route(API_KEY_SMTRC_INVESTMENT_START, methods=['POST', 'GET'])
def smtrc_investment_start():
    return ParseSmtrcInvestmentStartAsync().main("https://smtrc.jp/list/Listviewinvest/index?proptype=33&prefcode=13")

smtrcInvestmentStart = smtrc_investment_start

@smtrc_bp.route(API_KEY_SMTRC_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def smtrc_investment_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseSmtrcInvestmentDetailFuncAsync().main(url)
    return "finish", 200

smtrcInvestmentDetail = smtrc_investment_detail


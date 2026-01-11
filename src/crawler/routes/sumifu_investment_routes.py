from flask import Blueprint, request
from package.api.api import API_KEY_SUMIFU_INVEST_START, API_KEY_SUMIFU_INVEST_LIST, API_KEY_SUMIFU_INVEST_DETAIL
from package.api.sumifu_investment import ParseSumifuInvestStartAsync, ParseSumifuInvestListFuncAsync, ParseSumifuInvestDetailFuncAsync

sumifu_investment_bp = Blueprint('sumifu_investment', __name__)

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_START, methods=['POST', 'GET'])
def sumifuInvestStart():
    ParseSumifuInvestStartAsync().main("")
    return "OK"

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_LIST, methods=['POST', 'GET'])
def sumifuInvestList():
    url = request.json['url']
    ParseSumifuInvestListFuncAsync().main(url)
    return "OK"

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_DETAIL, methods=['POST', 'GET'])
def sumifuInvestDetail():
    url = request.json['url']
    ParseSumifuInvestDetailFuncAsync().main(url)
    return "OK"

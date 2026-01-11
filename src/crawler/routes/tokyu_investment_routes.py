from flask import Blueprint, request
from package.api.api import API_KEY_TOKYU_INVEST_START, API_KEY_TOKYU_INVEST_LIST, API_KEY_TOKYU_INVEST_DETAIL
from package.api.tokyu_investment import ParseTokyuInvestStartAsync, ParseTokyuInvestListFuncAsync, ParseTokyuInvestDetailFuncAsync

tokyu_investment_bp = Blueprint('tokyu_investment', __name__)

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_START, methods=['POST', 'GET'])
def tokyuInvestStart():
    ParseTokyuInvestStartAsync().main("")
    return "OK"

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_LIST, methods=['POST', 'GET'])
def tokyuInvestList():
    url = request.json['url']
    ParseTokyuInvestListFuncAsync().main(url)
    return "OK"

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_DETAIL, methods=['POST', 'GET'])
def tokyuInvestDetail():
    url = request.json['url']
    ParseTokyuInvestDetailFuncAsync().main(url)
    return "OK"

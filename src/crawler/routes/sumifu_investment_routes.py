
from flask import Blueprint, request
from package.api.api import \
    API_KEY_SUMIFU_INVEST_KODATE_START, API_KEY_SUMIFU_INVEST_KODATE_LIST, API_KEY_SUMIFU_INVEST_KODATE_DETAIL, \
    API_KEY_SUMIFU_INVEST_APARTMENT_START, API_KEY_SUMIFU_INVEST_APARTMENT_LIST, API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL

from package.api.sumifu_investment import \
    ParseSumifuInvestKodateStartAsync, ParseSumifuInvestKodateListFuncAsync, ParseSumifuInvestKodateDetailFuncAsync, \
    ParseSumifuInvestApartmentStartAsync, ParseSumifuInvestApartmentListFuncAsync, ParseSumifuInvestApartmentDetailFuncAsync

sumifu_investment_bp = Blueprint('sumifu_investment', __name__)

# ==============================================================================
#  KODATE ROUTES
# ==============================================================================

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_KODATE_START, methods=['POST', 'GET'])
def sumifuInvestKodateStart():
    ParseSumifuInvestKodateStartAsync().main("")
    return "OK"

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_KODATE_LIST, methods=['POST', 'GET'])
def sumifuInvestKodateList():
    url = request.json['url']
    ParseSumifuInvestKodateListFuncAsync().main(url)
    return "OK"

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_KODATE_DETAIL, methods=['POST', 'GET'])
def sumifuInvestKodateDetail():
    url = request.json['url']
    ParseSumifuInvestKodateDetailFuncAsync().main(url)
    return "OK"

# ==============================================================================
#  APARTMENT ROUTES
# ==============================================================================

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def sumifuInvestApartmentStart():
    ParseSumifuInvestApartmentStartAsync().main("")
    return "OK"

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_APARTMENT_LIST, methods=['POST', 'GET'])
def sumifuInvestApartmentList():
    url = request.json['url']
    ParseSumifuInvestApartmentListFuncAsync().main(url)
    return "OK"

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def sumifuInvestApartmentDetail():
    url = request.json['url']
    ParseSumifuInvestApartmentDetailFuncAsync().main(url)
    return "OK"

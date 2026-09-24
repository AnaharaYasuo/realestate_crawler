
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
def sumifu_invest_kodate_start():
    ParseSumifuInvestKodateStartAsync().main("")
    return "OK"

sumifuInvestKodateStart = sumifu_invest_kodate_start

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_KODATE_LIST, methods=['POST', 'GET'])
def sumifu_invest_kodate_list():
    url = request.json['url']
    ParseSumifuInvestKodateListFuncAsync().main(url)
    return "OK"

sumifuInvestKodateList = sumifu_invest_kodate_list

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_KODATE_DETAIL, methods=['POST', 'GET'])
def sumifu_invest_kodate_detail():
    url = request.json['url']
    ParseSumifuInvestKodateDetailFuncAsync().main(url)
    return "OK"

sumifuInvestKodateDetail = sumifu_invest_kodate_detail

# ==============================================================================
#  APARTMENT ROUTES
# ==============================================================================

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def sumifu_invest_apartment_start():
    ParseSumifuInvestApartmentStartAsync().main("")
    return "OK"

sumifuInvestApartmentStart = sumifu_invest_apartment_start

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_APARTMENT_LIST, methods=['POST', 'GET'])
def sumifu_invest_apartment_list():
    url = request.json['url']
    ParseSumifuInvestApartmentListFuncAsync().main(url)
    return "OK"

sumifuInvestApartmentList = sumifu_invest_apartment_list

@sumifu_investment_bp.route(API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def sumifu_invest_apartment_detail():
    url = request.json['url']
    ParseSumifuInvestApartmentDetailFuncAsync().main(url)
    return "OK"

sumifuInvestApartmentDetail = sumifu_invest_apartment_detail

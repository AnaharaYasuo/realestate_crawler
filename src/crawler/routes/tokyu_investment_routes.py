from flask import Blueprint, request
from package.api.api import \
    API_KEY_TOKYU_INVEST_APARTMENT_START, API_KEY_TOKYU_INVEST_APARTMENT_LIST, API_KEY_TOKYU_INVEST_APARTMENT_DETAIL, \
    API_KEY_TOKYU_INVEST_KODATE_START, API_KEY_TOKYU_INVEST_KODATE_LIST, API_KEY_TOKYU_INVEST_KODATE_DETAIL

from package.api.tokyu_investment import \
    ParseTokyuInvestApartmentStartAsync, ParseTokyuInvestApartmentListFuncAsync, ParseTokyuInvestApartmentDetailFuncAsync, \
    ParseTokyuInvestKodateStartAsync, ParseTokyuInvestKodateListFuncAsync, ParseTokyuInvestKodateDetailFuncAsync

tokyu_investment_bp = Blueprint('tokyu_investment', __name__)

# ==============================================================================
#  APARTMENT ROUTES
# ==============================================================================

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def tokyu_invest_apartment_start():
    ParseTokyuInvestApartmentStartAsync().main("")
    return "OK"

tokyuInvestApartmentStart = tokyu_invest_apartment_start

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_APARTMENT_LIST, methods=['POST', 'GET'])
def tokyu_invest_apartment_list():
    url = request.json['url']
    ParseTokyuInvestApartmentListFuncAsync().main(url)
    return "OK"

tokyuInvestApartmentList = tokyu_invest_apartment_list

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def tokyu_invest_apartment_detail():
    url = request.json['url']
    ParseTokyuInvestApartmentDetailFuncAsync().main(url)
    return "OK"

tokyuInvestApartmentDetail = tokyu_invest_apartment_detail

# ==============================================================================
#  KODATE ROUTES
# ==============================================================================

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_KODATE_START, methods=['POST', 'GET'])
def tokyu_invest_kodate_start():
    ParseTokyuInvestKodateStartAsync().main("")
    return "OK"

tokyuInvestKodateStart = tokyu_invest_kodate_start

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_KODATE_LIST, methods=['POST', 'GET'])
def tokyu_invest_kodate_list():
    url = request.json['url']
    ParseTokyuInvestKodateListFuncAsync().main(url)
    return "OK"

tokyuInvestKodateList = tokyu_invest_kodate_list

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_KODATE_DETAIL, methods=['POST', 'GET'])
def tokyu_invest_kodate_detail():
    url = request.json['url']
    ParseTokyuInvestKodateDetailFuncAsync().main(url)
    return "OK"

tokyuInvestKodateDetail = tokyu_invest_kodate_detail

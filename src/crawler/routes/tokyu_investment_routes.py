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
def tokyuInvestApartmentStart():
    ParseTokyuInvestApartmentStartAsync().main("")
    return "OK"

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_APARTMENT_LIST, methods=['POST', 'GET'])
def tokyuInvestApartmentList():
    url = request.json['url']
    ParseTokyuInvestApartmentListFuncAsync().main(url)
    return "OK"

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def tokyuInvestApartmentDetail():
    url = request.json['url']
    ParseTokyuInvestApartmentDetailFuncAsync().main(url)
    return "OK"

# ==============================================================================
#  KODATE ROUTES
# ==============================================================================

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_KODATE_START, methods=['POST', 'GET'])
def tokyuInvestKodateStart():
    ParseTokyuInvestKodateStartAsync().main("")
    return "OK"

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_KODATE_LIST, methods=['POST', 'GET'])
def tokyuInvestKodateList():
    url = request.json['url']
    ParseTokyuInvestKodateListFuncAsync().main(url)
    return "OK"

@tokyu_investment_bp.route(API_KEY_TOKYU_INVEST_KODATE_DETAIL, methods=['POST', 'GET'])
def tokyuInvestKodateDetail():
    url = request.json['url']
    ParseTokyuInvestKodateDetailFuncAsync().main(url)
    return "OK"

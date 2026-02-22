
from flask import Blueprint, request
from package.api.api import \
    API_KEY_MISAWA_INVEST_APARTMENT_START, API_KEY_MISAWA_INVEST_APARTMENT_LIST, API_KEY_MISAWA_INVEST_APARTMENT_DETAIL, \
    API_KEY_MISAWA_INVEST_KODATE_START, API_KEY_MISAWA_INVEST_KODATE_LIST, API_KEY_MISAWA_INVEST_KODATE_DETAIL, \
    API_KEY_MISAWA_INVEST_START

from package.api.misawa_investment import \
    ParseMisawaInvestmentApartmentStartAsync, ParseMisawaInvestmentApartmentListFuncAsync, ParseMisawaInvestmentApartmentDetailFuncAsync, \
    ParseMisawaInvestmentKodateStartAsync, ParseMisawaInvestmentKodateListFuncAsync, ParseMisawaInvestmentKodateDetailFuncAsync, \
    ParseMisawaInvestmentStartAsync

misawa_investment_bp = Blueprint('misawa_investment', __name__)

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_START, methods=['POST', 'GET'])
def misawaInvestStart():
    ParseMisawaInvestmentStartAsync().main("")
    return "OK"

# ==============================================================================
#  APARTMENT ROUTES
# ==============================================================================

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def misawaInvestApartmentStart():
    ParseMisawaInvestmentApartmentStartAsync().main("")
    return "OK"

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_APARTMENT_LIST, methods=['POST', 'GET'])
def misawaInvestApartmentList():
    url = request.json['url']
    ParseMisawaInvestmentApartmentListFuncAsync().main(url)
    return "OK"

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def misawaInvestApartmentDetail():
    url = request.json['url']
    ParseMisawaInvestmentApartmentDetailFuncAsync().main(url)
    return "OK"


# ==============================================================================
#  KODATE ROUTES
# ==============================================================================

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_KODATE_START, methods=['POST', 'GET'])
def misawaInvestKodateStart():
    ParseMisawaInvestmentKodateStartAsync().main("")
    return "OK"

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_KODATE_LIST, methods=['POST', 'GET'])
def misawaInvestKodateList():
    url = request.json['url']
    ParseMisawaInvestmentKodateListFuncAsync().main(url)
    return "OK"

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_KODATE_DETAIL, methods=['POST', 'GET'])
def misawaInvestKodateDetail():
    url = request.json['url']
    ParseMisawaInvestmentKodateDetailFuncAsync().main(url)
    return "OK"

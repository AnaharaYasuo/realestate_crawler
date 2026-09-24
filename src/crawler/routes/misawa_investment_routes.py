
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
def misawa_invest_start():
    ParseMisawaInvestmentStartAsync().main("")
    return "OK"

misawaInvestStart = misawa_invest_start

# ==============================================================================
#  APARTMENT ROUTES
# ==============================================================================

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def misawa_invest_apartment_start():
    ParseMisawaInvestmentApartmentStartAsync().main("")
    return "OK"

misawaInvestApartmentStart = misawa_invest_apartment_start

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_APARTMENT_LIST, methods=['POST', 'GET'])
def misawa_invest_apartment_list():
    url = request.json['url']
    ParseMisawaInvestmentApartmentListFuncAsync().main(url)
    return "OK"

misawaInvestApartmentList = misawa_invest_apartment_list

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def misawa_invest_apartment_detail():
    url = request.json['url']
    ParseMisawaInvestmentApartmentDetailFuncAsync().main(url)
    return "OK"

misawaInvestApartmentDetail = misawa_invest_apartment_detail


# ==============================================================================
#  KODATE ROUTES
# ==============================================================================

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_KODATE_START, methods=['POST', 'GET'])
def misawa_invest_kodate_start():
    ParseMisawaInvestmentKodateStartAsync().main("")
    return "OK"

misawaInvestKodateStart = misawa_invest_kodate_start

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_KODATE_LIST, methods=['POST', 'GET'])
def misawa_invest_kodate_list():
    url = request.json['url']
    ParseMisawaInvestmentKodateListFuncAsync().main(url)
    return "OK"

misawaInvestKodateList = misawa_invest_kodate_list

@misawa_investment_bp.route(API_KEY_MISAWA_INVEST_KODATE_DETAIL, methods=['POST', 'GET'])
def misawa_invest_kodate_detail():
    url = request.json['url']
    ParseMisawaInvestmentKodateDetailFuncAsync().main(url)
    return "OK"

misawaInvestKodateDetail = misawa_invest_kodate_detail

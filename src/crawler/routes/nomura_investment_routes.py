
from flask import Blueprint, request
from package.api.api import \
    API_KEY_NOMURA_INVEST_KODATE_START, API_KEY_NOMURA_INVEST_KODATE_LIST, API_KEY_NOMURA_INVEST_KODATE_DETAIL, \
    API_KEY_NOMURA_INVEST_APARTMENT_START, API_KEY_NOMURA_INVEST_APARTMENT_LIST, API_KEY_NOMURA_INVEST_APARTMENT_DETAIL

from package.api.nomura_investment import \
    ParseNomuraInvestKodateStartAsync, ParseNomuraInvestKodateListFuncAsync, ParseNomuraInvestKodateDetailFuncAsync, \
    ParseNomuraInvestApartmentStartAsync, ParseNomuraInvestApartmentListFuncAsync, ParseNomuraInvestApartmentDetailFuncAsync

nomura_investment_bp = Blueprint('nomura_investment', __name__)

# ==============================================================================
#  KODATE ROUTES
# ==============================================================================

@nomura_investment_bp.route(API_KEY_NOMURA_INVEST_KODATE_START, methods=['POST', 'GET'])
def nomura_invest_kodate_start():
    ParseNomuraInvestKodateStartAsync().main("")
    return "OK"

nomuraInvestKodateStart = nomura_invest_kodate_start

@nomura_investment_bp.route(API_KEY_NOMURA_INVEST_KODATE_LIST, methods=['POST', 'GET'])
def nomura_invest_kodate_list():
    url = request.json['url']
    ParseNomuraInvestKodateListFuncAsync().main(url)
    return "OK"

nomuraInvestKodateList = nomura_invest_kodate_list

@nomura_investment_bp.route(API_KEY_NOMURA_INVEST_KODATE_DETAIL, methods=['POST', 'GET'])
def nomura_invest_kodate_detail():
    url = request.json['url']
    ParseNomuraInvestKodateDetailFuncAsync().main(url)
    return "OK"

nomuraInvestKodateDetail = nomura_invest_kodate_detail

# ==============================================================================
#  APARTMENT ROUTES
# ==============================================================================

@nomura_investment_bp.route(API_KEY_NOMURA_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def nomura_invest_apartment_start():
    ParseNomuraInvestApartmentStartAsync().main("")
    return "OK"

nomuraInvestApartmentStart = nomura_invest_apartment_start

@nomura_investment_bp.route(API_KEY_NOMURA_INVEST_APARTMENT_LIST, methods=['POST', 'GET'])
def nomura_invest_apartment_list():
    url = request.json['url']
    ParseNomuraInvestApartmentListFuncAsync().main(url)
    return "OK"

nomuraInvestApartmentList = nomura_invest_apartment_list

@nomura_investment_bp.route(API_KEY_NOMURA_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def nomura_invest_apartment_detail():
    url = request.json['url']
    ParseNomuraInvestApartmentDetailFuncAsync().main(url)
    return "OK"

nomuraInvestApartmentDetail = nomura_invest_apartment_detail


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
def nomuraInvestKodateStart():
    ParseNomuraInvestKodateStartAsync().main("")
    return "OK"

@nomura_investment_bp.route(API_KEY_NOMURA_INVEST_KODATE_LIST, methods=['POST', 'GET'])
def nomuraInvestKodateList():
    url = request.json['url']
    ParseNomuraInvestKodateListFuncAsync().main(url)
    return "OK"

@nomura_investment_bp.route(API_KEY_NOMURA_INVEST_KODATE_DETAIL, methods=['POST', 'GET'])
def nomuraInvestKodateDetail():
    url = request.json['url']
    ParseNomuraInvestKodateDetailFuncAsync().main(url)
    return "OK"

# ==============================================================================
#  APARTMENT ROUTES
# ==============================================================================

@nomura_investment_bp.route(API_KEY_NOMURA_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def nomuraInvestApartmentStart():
    ParseNomuraInvestApartmentStartAsync().main("")
    return "OK"

@nomura_investment_bp.route(API_KEY_NOMURA_INVEST_APARTMENT_LIST, methods=['POST', 'GET'])
def nomuraInvestApartmentList():
    url = request.json['url']
    ParseNomuraInvestApartmentListFuncAsync().main(url)
    return "OK"

@nomura_investment_bp.route(API_KEY_NOMURA_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def nomuraInvestApartmentDetail():
    url = request.json['url']
    ParseNomuraInvestApartmentDetailFuncAsync().main(url)
    return "OK"

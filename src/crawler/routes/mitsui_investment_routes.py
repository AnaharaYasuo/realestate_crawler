
from flask import Blueprint, request
import json
from package.api.api import \
    API_KEY_MITSUI_INVEST_KODATE_START, API_KEY_MITSUI_INVEST_KODATE_AREA, API_KEY_MITSUI_INVEST_KODATE_LIST, API_KEY_MITSUI_INVEST_KODATE_DETAIL, \
    API_KEY_MITSUI_INVEST_APARTMENT_START, API_KEY_MITSUI_INVEST_APARTMENT_AREA, API_KEY_MITSUI_INVEST_APARTMENT_LIST, API_KEY_MITSUI_INVEST_APARTMENT_DETAIL

from package.api.mitsui_investment import \
    ParseMitsuiInvestKodateStartAsync, ParseMitsuiInvestKodateAreaFuncAsync, ParseMitsuiInvestKodateListFuncAsync, ParseMitsuiInvestKodateDetailFuncAsync, \
    ParseMitsuiInvestApartmentStartAsync, ParseMitsuiInvestApartmentAreaFuncAsync, ParseMitsuiInvestApartmentListFuncAsync, ParseMitsuiInvestApartmentDetailFuncAsync

mitsui_investment_bp = Blueprint('mitsui_investment', __name__)

INVEST_ROOT_URL = "https://www.rehouse.co.jp/buy/tohshi/"

# ==============================================================================
#  KODATE ROUTES
# ==============================================================================

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_KODATE_START, methods=['POST', 'GET'])
def mitsuiInvestKodateStart():
    return ParseMitsuiInvestKodateStartAsync().main(INVEST_ROOT_URL)

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_KODATE_AREA, methods=['POST', 'GET'])
def mitsuiInvestKodateArea():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestKodateAreaFuncAsync().main(url)
    return "finish", 200

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_KODATE_LIST, methods=['POST', 'GET'])
def mitsuiInvestKodateList():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestKodateListFuncAsync().main(url)
    return "finish", 200

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_KODATE_DETAIL, methods=['POST', 'GET'])
def mitsuiInvestKodateDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestKodateDetailFuncAsync().main(url)
    return "finish", 200

# ==============================================================================
#  APARTMENT ROUTES
# ==============================================================================

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def mitsuiInvestApartmentStart():
    return ParseMitsuiInvestApartmentStartAsync().main(INVEST_ROOT_URL)

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_APARTMENT_AREA, methods=['POST', 'GET'])
def mitsuiInvestApartmentArea():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestApartmentAreaFuncAsync().main(url)
    return "finish", 200

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_APARTMENT_LIST, methods=['POST', 'GET'])
def mitsuiInvestApartmentList():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestApartmentListFuncAsync().main(url)
    return "finish", 200

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def mitsuiInvestApartmentDetail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestApartmentDetailFuncAsync().main(url)
    return "finish", 200

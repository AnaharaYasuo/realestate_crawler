
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
def mitsui_invest_kodate_start():
    return ParseMitsuiInvestKodateStartAsync().main(INVEST_ROOT_URL)

mitsuiInvestKodateStart = mitsui_invest_kodate_start

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_KODATE_AREA, methods=['POST', 'GET'])
def mitsui_invest_kodate_area():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestKodateAreaFuncAsync().main(url)
    return "finish", 200

mitsuiInvestKodateArea = mitsui_invest_kodate_area

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_KODATE_LIST, methods=['POST', 'GET'])
def mitsui_invest_kodate_list():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestKodateListFuncAsync().main(url)
    return "finish", 200

mitsuiInvestKodateList = mitsui_invest_kodate_list

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_KODATE_DETAIL, methods=['POST', 'GET'])
def mitsui_invest_kodate_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestKodateDetailFuncAsync().main(url)
    return "finish", 200

mitsuiInvestKodateDetail = mitsui_invest_kodate_detail

# ==============================================================================
#  APARTMENT ROUTES
# ==============================================================================

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def mitsui_invest_apartment_start():
    return ParseMitsuiInvestApartmentStartAsync().main(INVEST_ROOT_URL)

mitsuiInvestApartmentStart = mitsui_invest_apartment_start

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_APARTMENT_AREA, methods=['POST', 'GET'])
def mitsui_invest_apartment_area():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestApartmentAreaFuncAsync().main(url)
    return "finish", 200

mitsuiInvestApartmentArea = mitsui_invest_apartment_area

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_APARTMENT_LIST, methods=['POST', 'GET'])
def mitsui_invest_apartment_list():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestApartmentListFuncAsync().main(url)
    return "finish", 200

mitsuiInvestApartmentList = mitsui_invest_apartment_list

@mitsui_investment_bp.route(API_KEY_MITSUI_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def mitsui_invest_apartment_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseMitsuiInvestApartmentDetailFuncAsync().main(url)
    return "finish", 200

mitsuiInvestApartmentDetail = mitsui_invest_apartment_detail

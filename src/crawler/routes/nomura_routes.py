
from flask import Blueprint, request
from package.api.api import \
    API_KEY_NOMURA_MANSION_START, API_KEY_NOMURA_MANSION_REGION, API_KEY_NOMURA_MANSION_AREA, API_KEY_NOMURA_MANSION_LIST, API_KEY_NOMURA_MANSION_DETAIL, \
    API_KEY_NOMURA_KODATE_START, API_KEY_NOMURA_KODATE_LIST, API_KEY_NOMURA_KODATE_DETAIL, \
    API_KEY_NOMURA_TOCHI_START, API_KEY_NOMURA_TOCHI_LIST, API_KEY_NOMURA_TOCHI_DETAIL

from package.api.nomura import \
    ParseNomuraMansionStartAsync, ParseNomuraMansionRegionFuncAsync, ParseNomuraMansionAreaFuncAsync, ParseNomuraMansionListFuncAsync, ParseNomuraMansionDetailFuncAsync, \
    ParseNomuraKodateStartAsync, ParseNomuraKodateListFuncAsync, ParseNomuraKodateDetailFuncAsync, \
    ParseNomuraTochiStartAsync, ParseNomuraTochiListFuncAsync, ParseNomuraTochiDetailFuncAsync

nomura_bp = Blueprint('nomura', __name__)

# Mansion
@nomura_bp.route(API_KEY_NOMURA_MANSION_START, methods=['POST', 'GET'])
def nomura_mansion_start():
    ParseNomuraMansionStartAsync().main("")
    return "OK"

nomuraMansionStart = nomura_mansion_start

@nomura_bp.route(API_KEY_NOMURA_MANSION_REGION, methods=['POST', 'GET'])
def nomura_mansion_region():
    url = request.json['url']
    ParseNomuraMansionRegionFuncAsync().main(url)
    return "OK"

nomuraMansionRegion = nomura_mansion_region

@nomura_bp.route(API_KEY_NOMURA_MANSION_AREA, methods=['POST', 'GET'])
def nomura_mansion_area():
    url = request.json['url']
    ParseNomuraMansionAreaFuncAsync().main(url)
    return "OK"

nomuraMansionArea = nomura_mansion_area

@nomura_bp.route(API_KEY_NOMURA_MANSION_LIST, methods=['POST', 'GET'])
def nomura_mansion_list():
    url = request.json['url']
    ParseNomuraMansionListFuncAsync().main(url)
    return "OK"

nomuraMansionList = nomura_mansion_list

@nomura_bp.route(API_KEY_NOMURA_MANSION_DETAIL, methods=['POST', 'GET'])
def nomura_mansion_detail():
    url = request.json['url']
    ParseNomuraMansionDetailFuncAsync().main(url)
    return "OK"

nomuraMansionDetail = nomura_mansion_detail

# Kodate
@nomura_bp.route(API_KEY_NOMURA_KODATE_START, methods=['POST', 'GET'])
def nomura_kodate_start():
    ParseNomuraKodateStartAsync().main("")
    return "OK"

nomuraKodateStart = nomura_kodate_start

@nomura_bp.route(API_KEY_NOMURA_KODATE_LIST, methods=['POST', 'GET'])
def nomura_kodate_list():
    url = request.json['url']
    ParseNomuraKodateListFuncAsync().main(url)
    return "OK"

nomuraKodateList = nomura_kodate_list

@nomura_bp.route(API_KEY_NOMURA_KODATE_DETAIL, methods=['POST', 'GET'])
def nomura_kodate_detail():
    url = request.json['url']
    ParseNomuraKodateDetailFuncAsync().main(url)
    return "OK"

nomuraKodateDetail = nomura_kodate_detail

# Tochi
@nomura_bp.route(API_KEY_NOMURA_TOCHI_START, methods=['POST', 'GET'])
def nomura_tochi_start():
    ParseNomuraTochiStartAsync().main("")
    return "OK"

nomuraTochiStart = nomura_tochi_start

@nomura_bp.route(API_KEY_NOMURA_TOCHI_LIST, methods=['POST', 'GET'])
def nomura_tochi_list():
    url = request.json['url']
    ParseNomuraTochiListFuncAsync().main(url)
    return "OK"

nomuraTochiList = nomura_tochi_list

@nomura_bp.route(API_KEY_NOMURA_TOCHI_DETAIL, methods=['POST', 'GET'])
def nomura_tochi_detail():
    url = request.json['url']
    ParseNomuraTochiDetailFuncAsync().main(url)
    return "OK"

nomuraTochiDetail = nomura_tochi_detail


from flask import Blueprint, request
from package.api.api import \
    API_KEY_NOMURA_MANSION_START, API_KEY_NOMURA_MANSION_REGION, API_KEY_NOMURA_MANSION_AREA, API_KEY_NOMURA_MANSION_LIST, API_KEY_NOMURA_MANSION_DETAIL, \
    API_KEY_NOMURA_KODATE_START, API_KEY_NOMURA_KODATE_REGION, API_KEY_NOMURA_KODATE_AREA, API_KEY_NOMURA_KODATE_LIST, API_KEY_NOMURA_KODATE_DETAIL, \
    API_KEY_NOMURA_TOCHI_START, API_KEY_NOMURA_TOCHI_REGION, API_KEY_NOMURA_TOCHI_AREA, API_KEY_NOMURA_TOCHI_LIST, API_KEY_NOMURA_TOCHI_DETAIL

from package.api.nomura import \
    ParseNomuraMansionStartAsync, ParseNomuraMansionRegionFuncAsync, ParseNomuraMansionAreaFuncAsync, ParseNomuraMansionListFuncAsync, ParseNomuraMansionDetailFuncAsync, \
    ParseNomuraKodateStartAsync, ParseNomuraKodateRegionFuncAsync, ParseNomuraKodateAreaFuncAsync, ParseNomuraKodateListFuncAsync, ParseNomuraKodateDetailFuncAsync, \
    ParseNomuraTochiStartAsync, ParseNomuraTochiRegionFuncAsync, ParseNomuraTochiAreaFuncAsync, ParseNomuraTochiListFuncAsync, ParseNomuraTochiDetailFuncAsync

nomura_bp = Blueprint('nomura', __name__)

# Mansion
@nomura_bp.route(API_KEY_NOMURA_MANSION_START, methods=['POST', 'GET'])
def nomuraMansionStart():
    ParseNomuraMansionStartAsync().main("")
    return "OK"

@nomura_bp.route(API_KEY_NOMURA_MANSION_REGION, methods=['POST', 'GET'])
def nomuraMansionRegion():
    url = request.json['url']
    ParseNomuraMansionRegionFuncAsync().main(url)
    return "OK"

@nomura_bp.route(API_KEY_NOMURA_MANSION_AREA, methods=['POST', 'GET'])
def nomuraMansionArea():
    url = request.json['url']
    ParseNomuraMansionAreaFuncAsync().main(url)
    return "OK"

@nomura_bp.route(API_KEY_NOMURA_MANSION_LIST, methods=['POST', 'GET'])
def nomuraMansionList():
    url = request.json['url']
    ParseNomuraMansionListFuncAsync().main(url)
    return "OK"

@nomura_bp.route(API_KEY_NOMURA_MANSION_DETAIL, methods=['POST', 'GET'])
def nomuraMansionDetail():
    url = request.json['url']
    ParseNomuraMansionDetailFuncAsync().main(url)
    return "OK"

# Kodate
@nomura_bp.route(API_KEY_NOMURA_KODATE_START, methods=['POST', 'GET'])
def nomuraKodateStart():
    ParseNomuraKodateStartAsync().main("")
    return "OK"

@nomura_bp.route(API_KEY_NOMURA_KODATE_LIST, methods=['POST', 'GET'])
def nomuraKodateList():
    url = request.json['url']
    ParseNomuraKodateListFuncAsync().main(url)
    return "OK"

@nomura_bp.route(API_KEY_NOMURA_KODATE_DETAIL, methods=['POST', 'GET'])
def nomuraKodateDetail():
    url = request.json['url']
    ParseNomuraKodateDetailFuncAsync().main(url)
    return "OK"

# Tochi
@nomura_bp.route(API_KEY_NOMURA_TOCHI_START, methods=['POST', 'GET'])
def nomuraTochiStart():
    ParseNomuraTochiStartAsync().main("")
    return "OK"

@nomura_bp.route(API_KEY_NOMURA_TOCHI_LIST, methods=['POST', 'GET'])
def nomuraTochiList():
    url = request.json['url']
    ParseNomuraTochiListFuncAsync().main(url)
    return "OK"

@nomura_bp.route(API_KEY_NOMURA_TOCHI_DETAIL, methods=['POST', 'GET'])
def nomuraTochiDetail():
    url = request.json['url']
    ParseNomuraTochiDetailFuncAsync().main(url)
    return "OK"

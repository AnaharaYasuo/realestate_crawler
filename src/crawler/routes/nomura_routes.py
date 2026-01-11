from flask import Blueprint, request
from package.api.api import API_KEY_NOMURA_PRO_START, API_KEY_NOMURA_PRO_LIST, API_KEY_NOMURA_PRO_DETAIL
from package.api.nomura import ParseNomuraProStartAsync, ParseNomuraProListFuncAsync, ParseNomuraProDetailFuncAsync

nomura_bp = Blueprint('nomura', __name__)

@nomura_bp.route(API_KEY_NOMURA_PRO_START, methods=['POST', 'GET'])
def nomuraProStart():
    ParseNomuraProStartAsync().main("")
    return "OK"

@nomura_bp.route(API_KEY_NOMURA_PRO_LIST, methods=['POST', 'GET'])
def nomuraProList():
    url = request.json['url']
    ParseNomuraProListFuncAsync().main(url)
    return "OK"

@nomura_bp.route(API_KEY_NOMURA_PRO_DETAIL, methods=['POST', 'GET'])
def nomuraProDetail():
    url = request.json['url']
    ParseNomuraProDetailFuncAsync().main(url)
    return "OK"

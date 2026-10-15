import json

from flask import Blueprint, request
from package.api.api import (
    API_KEY_REGUIDE_INVESTMENT_DETAIL,
    API_KEY_REGUIDE_INVESTMENT_START,
)
from package.api.reguide import (
    ParseReguideInvestmentDetailFuncAsync,
    ParseReguideInvestmentStartAsync,
)

reguide_bp = Blueprint('reguide', __name__)

REGUIDE_INVESTMENT_ROOT_URL = "https://re-guide.jp/investment/list/"


@reguide_bp.route(API_KEY_REGUIDE_INVESTMENT_START, methods=['POST', 'GET'])
def reguide_investment_start():
    return ParseReguideInvestmentStartAsync().main(REGUIDE_INVESTMENT_ROOT_URL)


reguideInvestmentStart = reguide_investment_start


@reguide_bp.route(API_KEY_REGUIDE_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def reguide_investment_detail():
    request_json = json.loads(request.get_json())
    url = request_json['url']
    ParseReguideInvestmentDetailFuncAsync().main(url)
    return "finish", 200


reguideInvestmentDetail = reguide_investment_detail

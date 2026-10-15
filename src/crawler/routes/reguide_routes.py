import json
import re
import urllib.parse

from flask import Blueprint, abort, request
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
REGUIDE_DETAIL_URL_PATTERN = re.compile(r"^https://re-guide\.jp/investment/\d+/?$")


def _is_valid_reguide_detail_url(url: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "re-guide.jp":
        return False
    return bool(REGUIDE_DETAIL_URL_PATTERN.match(url))


@reguide_bp.route(API_KEY_REGUIDE_INVESTMENT_START, methods=['POST', 'GET'])
def reguide_investment_start():
    return ParseReguideInvestmentStartAsync().main(REGUIDE_INVESTMENT_ROOT_URL)


reguideInvestmentStart = reguide_investment_start


@reguide_bp.route(API_KEY_REGUIDE_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def reguide_investment_detail():
    data = request.get_json(silent=True)
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        abort(400, description="Invalid request body")
    url = data.get('url')
    if not url or not _is_valid_reguide_detail_url(url):
        abort(400, description="Invalid or unauthorized detail url")
    ParseReguideInvestmentDetailFuncAsync().main(url)
    return "finish", 200


reguideInvestmentDetail = reguide_investment_detail


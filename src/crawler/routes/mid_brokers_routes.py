import json

from flask import Blueprint, request
from package.api.api import (
    API_KEY_ADCAST_KODATE_DETAIL,
    API_KEY_ADCAST_TOCHI_DETAIL,
    API_KEY_HASEKO_MANSION_DETAIL,
    API_KEY_IETAN_KODATE_DETAIL,
    API_KEY_IETAN_MANSION_DETAIL,
    API_KEY_IETAN_TOCHI_DETAIL,
    API_KEY_TOHO_KODATE_DETAIL,
    API_KEY_TOHO_MANSION_DETAIL,
    API_KEY_TOHO_TOCHI_DETAIL,
)
from package.api.mid_brokers import (
    ParseAdCastKodateDetailFuncAsync,
    ParseAdCastTochiDetailFuncAsync,
    ParseHasekoMansionDetailFuncAsync,
    ParseIetanKodateDetailFuncAsync,
    ParseIetanMansionDetailFuncAsync,
    ParseIetanTochiDetailFuncAsync,
    ParseTohoKodateDetailFuncAsync,
    ParseTohoMansionDetailFuncAsync,
    ParseTohoTochiDetailFuncAsync,
)

mid_brokers_bp = Blueprint('mid_brokers', __name__)

def _handle_detail(parser_async_cls):
    request_json = json.loads(request.get_json())
    url = request_json['url']
    parser_async_cls().main(url)
    return "finish", 200

# --- Ietan Detail Routes ---
@mid_brokers_bp.route(API_KEY_IETAN_MANSION_DETAIL, methods=['POST', 'GET'])
def ietan_mansion_detail(): return _handle_detail(ParseIetanMansionDetailFuncAsync)

@mid_brokers_bp.route(API_KEY_IETAN_KODATE_DETAIL, methods=['POST', 'GET'])
def ietan_kodate_detail(): return _handle_detail(ParseIetanKodateDetailFuncAsync)

@mid_brokers_bp.route(API_KEY_IETAN_TOCHI_DETAIL, methods=['POST', 'GET'])
def ietan_tochi_detail(): return _handle_detail(ParseIetanTochiDetailFuncAsync)

# --- Haseko Detail Routes ---
@mid_brokers_bp.route(API_KEY_HASEKO_MANSION_DETAIL, methods=['POST', 'GET'])
def haseko_mansion_detail(): return _handle_detail(ParseHasekoMansionDetailFuncAsync)

# --- AdCast Detail Routes ---
@mid_brokers_bp.route(API_KEY_ADCAST_KODATE_DETAIL, methods=['POST', 'GET'])
def adcast_kodate_detail(): return _handle_detail(ParseAdCastKodateDetailFuncAsync)

@mid_brokers_bp.route(API_KEY_ADCAST_TOCHI_DETAIL, methods=['POST', 'GET'])
def adcast_tochi_detail(): return _handle_detail(ParseAdCastTochiDetailFuncAsync)

# --- Toho Detail Routes ---
@mid_brokers_bp.route(API_KEY_TOHO_MANSION_DETAIL, methods=['POST', 'GET'])
def toho_mansion_detail(): return _handle_detail(ParseTohoMansionDetailFuncAsync)

@mid_brokers_bp.route(API_KEY_TOHO_KODATE_DETAIL, methods=['POST', 'GET'])
def toho_kodate_detail(): return _handle_detail(ParseTohoKodateDetailFuncAsync)

@mid_brokers_bp.route(API_KEY_TOHO_TOCHI_DETAIL, methods=['POST', 'GET'])
def toho_tochi_detail(): return _handle_detail(ParseTohoTochiDetailFuncAsync)

import json

from flask import Blueprint, request
from package.api.api import (
    API_KEY_ADCAST_KODATE_DETAIL,
    API_KEY_ADCAST_KODATE_START,
    API_KEY_ADCAST_TOCHI_DETAIL,
    API_KEY_ADCAST_TOCHI_START,
    API_KEY_HASEKO_MANSION_DETAIL,
    API_KEY_HASEKO_MANSION_START,
    API_KEY_IETAN_KODATE_DETAIL,
    API_KEY_IETAN_KODATE_START,
    API_KEY_IETAN_MANSION_DETAIL,
    API_KEY_IETAN_MANSION_START,
    API_KEY_IETAN_TOCHI_DETAIL,
    API_KEY_IETAN_TOCHI_START,
    API_KEY_TOHO_KODATE_DETAIL,
    API_KEY_TOHO_KODATE_START,
    API_KEY_TOHO_MANSION_DETAIL,
    API_KEY_TOHO_MANSION_START,
    API_KEY_TOHO_TOCHI_DETAIL,
    API_KEY_TOHO_TOCHI_START,
)
from package.api.mid_brokers import (
    ParseAdCastKodateDetailFuncAsync,
    ParseAdCastKodateStartAsync,
    ParseAdCastTochiDetailFuncAsync,
    ParseAdCastTochiStartAsync,
    ParseHasekoMansionDetailFuncAsync,
    ParseHasekoMansionStartAsync,
    ParseIetanKodateDetailFuncAsync,
    ParseIetanKodateStartAsync,
    ParseIetanMansionDetailFuncAsync,
    ParseIetanMansionStartAsync,
    ParseIetanTochiDetailFuncAsync,
    ParseIetanTochiStartAsync,
    ParseTohoKodateDetailFuncAsync,
    ParseTohoKodateStartAsync,
    ParseTohoMansionDetailFuncAsync,
    ParseTohoMansionStartAsync,
    ParseTohoTochiDetailFuncAsync,
    ParseTohoTochiStartAsync,
)

mid_brokers_bp = Blueprint('mid_brokers', __name__)

def _handle_detail(parser_async_cls):
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    parser_async_cls().main(url)
    return "finish", 200

# --- Ietan Routes ---
@mid_brokers_bp.route(API_KEY_IETAN_MANSION_START, methods=['POST', 'GET'])
def ietan_mansion_start():
    return ParseIetanMansionStartAsync().main("https://www.ietan.jp/mansion/tokyo/list/cc_13100")
ietanMansionStart = ietan_mansion_start

@mid_brokers_bp.route(API_KEY_IETAN_MANSION_DETAIL, methods=['POST', 'GET'])
def ietan_mansion_detail(): return _handle_detail(ParseIetanMansionDetailFuncAsync)
ietanMansionDetail = ietan_mansion_detail

@mid_brokers_bp.route(API_KEY_IETAN_KODATE_START, methods=['POST', 'GET'])
def ietan_kodate_start():
    return ParseIetanKodateStartAsync().main("https://www.ietan.jp/kodate/tokyo/list/cc_13100")
ietanKodateStart = ietan_kodate_start

@mid_brokers_bp.route(API_KEY_IETAN_KODATE_DETAIL, methods=['POST', 'GET'])
def ietan_kodate_detail(): return _handle_detail(ParseIetanKodateDetailFuncAsync)
ietanKodateDetail = ietan_kodate_detail

@mid_brokers_bp.route(API_KEY_IETAN_TOCHI_START, methods=['POST', 'GET'])
def ietan_tochi_start():
    return ParseIetanTochiStartAsync().main("https://www.ietan.jp/land/tokyo/list/cc_13100")
ietanTochiStart = ietan_tochi_start

@mid_brokers_bp.route(API_KEY_IETAN_TOCHI_DETAIL, methods=['POST', 'GET'])
def ietan_tochi_detail(): return _handle_detail(ParseIetanTochiDetailFuncAsync)
ietanTochiDetail = ietan_tochi_detail

# --- Haseko Routes ---
@mid_brokers_bp.route(API_KEY_HASEKO_MANSION_START, methods=['POST', 'GET'])
def haseko_mansion_start():
    return ParseHasekoMansionStartAsync().main("https://www.haseko-chukai.com/syutoken-buy/mansion/areas/tokyoto/")
hasekoMansionStart = haseko_mansion_start

@mid_brokers_bp.route(API_KEY_HASEKO_MANSION_DETAIL, methods=['POST', 'GET'])
def haseko_mansion_detail(): return _handle_detail(ParseHasekoMansionDetailFuncAsync)
hasekoMansionDetail = haseko_mansion_detail

# --- AdCast Routes ---
@mid_brokers_bp.route(API_KEY_ADCAST_KODATE_START, methods=['POST', 'GET'])
def adcast_kodate_start():
    return ParseAdCastKodateStartAsync().main("https://www.ad-cast.info/sch/list.php?kind=2")
adcastKodateStart = adcast_kodate_start

@mid_brokers_bp.route(API_KEY_ADCAST_KODATE_DETAIL, methods=['POST', 'GET'])
def adcast_kodate_detail(): return _handle_detail(ParseAdCastKodateDetailFuncAsync)
adcastKodateDetail = adcast_kodate_detail

@mid_brokers_bp.route(API_KEY_ADCAST_TOCHI_START, methods=['POST', 'GET'])
def adcast_tochi_start():
    return ParseAdCastTochiStartAsync().main("https://www.ad-cast.info/sch/list.php?kind=1")
adcastTochiStart = adcast_tochi_start

@mid_brokers_bp.route(API_KEY_ADCAST_TOCHI_DETAIL, methods=['POST', 'GET'])
def adcast_tochi_detail(): return _handle_detail(ParseAdCastTochiDetailFuncAsync)
adcastTochiDetail = adcast_tochi_detail

# --- Toho Routes ---
@mid_brokers_bp.route(API_KEY_TOHO_MANSION_START, methods=['POST', 'GET'])
def toho_mansion_start():
    return ParseTohoMansionStartAsync().main("https://th-yokohama.com/estates/index?div=2&page=1")
tohoMansionStart = toho_mansion_start

@mid_brokers_bp.route(API_KEY_TOHO_MANSION_DETAIL, methods=['POST', 'GET'])
def toho_mansion_detail(): return _handle_detail(ParseTohoMansionDetailFuncAsync)
tohoMansionDetail = toho_mansion_detail

@mid_brokers_bp.route(API_KEY_TOHO_KODATE_START, methods=['POST', 'GET'])
def toho_kodate_start():
    return ParseTohoKodateStartAsync().main("https://th-yokohama.com/estates/index?div=1&page=1")
tohoKodateStart = toho_kodate_start

@mid_brokers_bp.route(API_KEY_TOHO_KODATE_DETAIL, methods=['POST', 'GET'])
def toho_kodate_detail(): return _handle_detail(ParseTohoKodateDetailFuncAsync)
tohoKodateDetail = toho_kodate_detail

@mid_brokers_bp.route(API_KEY_TOHO_TOCHI_START, methods=['POST', 'GET'])
def toho_tochi_start():
    return ParseTohoTochiStartAsync().main("https://th-yokohama.com/estates/index?div=3&page=1")
tohoTochiStart = toho_tochi_start

@mid_brokers_bp.route(API_KEY_TOHO_TOCHI_DETAIL, methods=['POST', 'GET'])
def toho_tochi_detail(): return _handle_detail(ParseTohoTochiDetailFuncAsync)
tohoTochiDetail = toho_tochi_detail

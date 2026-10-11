import json

from flask import Blueprint, request
from package.api.api import (
    API_KEY_KENBIYA_INVEST_APARTMENT_DETAIL,
    API_KEY_KENBIYA_INVEST_APARTMENT_START,
    API_KEY_KENBIYA_INVEST_BUILDING_DETAIL,
    API_KEY_KENBIYA_INVEST_BUILDING_START,
    API_KEY_KENBIYA_KODATE_DETAIL,
    API_KEY_KENBIYA_KODATE_START,
    API_KEY_KENBIYA_MANSION_DETAIL,
    API_KEY_KENBIYA_MANSION_START,
    API_KEY_KENBIYA_TOCHI_DETAIL,
    API_KEY_KENBIYA_TOCHI_START,
)
from package.api.kenbiya import (
    ParseKenbiyaInvestApartmentDetailFuncAsync,
    ParseKenbiyaInvestApartmentStartAsync,
    ParseKenbiyaInvestBuildingDetailFuncAsync,
    ParseKenbiyaInvestBuildingStartAsync,
    ParseKenbiyaKodateDetailFuncAsync,
    ParseKenbiyaKodateStartAsync,
    ParseKenbiyaMansionDetailFuncAsync,
    ParseKenbiyaMansionStartAsync,
    ParseKenbiyaTochiDetailFuncAsync,
    ParseKenbiyaTochiStartAsync,
)

kenbiya_bp = Blueprint('kenbiya', __name__)

def _handle_detail(parser_async_cls):
    request_json = request.get_json()
    if isinstance(request_json, str):
        request_json = json.loads(request_json)
    url = request_json['url']
    parser_async_cls().main(url)
    return "finish", 200

# --- Mansion (/pp1/) ---
@kenbiya_bp.route(API_KEY_KENBIYA_MANSION_START, methods=['POST', 'GET'])
def kenbiya_mansion_start():
    # 健美家 区分マンション (東京都)
    return ParseKenbiyaMansionStartAsync().main("https://www.kenbiya.com/pp1/s/tokyo/")

kenbiyaMansionStart = kenbiya_mansion_start

@kenbiya_bp.route(API_KEY_KENBIYA_MANSION_DETAIL, methods=['POST', 'GET'])
def kenbiya_mansion_detail(): return _handle_detail(ParseKenbiyaMansionDetailFuncAsync)
kenbiyaMansionDetail = kenbiya_mansion_detail

# --- Kodate (/pp8/) ---
@kenbiya_bp.route(API_KEY_KENBIYA_KODATE_START, methods=['POST', 'GET'])
def kenbiya_kodate_start():
    # 健美家 戸建賃貸 (東京都)
    return ParseKenbiyaKodateStartAsync().main("https://www.kenbiya.com/pp8/s/tokyo/")

kenbiyaKodateStart = kenbiya_kodate_start

@kenbiya_bp.route(API_KEY_KENBIYA_KODATE_DETAIL, methods=['POST', 'GET'])
def kenbiya_kodate_detail(): return _handle_detail(ParseKenbiyaKodateDetailFuncAsync)
kenbiyaKodateDetail = kenbiya_kodate_detail

# --- Tochi (/pp5/) ---
@kenbiya_bp.route(API_KEY_KENBIYA_TOCHI_START, methods=['POST', 'GET'])
def kenbiya_tochi_start():
    # 健美家 土地 (東京都)
    return ParseKenbiyaTochiStartAsync().main("https://www.kenbiya.com/pp5/s/tokyo/")

kenbiyaTochiStart = kenbiya_tochi_start

@kenbiya_bp.route(API_KEY_KENBIYA_TOCHI_DETAIL, methods=['POST', 'GET'])
def kenbiya_tochi_detail(): return _handle_detail(ParseKenbiyaTochiDetailFuncAsync)
kenbiyaTochiDetail = kenbiya_tochi_detail

# --- Invest Apartment (/pp2/) ---
@kenbiya_bp.route(API_KEY_KENBIYA_INVEST_APARTMENT_START, methods=['POST', 'GET'])
def kenbiya_invest_apartment_start():
    # 健美家 一棟アパート (東京都)
    return ParseKenbiyaInvestApartmentStartAsync().main("https://www.kenbiya.com/pp2/s/tokyo/")

kenbiyaInvestApartmentStart = kenbiya_invest_apartment_start

@kenbiya_bp.route(API_KEY_KENBIYA_INVEST_APARTMENT_DETAIL, methods=['POST', 'GET'])
def kenbiya_invest_apartment_detail(): return _handle_detail(ParseKenbiyaInvestApartmentDetailFuncAsync)
kenbiyaInvestApartmentDetail = kenbiya_invest_apartment_detail

# --- Invest Building (/pp3/, /pp4/) ---
@kenbiya_bp.route(API_KEY_KENBIYA_INVEST_BUILDING_START, methods=['POST', 'GET'])
def kenbiya_invest_building_start():
    # 健美家 一棟マンション・ビル (東京都)
    return ParseKenbiyaInvestBuildingStartAsync().main("https://www.kenbiya.com/pp3/s/tokyo/")

kenbiyaInvestBuildingStart = kenbiya_invest_building_start

@kenbiya_bp.route(API_KEY_KENBIYA_INVEST_BUILDING_DETAIL, methods=['POST', 'GET'])
def kenbiya_invest_building_detail(): return _handle_detail(ParseKenbiyaInvestBuildingDetailFuncAsync)
kenbiyaInvestBuildingDetail = kenbiya_invest_building_detail

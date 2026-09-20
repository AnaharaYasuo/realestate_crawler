from flask import Blueprint, request
import json
from package.api.api import API_KEY_MIZUHO_MANSION_START, API_KEY_MIZUHO_MANSION_DETAIL, API_KEY_MIZUHO_KODATE_START, API_KEY_MIZUHO_KODATE_DETAIL, API_KEY_MIZUHO_TOCHI_START, API_KEY_MIZUHO_TOCHI_DETAIL, API_KEY_MIZUHO_INVESTMENT_START, API_KEY_MIZUHO_INVESTMENT_DETAIL
from package.api.mizuho import ParseMizuhoMansionStartAsync, ParseMizuhoMansionDetailFuncAsync, ParseMizuhoKodateStartAsync, ParseMizuhoKodateDetailFuncAsync, ParseMizuhoTochiStartAsync, ParseMizuhoTochiDetailFuncAsync, ParseMizuhoInvestmentStartAsync, ParseMizuhoInvestmentDetailFuncAsync
mizuho_bp = Blueprint('mizuho', __name__)

def get_start_url(property_type='Mansion'):
    """みずほ不動産販売の指定種別における東京都全域スタートURLを取得する。"""
    return f'https://www.mizuho-re.co.jp/buyers/search/area/type_{property_type}/pref_13/list/'

@mizuho_bp.route(API_KEY_MIZUHO_MANSION_START, methods=['POST', 'GET'])
def mizuhoMansionStart():
    """みずほマンション一覧クローリング開始エンドポイント。"""
    return ParseMizuhoMansionStartAsync().main(get_start_url('Mansion'))

@mizuho_bp.route(API_KEY_MIZUHO_MANSION_DETAIL, methods=['POST', 'GET'])
def mizuhoMansionDetail():
    """みずほマンション詳細クローリングエンドポイント。"""
    req_data = request.get_json()
    request_json = json.loads(req_data) if isinstance(req_data, str) else req_data
    url = request_json['url']
    ParseMizuhoMansionDetailFuncAsync().main(url)
    return ('finish', 200)

@mizuho_bp.route(API_KEY_MIZUHO_KODATE_START, methods=['POST', 'GET'])
def mizuhoKodateStart():
    """みずほ戸建て一覧クローリング開始エンドポイント。"""
    return ParseMizuhoKodateStartAsync().main(get_start_url('House'))

@mizuho_bp.route(API_KEY_MIZUHO_KODATE_DETAIL, methods=['POST', 'GET'])
def mizuhoKodateDetail():
    """みずほ戸建て詳細クローリングエンドポイント。"""
    req_data = request.get_json()
    request_json = json.loads(req_data) if isinstance(req_data, str) else req_data
    url = request_json['url']
    ParseMizuhoKodateDetailFuncAsync().main(url)
    return ('finish', 200)

@mizuho_bp.route(API_KEY_MIZUHO_TOCHI_START, methods=['POST', 'GET'])
def mizuhoTochiStart():
    """みずほ土地一覧クローリング開始エンドポイント。"""
    return ParseMizuhoTochiStartAsync().main(get_start_url('Land'))

@mizuho_bp.route(API_KEY_MIZUHO_TOCHI_DETAIL, methods=['POST', 'GET'])
def mizuhoTochiDetail():
    """みずほ土地詳細クローリングエンドポイント。"""
    req_data = request.get_json()
    request_json = json.loads(req_data) if isinstance(req_data, str) else req_data
    url = request_json['url']
    ParseMizuhoTochiDetailFuncAsync().main(url)
    return ('finish', 200)

@mizuho_bp.route(API_KEY_MIZUHO_INVESTMENT_START, methods=['POST', 'GET'])
def mizuhoInvestmentStart():
    """みずほ投資用物件一覧クローリング開始エンドポイント。"""
    return ParseMizuhoInvestmentStartAsync().main('https://www.mizuho-re.co.jp/investors/search/area/all_apartment-building-dormitory-office-store-warehouse-factory-land-other/pref_13/list/')

@mizuho_bp.route(API_KEY_MIZUHO_INVESTMENT_DETAIL, methods=['POST', 'GET'])
def mizuhoInvestmentDetail():
    """みずほ投資用物件詳細クローリングエンドポイント。"""
    req_data = request.get_json()
    request_json = json.loads(req_data) if isinstance(req_data, str) else req_data
    url = request_json['url']
    ParseMizuhoInvestmentDetailFuncAsync().main(url)
    return ('finish', 200)
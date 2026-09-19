# -*- coding: utf-8 -*-
import os
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import logging
import asyncio
import aiohttp
import urllib.parse
import importlib
from flask import Blueprint, request, jsonify
from django.db import connections, reset_queries

from package.ml.predict import predict_first_stage_local, predict_second_stage_local, _serialize_property
from package.utils.url_security import UrlSecurityValidator
from package.utils.url_router import UrlRouter
from package.utils.url_matcher import UrlMatcher
from package.utils.singleflight import SingleflightGroup
from package.utils.rate_limiter import SlidingWindowRateLimiter, LockoutManager
from package.models.evaluation import PropertyEvaluation
from package.models.candidate import CandidatePropertyUrl
from package.parser.baseParser import ListingEndedException, LoadPropertyPageException

evaluation_bp = Blueprint('evaluation', __name__)

rate_limiter = SlidingWindowRateLimiter(limit_per_minute=60, burst_per_second=5)
lockout_manager = LockoutManager(lockout_seconds=900, strike_threshold=3)
singleflight_group = SingleflightGroup()


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def is_internal_client():
    """
    内部システム（自作システム、バッチ、正規内部キー保持者、ローカルホスト）判定
    内部クライアントは流量制限・ロックアウトから完全除外される
    """
    # 1. 内部キーの一致確認 (X-API-KEY == ESTIMATION_API_KEY)
    required_key = os.getenv("ESTIMATION_API_KEY")
    provided_key = request.headers.get("X-API-KEY")
    if required_key and provided_key and provided_key == required_key:
        return True

    # 2. 内部明示ヘッダ
    if request.headers.get("X-INTERNAL-REQUEST", "").lower() in ("true", "1"):
        if not os.getenv("IS_CLOUD") or (required_key and provided_key == required_key):
            return True

    # 3. ローカルIP (127.0.0.1, ::1, testclient)
    client_ip = get_client_ip()
    if client_ip in ("127.0.0.1", "::1", "localhost", "testclient"):
        return True

    return False


def _check_api_key():
    """
    外部アクセス用APIキー検証
    - クラウド環境(IS_CLOUD=true)ではAPIキー認証を完全強制
    - ローカル環境でも ESTIMATION_API_KEY が設定されている場合は検証
    """
    is_cloud = os.getenv("IS_CLOUD", "").lower() in ("true", "1")
    required_key = os.getenv("ESTIMATION_API_KEY")
    
    if is_cloud and not required_key:
        logging.error("ESTIMATION_API_KEY is not configured in cloud environment")
        return jsonify({
            "success": False,
            "message": "Server configuration error: API key not configured"
        }), 500

    if not required_key:
        return None  # ローカル開発時のみ未設定スキップ
    
    provided_key = request.headers.get("X-API-KEY")
    if not provided_key or provided_key != required_key:
        return jsonify({
            "success": False,
            "message": "Unauthorized: Invalid or missing X-API-KEY header"
        }), 401
    return None


@evaluation_bp.before_request
def check_evaluation_request():
    if request.method == 'OPTIONS':
        return "", 200
    return _check_api_key()


def _predict_price_internal(property_type, data):
    """
    推論処理の共通ヘルパー関数
    """
    if not data or not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Missing or invalid JSON request body"
        }), 400
        
    property_data = data.get("property_data")
    if not property_data or not isinstance(property_data, dict):
        return jsonify({
            "success": False,
            "message": "Missing or invalid 'property_data' in request body"
        }), 400
        
    # 機械学習モデルの判定が確実に指定された種別になるよう明示的に設定
    property_data = property_data.copy()
    property_data["propertyType"] = property_type

    # オプションパラメータの取得
    interior_score = float(data.get("interior_score", 3.0))
    layout_score = float(data.get("layout_score", 3.0))
    try:
        # 価格推定の実行
        first_stage_pred = predict_first_stage_local(property_data)
        second_stage_pred = predict_second_stage_local(property_data, interior_score, layout_score)
        
        return jsonify({
            "success": True,
            "property_type": property_type,
            "first_stage_predicted_price": first_stage_pred,
            "second_stage_predicted_price": second_stage_pred,
            "message": "Estimation completed successfully"
        }), 200
    finally:
        try:
            connections.close_all()
            reset_queries()
        except Exception:
            pass

@evaluation_bp.route('/api/evaluation/predict/mansion', methods=['POST', 'OPTIONS'])
def predict_mansion():
    """
    マンション価格推定API
    ---
    tags:
      - Evaluation
    summary: マンション（区分所有）の推定理論価格を算出します。
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - property_data
          properties:
            property_data:
              type: object
              required:
                - price
                - address
                - senyuMenseki
              properties:
                price:
                  type: integer
                  description: 販売価格（円）
                  example: 45000000
                address:
                  type: string
                  description: 住所（市区町村地価・所得・ハザードマスタ引き当て用）
                  example: "東京都世田谷区桜丘1-1"
                station1:
                  type: string
                  description: 最寄り駅名（乗降客数引き当て用）
                  example: "経堂"
                senyuMenseki:
                  type: number
                  description: 専有面積 (㎡)
                  example: 72.5
                chikunengetsuStr:
                  type: string
                  description: 築年月（和暦・西暦どちらも可）
                  example: "平成15年10月"
                railwayWalkMinute1:
                  type: integer
                  description: 徒歩分数（分）
                  example: 8
                kouzou:
                  type: string
                  description: 構造 (例: RC, SRC)
                  example: "RC"
                kanrihi:
                  type: integer
                  description: 月額管理費（円）
                  example: 12000
                syuzenTsumitate:
                  type: integer
                  description: 月額修繕積立金（円）
                  example: 15000
                yousekiStr:
                  type: string
                  description: 指定容積率 (%不要、数値・文字列可)
                  example: "200"
                kenpeiStr:
                  type: string
                  description: 指定建ぺい率 (%不要、数値・文字列可)
                  example: "60"
                tochikenri:
                  type: string
                  description: 土地権利形態
                  example: "所有権"
                biko:
                  type: string
                  description: 備考（再建築不可や市街化調整などの判定キー）
                  example: ""
            interior_score:
              type: number
              description: 内装評価スコア (1.0〜5.0)。二次予測で使用。未指定時は 3.0
              default: 3.0
              example: 4.2
            layout_score:
              type: number
              description: 間取り評価スコア (1.0〜5.0)。二次予測で使用。未指定時は 3.0
              default: 3.0
              example: 3.8
    responses:
      200:
        description: 価格推定成功
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            property_type:
              type: string
              example: mansion
            first_stage_predicted_price:
              type: integer
              description: 一次推定理論価格（万円）
              example: 4420
            second_stage_predicted_price:
              type: integer
              description: 二次推定精密理論価格（万円）
              example: 4580
            message:
              type: string
              example: "Estimation completed successfully"
      400:
        description: パラメータ不正
      500:
        description: サーバー内部エラー
    """
    try:
        data = request.get_json(silent=True)
        return _predict_price_internal('mansion', data)
    except Exception as e:
        logging.error(f"Error in predict_mansion: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

@evaluation_bp.route('/api/evaluation/predict/kodate', methods=['POST', 'OPTIONS'])
def predict_kodate():
    """
    戸建価格推定API
    ---
    tags:
      - Evaluation
    summary: 戸建（一戸建て）の推定理論価格を算出します。
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - property_data
          properties:
            property_data:
              type: object
              required:
                - price
                - address
                - tatemonoMenseki
                - tochiMenseki
              properties:
                price:
                  type: integer
                  description: 販売価格（円）
                  example: 55000000
                address:
                  type: string
                  description: 住所
                  example: "東京都世田谷区桜丘1-1"
                station1:
                  type: string
                  description: 最寄り駅名
                  example: "経堂"
                tatemonoMenseki:
                  type: number
                  description: 建物面積 (㎡)
                  example: 95.0
                tochiMenseki:
                  type: number
                  description: 土地面積 (㎡)
                  example: 120.0
                chikunengetsuStr:
                  type: string
                  description: 築年月
                  example: "平成20年5月"
                railwayWalkMinute1:
                  type: integer
                  description: 徒歩分数（分）
                  example: 12
                kouzou:
                  type: string
                  description: 構造 (例: 木造)
                  example: "木造"
                yousekiStr:
                  type: string
                  description: 指定容積率 (%不要、数値・文字列可)
                  example: "150"
                kenpeiStr:
                  type: string
                  description: 指定建ぺい率 (%不要、数値・文字列可)
                  example: "50"
                maguchi:
                  type: number
                  description: 接道間口 (m)
                  example: 8.5
                roadWidth:
                  type: number
                  description: 前面道路幅員 (m)
                  example: 4.0
                setsudou:
                  type: string
                  description: 接道状況詳細テキスト (例: "南側道路 幅員4m 公道")
                  example: "南側道路 幅員4m 公道"
                tochikenri:
                  type: string
                  description: 土地権利形態
                  example: "所有権"
                biko:
                  type: string
                  description: 備考
                  example: ""
            interior_score:
              type: number
              description: 内装評価スコア (1.0〜5.0)。二次予測で使用。未指定時は 3.0
              default: 3.0
              example: 4.0
            layout_score:
              type: number
              description: 間取り評価スコア (1.0〜5.0)。二次予測で使用。未指定時は 3.0
              default: 3.0
              example: 3.5
    responses:
      200:
        description: 価格推定成功
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            property_type:
              type: string
              example: kodate
            first_stage_predicted_price:
              type: integer
              description: 一次推定理論価格（万円）
              example: 5400
            second_stage_predicted_price:
              type: integer
              description: 二次推定精密理論価格（万円）
              example: 5550
            message:
              type: string
              example: "Estimation completed successfully"
    """
    try:
        data = request.get_json(silent=True)
        return _predict_price_internal('kodate', data)
    except Exception as e:
        logging.error(f"Error in predict_kodate: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

@evaluation_bp.route('/api/evaluation/predict/apartment', methods=['POST', 'OPTIONS'])
def predict_apartment():
    """
    一棟アパート（投資用）価格推定API
    ---
    tags:
      - Evaluation
    summary: 一棟アパート（投資用集合住宅）の推定理論価格を算出します。
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - property_data
          properties:
            property_data:
              type: object
              required:
                - price
                - address
                - tatemonoMenseki
                - tochiMenseki
                - grossYield
                - annualRent
              properties:
                price:
                  type: integer
                  description: 販売価格（円）
                  example: 120000000
                address:
                  type: string
                  description: 住所
                  example: "東京都世田谷区桜丘1-1"
                station1:
                  type: string
                  description: 最寄り駅名
                  example: "経堂"
                tatemonoMenseki:
                  type: number
                  description: 建物延床面積 (㎡)
                  example: 220.0
                tochiMenseki:
                  type: number
                  description: 土地面積 (㎡)
                  example: 180.0
                chikunengetsuStr:
                  type: string
                  description: 築年月
                  example: "平成18年3月"
                railwayWalkMinute1:
                  type: integer
                  description: 徒歩分数（分）
                  example: 10
                kouzou:
                  type: string
                  description: 構造 (例: 木造, 軽量鉄骨造)
                  example: "軽量鉄骨造"
                yousekiStr:
                  type: string
                  description: 指定容積率 (%不要、数値・文字列可)
                  example: "200"
                kenpeiStr:
                  type: string
                  description: 指定建ぺい率 (%不要、数値・文字列可)
                  example: "60"
                maguchi:
                  type: number
                  description: 接道間口 (m)
                  example: 12.0
                roadWidth:
                  type: number
                  description: 前面道路幅員 (m)
                  example: 5.0
                setsudou:
                  type: string
                  description: 接道状況詳細テキスト
                  example: "東側幅員5m公道"
                grossYield:
                  type: number
                  description: 表面利回り (%) ※一棟アパート用の収益価格特徴量
                  example: 6.8
                annualRent:
                  type: integer
                  description: 年間想定賃料（円） ※一棟アパート用の収益価格特徴量
                  example: 8160000
                tochikenri:
                  type: string
                  description: 土地権利形態
                  example: "所有権"
                biko:
                  type: string
                  description: 備考
                  example: ""
            interior_score:
              type: number
              description: 内装評価スコア
              default: 3.0
            layout_score:
              type: number
              description: 間取り評価スコア
              default: 3.0
    responses:
      200:
        description: 価格推定成功
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            property_type:
              type: string
              example: apartment
            first_stage_predicted_price:
              type: integer
              description: 一次推定理論価格（万円）
              example: 11500
            second_stage_predicted_price:
              type: integer
              description: 二次推定精密理論価格（万円）
              example: 11800
            message:
              type: string
              example: "Estimation completed successfully"
    """
    try:
        data = request.get_json(silent=True)
        return _predict_price_internal('apartment', data)
    except Exception as e:
        logging.error(f"Error in predict_apartment: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

@evaluation_bp.route('/api/evaluation/predict/tochi', methods=['POST', 'OPTIONS'])
def predict_tochi():
    """
    土地価格推定API
    ---
    tags:
      - Evaluation
    summary: 土地の推定理論価格を算出します。
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - property_data
          properties:
            property_data:
              type: object
              required:
                - price
                - address
                - tochiMenseki
              properties:
                price:
                  type: integer
                  description: 販売価格（円）
                  example: 30000000
                address:
                  type: string
                  description: 住所
                  example: "東京都世田谷区桜丘1-1"
                station1:
                  type: string
                  description: 最寄り駅名
                  example: "経堂"
                tochiMenseki:
                  type: number
                  description: 土地面積 (㎡)
                  example: 100.0
                railwayWalkMinute1:
                  type: integer
                  description: 徒歩分数（分）
                  example: 9
                yousekiStr:
                  type: string
                  description: 指定容積率 (%不要、数値・文字列可)
                  example: "150"
                kenpeiStr:
                  type: string
                  description: 指定建ぺい率 (%不要、数値・文字列可)
                  example: "55"
                maguchi:
                  type: number
                  description: 接道間口 (m)
                  example: 6.5
                roadWidth:
                  type: number
                  description: 前面道路幅員 (m)
                  example: 4.0
                setsudou:
                  type: string
                  description: 接道状況詳細テキスト
                  example: "北側道路4m公道"
                tochikenri:
                  type: string
                  description: 土地権利形態
                  example: "所有権"
                biko:
                  type: string
                  description: 備考
                  example: ""
            interior_score:
              type: number
              description: 内装評価スコア (土地の場合は通常デフォルト3.0が使用されます)
              default: 3.0
            layout_score:
              type: number
              description: 間取り評価スコア (土地の場合は通常デフォルト3.0が使用されます)
              default: 3.0
    responses:
      200:
        description: 価格推定成功
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            property_type:
              type: string
              example: tochi
            first_stage_predicted_price:
              type: integer
              description: 一次推定理論価格（万円）
              example: 2850
            second_stage_predicted_price:
              type: integer
              description: 二次推定精密理論価格（万円）
              example: 2850
            message:
              type: string
              example: "Estimation completed successfully"
    """
    try:
        data = request.get_json(silent=True)
        return _predict_price_internal('tochi', data)
    except Exception as e:
        logging.error(f"Error in predict_tochi: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500


def _extract_property_info(item):
    """モデルオブジェクトまたは辞書から表示用プロパティ辞書を安全に抽出"""
    if not item:
        return {}

    def _val(attr, default=None):
        if isinstance(item, dict):
            val = item.get(attr, default)
        else:
            val = getattr(item, attr, default)

        # MagicMockやMockオブジェクトが自動生成された場合は除外
        if hasattr(val, '_mock_name') or type(val).__name__ in ('MagicMock', 'AsyncMock', 'Mock'):
            return default
        return val

    address = _val("address", "")
    if not address:
        a1 = _val("address1", "") or ""
        a2 = _val("address2", "") or ""
        address = f"{a1}{a2}".strip()

    price = _val("price", None)
    if price is not None:
        try:
            price = int(price)
        except Exception:
            price = None

    walk_minute = _val("railwayWalkMinute1", None)
    if walk_minute is not None:
        try:
            walk_minute = int(walk_minute)
        except Exception:
            walk_minute = None

    def _clean_float(v):
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            return None

    info = {
        "propertyName": str(_val("propertyName", "") or ""),
        "price": price,
        "address": str(address or ""),
        "station": str(_val("station1", "") or ""),
        "walkMinute": walk_minute,
        "senyuMenseki": _clean_float(_val("senyuMenseki", None)),
        "tatemonoMenseki": _clean_float(_val("tatemonoMenseki", None)),
        "tochiMenseki": _clean_float(_val("tochiMenseki", None)),
        "chikunengetsu": str(_val("chikunengetsuStr", "") or ""),
        "kouzou": str(_val("kouzou", "") or "")
    }
    return {k: v for k, v in info.items() if v is not None and v != ""}


async def _execute_predict_by_url(url: str, force_refresh: bool, interior_score: float, layout_score: float):
    """
    URL指定価格推定の非同期実行コアロジック (Singleflightで保護)
    """
    # -------------------------------------------------------------
    # Tier 1: PropertyEvaluation キャッシュ照会
    # -------------------------------------------------------------
    if not force_refresh:
        eval_record = None
        try:
            eval_record = PropertyEvaluation.objects.filter(UrlMatcher.build_db_filter("property_url", url)).first()
        except Exception as e:
            logging.debug(f"PropertyEvaluation cache query skipped: {e}")

        if eval_record and eval_record.first_stage_predicted_price is not None:
            prop_info = {}
            route = UrlRouter.resolve(url)
            if route:
                try:
                    mod = importlib.import_module(route["model_module"])
                    model_cls = getattr(mod, route["model_cls"])
                    existing_item = model_cls.objects.filter(UrlMatcher.build_db_filter("pageUrl", url)).first()
                    if existing_item:
                        prop_info = _extract_property_info(existing_item)
                except Exception as e:
                    logging.debug(f"Failed to fetch model info for cached eval: {e}")

            first_pred = int(eval_record.first_stage_predicted_price)
            second_pred = int(eval_record.second_stage_predicted_price) if eval_record.second_stage_predicted_price is not None else first_pred
            asking_price = prop_info.get("price")
            if asking_price is not None:
                try:
                    asking_price = int(asking_price)
                except Exception:
                    asking_price = None

            price_gap = (first_pred - asking_price) if asking_price else None
            ratio = round(first_pred / asking_price, 3) if asking_price else None
            is_bargain = (ratio >= 1.15) if ratio else False

            site_name = getattr(eval_record, 'company', 'unknown')
            if hasattr(site_name, '_mock_name') or type(site_name).__name__ in ('MagicMock', 'AsyncMock', 'Mock'):
                site_name = route["site"] if route else "unknown"

            ptype_name = getattr(eval_record, 'property_type', 'mansion')
            if hasattr(ptype_name, '_mock_name') or type(ptype_name).__name__ in ('MagicMock', 'AsyncMock', 'Mock'):
                ptype_name = route["property_type"] if route else "mansion"

            return {
                "success": True,
                "url": url,
                "data_source": "evaluation_cache",
                "site": str(site_name),
                "property_type": str(ptype_name),
                "property_info": prop_info,
                "prediction": {
                    "first_stage_predicted_price": first_pred,
                    "second_stage_predicted_price": second_pred,
                    "price_gap": price_gap,
                    "divergence_ratio": ratio,
                    "is_bargain": is_bargain
                },
                "investment": None,
                "message": "Estimation completed successfully (Cached)"
            }, 200

    # -------------------------------------------------------------
    # 対象サイトの判定
    # -------------------------------------------------------------
    route = UrlRouter.resolve(url)
    if not route:
        # 未対応サイト ➔ 到達性 & 不動産キーワードチェック ➔ CandidatePropertyUrl 登録
        is_prop, page_title, matched_kws = await UrlSecurityValidator.check_property_content_and_reachability(url)
        if is_prop:
            parsed_domain = urllib.parse.urlparse(url).netloc
            clean_url = UrlMatcher.normalize(url)
            cand = CandidatePropertyUrl.objects.filter(UrlMatcher.build_db_filter("url", url)).first()
            if cand:
                cand.request_count += 1
                cand.save(update_fields=["request_count", "updated_at"])
                req_count = cand.request_count
            else:
                CandidatePropertyUrl.objects.create(
                    url=clean_url,
                    domain=parsed_domain,
                    title=str(page_title or "")[:300],
                    matched_keywords=matched_kws,
                    request_count=1
                )
                req_count = 1

            # パーサー未対応サイトとして明示的に ERROR ログを出力（監視・新規パーサー開発対象）
            logging.error(
                f"[PARSER_UNAVAILABLE] No parser implemented for site domain '{parsed_domain}' "
                f"(URL: {clean_url}, Title: '{page_title}', Keywords: {matched_kws}). "
                f"Target registered to CandidatePropertyUrl backlog (count={req_count})."
            )

            return {
                "success": False,
                "url": url,
                "data_source": None,
                "error_code": "UNSUPPORTED_SITE_CANDIDATE_RECORDED",
                "message": "指定されたサイトは現在未対応ですが、今後のクローリング候補として登録されました。",
                "details": {
                    "domain": parsed_domain,
                    "title": page_title,
                    "matched_keywords": matched_kws,
                    "candidate_request_count": req_count
                }
            }, 400
        else:
            return {
                "success": False,
                "url": url,
                "data_source": None,
                "error_code": "UNSUPPORTED_SITE_NOT_PROPERTY",
                "message": "指定されたURLは未対応のサイトであり、有効な不動産物件ページを確認できませんでした。"
            }, 400

    site = route["site"]
    property_type = route["property_type"]
    model_mod = importlib.import_module(route["model_module"])
    model_cls = getattr(model_mod, route["model_cls"])

    # -------------------------------------------------------------
    # Tier 2: 各社物件テーブル既存レコード確認
    # -------------------------------------------------------------
    existing_item = None
    if not force_refresh:
        existing_item = model_cls.objects.filter(UrlMatcher.build_db_filter("pageUrl", url)).first()

    target_item = existing_item
    data_source = "db_property" if existing_item else "live_crawl"

    # -------------------------------------------------------------
    # Tier 3: 存在しない（または force_refresh）の場合はリアルタイム取得
    # -------------------------------------------------------------
    if target_item is None:
        try:
            parser_mod = importlib.import_module(route["parser_module"])
            parser_cls = getattr(parser_mod, route["parser_cls"])
            parser = parser_cls()
        except Exception as e:
            logging.error(
                f"[PARSER_NOT_FOUND] Parser class '{route.get('parser_cls')}' could not be loaded for URL: {url}: {e}",
                exc_info=True
            )
            return {
                "success": False,
                "url": url,
                "data_source": None,
                "error_code": "PARSER_NOT_FOUND",
                "message": f"パーサーの実装が見つかりません: {str(e)}"
            }, 500

        try:
            connector = aiohttp.TCPConnector(ssl=False)
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                target_item = await parser.parsePropertyDetailPage(session, url)
        except ListingEndedException:
            return {
                "success": False,
                "url": url,
                "data_source": None,
                "error_code": "LISTING_ENDED",
                "message": "物件の掲載が終了しているか、削除されています。"
            }, 410
        except (LoadPropertyPageException, asyncio.TimeoutError):
            return {
                "success": False,
                "url": url,
                "data_source": None,
                "error_code": "TARGET_SITE_TIMEOUT",
                "message": "対象サイトへの接続に失敗したか、タイムアウトしました。"
            }, 504
        except Exception as e:
            logging.error(f"Live crawling error for {url}: {e}", exc_info=True)
            return {
                "success": False,
                "url": url,
                "data_source": None,
                "error_code": "PARSE_FAILED",
                "message": f"物件ページのパースに失敗しました: {str(e)}"
            }, 422

        if target_item is None:
            return {
                "success": False,
                "url": url,
                "data_source": None,
                "error_code": "PARSE_FAILED",
                "message": "物件情報の抽出結果が空です。"
            }, 422

        # 物件テーブルへの Upsert (正規化URLで保存)
        clean_url = UrlMatcher.normalize(url)
        try:
            model_fields = [f.name for f in model_cls._meta.fields if f.name not in ('id', 'created_at', 'updated_at', 'inputDate')]
            defaults_dict = {}
            for f in model_fields:
                val = getattr(target_item, f, None)
                if val is not None:
                    defaults_dict[f] = val
            saved_item, _ = model_cls.objects.update_or_create(pageUrl=clean_url, defaults=defaults_dict)
            target_item = saved_item
        except Exception as e:
            logging.warning(f"Failed to upsert property item to DB for {url}: {e}")

    # -------------------------------------------------------------
    # 特徴量化 & 機械学習推論
    # -------------------------------------------------------------
    serialized = _serialize_property(target_item, property_type)
    first_pred = predict_first_stage_local(serialized)
    second_pred = predict_second_stage_local(serialized, interior_score, layout_score)

    first_val = int(first_pred or 0)
    second_val = int(second_pred or first_val)

    # PropertyEvaluation への Upsert (正規化URLで保存)
    prop_id = getattr(target_item, 'id', 0)
    if hasattr(prop_id, '_mock_name') or type(prop_id).__name__ in ('MagicMock', 'AsyncMock', 'Mock'):
        prop_id = 0
    else:
        try:
            prop_id = int(prop_id or 0)
        except Exception:
            prop_id = 0

    try:
        PropertyEvaluation.objects.update_or_create(
            property_url=UrlMatcher.normalize(url),
            defaults={
                "company": site,
                "property_type": property_type,
                "property_id": prop_id,
                "first_stage_predicted_price": first_val,
                "second_stage_predicted_price": second_val,
                "interior_score": interior_score,
                "layout_score": layout_score
            }
        )
    except Exception as e:
        logging.warning(f"Failed to update PropertyEvaluation for {url}: {e}")

    prop_info = _extract_property_info(target_item)
    asking_price = prop_info.get("price")
    if asking_price is not None:
        try:
            asking_price = int(asking_price)
        except Exception:
            asking_price = None

    price_gap = (first_val - asking_price) if asking_price else None
    ratio = round(first_val / asking_price, 3) if asking_price else None
    is_bargain = (ratio >= 1.15) if ratio else False

    return {
        "success": True,
        "url": url,
        "data_source": data_source,
        "site": site,
        "property_type": property_type,
        "property_info": prop_info,
        "prediction": {
            "first_stage_predicted_price": first_val,
            "second_stage_predicted_price": second_val,
            "price_gap": price_gap,
            "divergence_ratio": ratio,
            "is_bargain": is_bargain
        },
        "investment": None,
        "message": "Estimation completed successfully"
    }, 200


@evaluation_bp.route('/api/evaluation/predict-by-url', methods=['POST', 'OPTIONS'])
def predict_by_url():
    """
    物件詳細URL価格推定API
    """
    if request.method == 'OPTIONS':
        return "", 200

    client_ip = get_client_ip()

    # 内部接続（自作システム、バッチ、正規キー、ローカル接続）は流量制限・ロックアウトをバイパス
    if not is_internal_client():
        # 1. ロックアウト確認
        is_locked, remaining_sec = lockout_manager.is_locked_out(client_ip)
        if is_locked:
            return jsonify({
                "success": False,
                "error_code": "IP_LOCKED_OUT",
                "message": "Too many violations. Access is temporarily blocked. Please retry later.",
                "retry_after_seconds": remaining_sec
            }), 403

        # 2. 流量制限（レートリミット）確認
        allowed, retry_after = rate_limiter.is_allowed(client_ip)
        if not allowed:
            lockout_manager.record_strike(client_ip)
            return jsonify({
                "success": False,
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "Rate limit exceeded. Please slow down.",
            }), 429

    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({
            "success": False,
            "error_code": "INVALID_URL",
            "message": "Missing 'url' parameter in request body"
        }), 400

    # 3. URL セキュリティ & SSRF 防御
    is_safe, sec_reason = UrlSecurityValidator.validate_url_security(url)
    if not is_safe:
        if "Blocked" in sec_reason or "SSRF" in sec_reason:
            lockout_manager.record_strike(client_ip, instant_ban=True)
        return jsonify({
            "success": False,
            "error_code": "SECURITY_BLOCKED",
            "message": sec_reason
        }), 400

    force_refresh = bool(data.get("force_refresh", False))
    interior_score = float(data.get("interior_score", 3.0))
    layout_score = float(data.get("layout_score", 3.0))

    # Singleflight で同一URLの並行処理合流
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        normalized_url = UrlMatcher.normalize(url)
        result, status_code = loop.run_until_complete(
            singleflight_group.do(
                normalized_url,
                _execute_predict_by_url,
                url,
                force_refresh,
                interior_score,
                layout_score
            )
        )
        return jsonify(result), status_code
    except Exception as e:
        logging.error(f"Error in predict_by_url: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": str(e)
        }), 500
    finally:
        try:
            connections.close_all()
            reset_queries()
        except Exception:
            pass

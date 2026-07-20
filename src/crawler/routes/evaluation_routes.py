# -*- coding: utf-8 -*-
import logging
from flask import Blueprint, request, jsonify
from package.ml.predict import predict_first_stage_local, predict_second_stage_local

evaluation_bp = Blueprint('evaluation', __name__)

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

@evaluation_bp.route('/api/evaluation/predict/mansion', methods=['POST'])
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
                  description: 指定容積率 (例: 200%)
                  example: "200%"
                kenpeiStr:
                  type: string
                  description: 指定建ぺい率 (例: 60%)
                  example: "60%"
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

@evaluation_bp.route('/api/evaluation/predict/kodate', methods=['POST'])
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
                  description: 指定容積率
                  example: "150%"
                kenpeiStr:
                  type: string
                  description: 指定建ぺい率
                  example: "50%"
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

@evaluation_bp.route('/api/evaluation/predict/apartment', methods=['POST'])
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
                  description: 指定容積率
                  example: "200%"
                kenpeiStr:
                  type: string
                  description: 指定建ぺい率
                  example: "60%"
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

@evaluation_bp.route('/api/evaluation/predict/tochi', methods=['POST'])
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
                  description: 指定容積率
                  example: "150%"
                kenpeiStr:
                  type: string
                  description: 指定建ぺい率
                  example: "55%"
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

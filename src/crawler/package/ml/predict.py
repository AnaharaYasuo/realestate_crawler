# -*- coding: utf-8 -*-
import os
import sys
import datetime
import pandas as pd
import numpy as np
import joblib
import logging

# Django設定のロード
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# モデルとマスタのキャッシュ
_first_stage_models = {}
_second_stage_models = {}
_mkt_comparison_master = None

def _get_models_and_master(property_type):
    """
    指定された物件種別のモデルと、共通の比準想定価格マスタをキャッシュロードする (アンサンブルモデル対応)
    """
    global _first_stage_models, _second_stage_models, _mkt_comparison_master
    
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    
    # 1. 共通マスタのロード
    if _mkt_comparison_master is None:
        master_path = os.path.join(model_dir, "mkt_comparison_master.joblib")
        if os.path.exists(master_path):
            try:
                _mkt_comparison_master = joblib.load(master_path)
                logging.info("ML: Loaded market comparison master.")
            except Exception as e:
                logging.error(f"ML: Failed to load market comparison master: {e}")
                _mkt_comparison_master = {}
        else:
            logging.warning("ML: Market comparison master not found. Run train.py first.")
            _mkt_comparison_master = {}
            
    # 2. 一次モデル (LGB, XGB, Cat) のロード
    if property_type not in _first_stage_models:
        _first_stage_models[property_type] = {}
        for algo in ['lgb', 'xgb', 'cat']:
            path = os.path.join(model_dir, f"{property_type}_first_stage_{algo}.joblib")
            if os.path.exists(path):
                try:
                    _first_stage_models[property_type][algo] = joblib.load(path)
                    logging.info(f"ML: Loaded {property_type} first stage {algo} model.")
                except Exception as e:
                    logging.error(f"ML: Failed to load {property_type} first stage {algo} model: {e}")
            else:
                # 従来モデルが存在する場合の互換フォールバック
                legacy_path = os.path.join(model_dir, f"{property_type}_first_stage_model.joblib")
                if algo == 'lgb' and os.path.exists(legacy_path):
                    try:
                        _first_stage_models[property_type]['lgb'] = joblib.load(legacy_path)
                        logging.info(f"ML: Loaded {property_type} first stage legacy model as lgb.")
                    except:
                        pass
            
    # 3. 二次モデル (LGB, XGB, Cat) のロード
    if property_type not in _second_stage_models:
        _second_stage_models[property_type] = {}
        for algo in ['lgb', 'xgb', 'cat']:
            path = os.path.join(model_dir, f"{property_type}_second_stage_{algo}.joblib")
            if os.path.exists(path):
                try:
                    _second_stage_models[property_type][algo] = joblib.load(path)
                    logging.info(f"ML: Loaded {property_type} second stage {algo} model.")
                except Exception as e:
                    logging.error(f"ML: Failed to load {property_type} second stage {algo} model: {e}")
            else:
                # 従来モデルが存在する場合の互換フォールバック
                legacy_path = os.path.join(model_dir, f"{property_type}_second_stage_model.joblib")
                if algo == 'lgb' and os.path.exists(legacy_path):
                    try:
                        _second_stage_models[property_type]['lgb'] = joblib.load(legacy_path)
                        logging.info(f"ML: Loaded {property_type} second stage legacy model as lgb.")
                    except:
                        pass
            
    return _first_stage_models[property_type], _second_stage_models[property_type], _mkt_comparison_master


def _detect_property_type(property_obj):
    """
    オブジェクト名または型から mansion / kodate / apartment の種別を自動判定
    """
    if isinstance(property_obj, dict):
        ptype = property_obj.get("propertyType", "").lower()
        if "mansion" in ptype: return "mansion"
        if "kodate" in ptype: return "kodate"
        if "apartment" in ptype: return "apartment"
        
        # 簡易フォールバック判定
        if "senyuMenseki" in property_obj: return "mansion"
        if "tatemonoMenseki" in property_obj:
            if "grossYield" in property_obj: return "apartment"
            return "kodate"
        return "mansion"
        
    # Djangoオブジェクトの場合
    class_name = property_obj.__class__.__name__.lower()
    if "mansion" in class_name:
        return "mansion"
    elif "kodate" in class_name:
        return "kodate"
    elif "apartment" in class_name:
        return "apartment"
    return "mansion"


def _log_prediction_error(property_obj, property_type, predicted_price, actual_price, features):
    """
    乖離率が +-30% 以上の予測エラー物件をログファイルにCSV出力する (自己改善サイクルの基盤)
    """
    if not actual_price or actual_price <= 0:
        return
        
    error_ratio = (predicted_price - actual_price) / actual_price
    if abs(error_ratio) >= 0.3:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "prediction_errors.csv")
        
        def get_attr(obj, name, default=None):
            if isinstance(obj, dict):
                return obj.get(name, default)
            return getattr(obj, name, default)
            
        page_url = get_attr(property_obj, 'pageUrl', '') or get_attr(property_obj, 'page_url', '')
        address = get_attr(property_obj, 'address', '') or f"{features.get('prefecture', '')}{features.get('city', '')}"
        
        row = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "property_type": property_type,
            "page_url": page_url,
            "address": address,
            "actual_price": actual_price,
            "predicted_price": predicted_price,
            "error_ratio": f"{error_ratio:.4f}",
            **{k: v for k, v in features.items() if k not in ["prefecture", "city", "station", "company", "kouzou"]}
        }
        
        df_row = pd.DataFrame([row])
        header = not os.path.exists(log_path)
        try:
            df_row.to_csv(log_path, mode='a', index=False, header=header, encoding='utf-8-sig')
            logging.info(f"ML: Logged prediction error for {page_url} (Error: {error_ratio*100:.1f}%)")
        except Exception as e:
            logging.error(f"ML: Failed to write prediction error log: {e}")


def predict_first_stage(property_obj) -> int:
    """
    一次理論価格予測 (画像なし予測) - アンサンブル加重平均
    """
    from package.ml.features import build_features
    
    ptype = _detect_property_type(property_obj)
    first_models, _, mkt_master = _get_models_and_master(ptype)
    
    # 共通関数を用いて特徴量を構築
    features = build_features(property_obj, ptype, mkt_comparison_master=mkt_master)
    
    feature_sets = {
        "mansion": [
            "area", "chikunen", "walk_min", "kanrihi", "syuzen",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei"
        ],
        "kodate": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei"
        ],
        "apartment": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "gross_yield", "annual_rent",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei"
        ]
    }
    
    feature_cols = feature_sets[ptype]
    
    df = pd.DataFrame([features])[feature_cols]
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype('category').cat.codes
            
    # アンサンブル予測の実行 (加重平均 - 再学習の精度に基づく動的ウェイト)
    if ptype == 'mansion':
        weights = {'lgb': 0.4, 'xgb': 0.4, 'cat': 0.2}
    elif ptype == 'kodate':
        weights = {'lgb': 0.4, 'xgb': 0.5, 'cat': 0.1}
    elif ptype == 'apartment':
        weights = {'lgb': 0.4, 'xgb': 0.5, 'cat': 0.1}
    else:
        weights = {'lgb': 0.4, 'xgb': 0.3, 'cat': 0.3}
    loaded_weights = {}
    total_weight = 0.0
    
    for algo, model in first_models.items():
        if model:
            loaded_weights[algo] = weights[algo]
            total_weight += weights[algo]
            
    if not loaded_weights:
        logging.error(f"ML: No first stage models available for {ptype}.")
        return 0
        
    final_pred = 0.0
    for algo, weight in loaded_weights.items():
        norm_weight = weight / total_weight
        pred = first_models[algo].predict(df)[0]
        final_pred += pred * norm_weight
        
    predicted_val = int(max(0, final_pred))
    
    # 予測エラーのログ化
    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)
    actual_price = get_attr(property_obj, 'price', 0)
    _log_prediction_error(property_obj, ptype, predicted_val, actual_price, features)
    
    return predicted_val


def predict_second_stage(property_obj, interior_score: float, layout_score: float) -> int:
    """
    二次理論価格予測 (画像スコアを組み込んだ精密予測) - アンサンブル加重平均
    """
    from package.ml.features import build_features
    
    ptype = _detect_property_type(property_obj)
    _, second_models, mkt_master = _get_models_and_master(ptype)
    
    features = build_features(property_obj, ptype, mkt_comparison_master=mkt_master)
    features["interior_score"] = float(interior_score)
    features["layout_score"] = float(layout_score)
    
    feature_sets = {
        "mansion": [
            "area", "chikunen", "walk_min", "kanrihi", "syuzen",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "interior_score", "layout_score"
        ],
        "kodate": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "interior_score", "layout_score"
        ],
        "apartment": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "gross_yield", "annual_rent",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "interior_score", "layout_score"
        ]
    }
    
    feature_cols = feature_sets[ptype]
    
    df = pd.DataFrame([features])[feature_cols]
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype('category').cat.codes
            
    # アンサンブル予測の実行 (加重平均 - 再学習の精度に基づく動的ウェイト)
    if ptype == 'mansion':
        weights = {'lgb': 0.4, 'xgb': 0.4, 'cat': 0.2}
    elif ptype == 'kodate':
        weights = {'lgb': 0.4, 'xgb': 0.5, 'cat': 0.1}
    elif ptype == 'apartment':
        weights = {'lgb': 0.4, 'xgb': 0.5, 'cat': 0.1}
    else:
        weights = {'lgb': 0.4, 'xgb': 0.3, 'cat': 0.3}
    loaded_weights = {}
    total_weight = 0.0
    
    for algo, model in second_models.items():
        if model:
            loaded_weights[algo] = weights[algo]
            total_weight += weights[algo]
            
    if not loaded_weights:
        logging.error(f"ML: No second stage models available for {ptype}.")
        return 0
        
    final_pred = 0.0
    for algo, weight in loaded_weights.items():
        norm_weight = weight / total_weight
        pred = second_models[algo].predict(df)[0]
        final_pred += pred * norm_weight
        
    predicted_val = int(max(0, final_pred))
    
    # 予測エラーのログ化
    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)
    actual_price = get_attr(property_obj, 'price', 0)
    _log_prediction_error(property_obj, ptype, predicted_val, actual_price, features)
    
    return predicted_val

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

def _load_mkt_comparison_master(model_dir):
    global _mkt_comparison_master
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
    return _mkt_comparison_master

def _load_legacy_model(property_type, algo, stage, model_dir):
    if algo != 'lgb':
        return None
    legacy_path = os.path.join(model_dir, f"{property_type}_{stage}_model.joblib")
    if os.path.exists(legacy_path):
        try:
            model = joblib.load(legacy_path)
            logging.info(f"ML: Loaded {property_type} {stage} legacy model as lgb.")
            return model
        except:
            pass
    return None

def _load_first_stage_models(property_type, model_dir):
    global _first_stage_models
    if property_type not in _first_stage_models:
        _first_stage_models[property_type] = {}
        for algo in ['lgb', 'xgb', 'cat', 'rf']:
            path = os.path.join(model_dir, f"{property_type}_first_stage_{algo}.joblib")
            if os.path.exists(path):
                try:
                    _first_stage_models[property_type][algo] = joblib.load(path)
                    logging.info(f"ML: Loaded {property_type} first stage {algo} model.")
                    continue
                except Exception as e:
                    logging.error(f"ML: Failed to load {property_type} first stage {algo} model: {e}")
            
            legacy_model = _load_legacy_model(property_type, algo, "first_stage", model_dir)
            if legacy_model:
                _first_stage_models[property_type][algo] = legacy_model
    return _first_stage_models[property_type]

def _load_second_stage_models(property_type, model_dir):
    global _second_stage_models
    if property_type not in _second_stage_models:
        _second_stage_models[property_type] = {}
        for algo in ['lgb', 'xgb', 'cat', 'rf']:
            path = os.path.join(model_dir, f"{property_type}_second_stage_{algo}.joblib")
            if os.path.exists(path):
                try:
                    _second_stage_models[property_type][algo] = joblib.load(path)
                    logging.info(f"ML: Loaded {property_type} second stage {algo} model.")
                    continue
                except Exception as e:
                    logging.error(f"ML: Failed to load {property_type} second stage {algo} model: {e}")
            
            legacy_model = _load_legacy_model(property_type, algo, "second_stage", model_dir)
            if legacy_model:
                _second_stage_models[property_type][algo] = legacy_model
    return _second_stage_models[property_type]

def _get_models_and_master(property_type):
    """
    指定された物件種別のモデルと、共通の比準想定価格マスタをキャッシュロードする (アンサンブルモデル対応)
    """
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    master = _load_mkt_comparison_master(model_dir)
    first = _load_first_stage_models(property_type, model_dir)
    second = _load_second_stage_models(property_type, model_dir)
    return first, second, master

def _detect_property_type_from_dict(property_obj):
    ptype = property_obj.get("propertyType", "").lower()
    if "mansion" in ptype: return "mansion"
    if "kodate" in ptype: return "kodate"
    if "apartment" in ptype: return "apartment"
    if "tochi" in ptype: return "tochi"
    
    if "senyuMenseki" in property_obj: return "mansion"
    if "tatemonoMenseki" in property_obj:
        if "grossYield" in property_obj: return "apartment"
        return "kodate"
    if "tochiMenseki" in property_obj or "maguchi" in property_obj: return "tochi"
    return "mansion"

def _detect_property_type_from_django(property_obj):
    class_name = property_obj.__class__.__name__.lower()
    if "mansion" in class_name:
        return "mansion"
    elif "kodate" in class_name:
        return "kodate"
    elif "apartment" in class_name:
        return "apartment"
    elif "tochi" in class_name:
        return "tochi"
    return "mansion"

def _detect_property_type(property_obj):
    """
    オブジェクト名または型から mansion / kodate / apartment / tochi の種別を自動判定
    """
    if isinstance(property_obj, dict):
        return _detect_property_type_from_dict(property_obj)
    return _detect_property_type_from_django(property_obj)

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

def _apply_rights_discount(_property_obj, predicted_price: float) -> int:
    """
    (廃止) 借地権・底地などの権利形態による価格ディスカウント補正を行う
    ※ 事後ディスカウント処理は廃止し、機械学習の特徴量（is_shigaika_chousei, is_saikenchiku_fuka, rights_ratio等）としてモデル自身に評価させるように移行しました。
    """
    return int(predicted_price)

def _align_features(df, model):
    expected_features = None
    if hasattr(model, "feature_names_in_"):
        expected_features = list(model.feature_names_in_)
    elif hasattr(model, "feature_names"):
        expected_features = list(model.feature_names)
        
    if not expected_features:
        return df
        
    df_aligned = df.copy()
    for col in expected_features:
        if col not in df_aligned.columns:
            df_aligned[col] = 0.0
    return df_aligned[expected_features]

def _ensemble_predict(models, df, weights, ptype) -> float:
    loaded_weights = {}
    total_weight = 0.0
    for algo, model in models.items():
        if model:
            loaded_weights[algo] = weights[algo]
            total_weight += weights[algo]
            
    if not loaded_weights:
        logging.error(f"ML: No models available for {ptype}.")
        return 0.0
        
    final_pred = 0.0
    for algo, weight in loaded_weights.items():
        norm_weight = weight / total_weight
        model = models[algo]
        df_for_pred = _align_features(df, model)
        pred_log = model.predict(df_for_pred)[0]
        pred_unit = np.expm1(pred_log)
        pred = pred_unit * float(df["area"].values[0])
        final_pred += pred * norm_weight
    return final_pred

def predict_first_stage(property_obj) -> int:
    """
    一次理論価格予測 (画像なし予測) - アンサンブル加重平均
    """
    from package.ml.features import build_features
    
    ptype = _detect_property_type(property_obj)
    first_models, _, mkt_master = _get_models_and_master(ptype)
    features = build_features(property_obj, ptype, mkt_comparison_master=mkt_master)
    
    feature_sets = {
        "mansion": [
            "area", "chikunen", "walk_min", "kanrihi", "syuzen",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "max_building_area", "max_floor_area",
            "kagechi_ratio", "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio"
        ],
        "kodate": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio"
        ],
        "apartment": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "gross_yield", "annual_rent",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio"
        ],
        "tochi": [
            "area", "tochi_menseki", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio"
        ]
    }
    
    feature_cols = feature_sets[ptype]
    df = pd.DataFrame([features])[feature_cols]
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype('category').cat.codes
            
    if ptype == 'mansion':
        weights = {'lgb': 0.35, 'xgb': 0.35, 'cat': 0.15, 'rf': 0.15}
    elif ptype == 'kodate':
        weights = {'lgb': 0.35, 'xgb': 0.45, 'cat': 0.1, 'rf': 0.1}
    elif ptype == 'apartment':
        weights = {'lgb': 0.35, 'xgb': 0.45, 'cat': 0.1, 'rf': 0.1}
    else:
        weights = {'lgb': 0.3, 'xgb': 0.25, 'cat': 0.25, 'rf': 0.2}
        
    final_pred = _ensemble_predict(first_models, df, weights, ptype)
    raw_predicted_val = int(max(0, final_pred))
    predicted_val = _apply_rights_discount(property_obj, raw_predicted_val)
    
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
    features["interior_score"] = interior_score
    features["layout_score"] = layout_score
    
    feature_sets = {
        "mansion": [
            "area", "chikunen", "walk_min", "kanrihi", "syuzen",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "interior_score", "layout_score",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio"
        ],
        "kodate": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "interior_score", "layout_score",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio"
        ],
        "apartment": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "gross_yield", "annual_rent",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "interior_score", "layout_score",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio"
        ],
        "tochi": [
            "area", "tochi_menseki", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "interior_score", "layout_score",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio"
        ]
    }
    
    feature_cols = feature_sets[ptype]
    df = pd.DataFrame([features])[feature_cols]
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype('category').cat.codes
            
    if ptype == 'mansion':
        weights = {'lgb': 0.35, 'xgb': 0.35, 'cat': 0.15, 'rf': 0.15}
    elif ptype == 'kodate':
        weights = {'lgb': 0.35, 'xgb': 0.45, 'cat': 0.1, 'rf': 0.1}
    elif ptype == 'apartment':
        weights = {'lgb': 0.35, 'xgb': 0.45, 'cat': 0.1, 'rf': 0.1}
    else:
        weights = {'lgb': 0.3, 'xgb': 0.25, 'cat': 0.25, 'rf': 0.2}
        
    final_pred = _ensemble_predict(second_models, df, weights, ptype)
    raw_predicted_val = int(max(0, final_pred))
    predicted_val = _apply_rights_discount(property_obj, raw_predicted_val)
    
    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)
    actual_price = get_attr(property_obj, 'price', 0)
    _log_prediction_error(property_obj, ptype, predicted_val, actual_price, features)
    
    return predicted_val

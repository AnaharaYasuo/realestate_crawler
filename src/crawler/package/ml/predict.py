# -*- coding: utf-8 -*-
import os
import sys
import datetime
import pandas as pd
import numpy as np
import joblib
import logging
import warnings
warnings.filterwarnings("ignore")

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
    
    # getattr を使用して静的解析属性エラーを回避
    names_in = getattr(model, "feature_names_in_", None)
    if names_in is not None:
        try:
            expected_features = list(names_in)
        except:
            pass
        
    if not expected_features:
        name_ = getattr(model, "feature_name_", None)
        if name_ is not None:
            try:
                expected_features = list(name_)
            except:
                pass
            
    if not expected_features:
        names = getattr(model, "feature_names", None)
        if names is not None:
            try:
                expected_features = list(names)
            except:
                pass
            
    if not expected_features:
        feature_name_func = getattr(model, "feature_name", None)
        if feature_name_func is not None and callable(feature_name_func):
            try:
                expected_features = list(feature_name_func())
            except:
                pass
                
    if not expected_features:
        booster = getattr(model, "booster_", None)
        if booster is not None:
            booster_feature_name = getattr(booster, "feature_name", None)
            if booster_feature_name is not None and callable(booster_feature_name):
                try:
                    expected_features = list(booster_feature_name())
                except:
                    pass
                    
    if not expected_features:
        get_booster_func = getattr(model, "get_booster", None)
        if get_booster_func is not None and callable(get_booster_func):
            try:
                booster_obj = get_booster_func()
                booster_names = getattr(booster_obj, "feature_names", None)
                if booster_names is not None:
                    expected_features = list(booster_names)
            except:
                pass
        
    if not expected_features:
        logging.warning("ML: Could not extract feature names from model. Using DataFrame columns as is.")
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

def get_api_base_url():
    """価格推定APIのベースURLを解決する"""
    url = os.getenv("EVALUATION_API_URL", "")
    if url:
        if not url.endswith("/"):
            url += "/"
        return url
        
    if os.getenv("IS_CLOUD", ""):
        return "https://us-central1-sumifu.cloudfunctions.net/api/evaluation/predict/"
    return "http://localhost:8000/api/evaluation/predict/"

def _serialize_property(item, ptype):
    """Djangoモデルオブジェクトまたは辞書からAPI送信用のシリアライズ辞書を作成"""
    def _val(name, default=None):
        if isinstance(item, dict):
            return item.get(name, default)
        return getattr(item, name, default)

    data = {
        "price": _val("price", None),
        "address": _val("address", ""),
        "station1": _val("station1", ""),
        "railwayWalkMinute1": _val("railwayWalkMinute1", None),
        "kouzou": _val("kouzou", ""),
        "yousekiStr": _val("yousekiStr", "") or str(_val("youseki", "")) or "",
        "kenpeiStr": _val("kenpeiStr", "") or str(_val("kenpei", "")) or "",
        "tochikenri": _val("tochikenri", ""),
        "biko": _val("biko", "")
    }
    
    # 築年月のシリアライズ (Date -> Str)
    chikunengetsu = _val("chikunengetsu", None)
    if chikunengetsu:
        if hasattr(chikunengetsu, "strftime"):
            data["chikunengetsuStr"] = chikunengetsu.strftime("%Y-%m-%d")
        else:
            data["chikunengetsuStr"] = str(chikunengetsu)
    else:
        data["chikunengetsuStr"] = _val("chikunengetsuStr", "")
        
    # 物件種別ごとの固有フィールド
    if ptype == "mansion":
        data["senyuMenseki"] = float(_val("senyuMenseki")) if _val("senyuMenseki") is not None else None
        data["kanrihi"] = _val("kanrihi", None)
        data["syuzenTsumitate"] = _val("syuzenTsumitate", None)
    elif ptype == "kodate":
        data["tatemonoMenseki"] = float(_val("tatemonoMenseki")) if _val("tatemonoMenseki") is not None else None
        data["tochiMenseki"] = float(_val("tochiMenseki")) if _val("tochiMenseki") is not None else None
        data["maguchi"] = float(_val("maguchi")) if _val("maguchi") is not None else None
        data["roadWidth"] = float(_val("roadWidth")) if _val("roadWidth") is not None else None
        data["setsudou"] = _val("setsudou", "")
    elif ptype == "apartment":
        data["tatemonoMenseki"] = float(_val("tatemonoMenseki")) if _val("tatemonoMenseki") is not None else None
        data["tochiMenseki"] = float(_val("tochiMenseki")) if _val("tochiMenseki") is not None else None
        data["maguchi"] = float(_val("maguchi")) if _val("maguchi") is not None else None
        data["roadWidth"] = float(_val("roadWidth")) if _val("roadWidth") is not None else None
        data["setsudou"] = _val("setsudou", "")
        data["grossYield"] = float(_val("grossYield")) if _val("grossYield") is not None else None
        data["annualRent"] = _val("annualRent", None)
    elif ptype == "tochi":
        data["tochiMenseki"] = float(_val("tochiMenseki")) if _val("tochiMenseki") is not None else None
        data["maguchi"] = float(_val("maguchi")) if _val("maguchi") is not None else None
        data["roadWidth"] = float(_val("roadWidth")) if _val("roadWidth") is not None else None
        data["setsudou"] = _val("setsudou", "")
        
    return data

def _call_predict_api(property_obj, interior_score=3.0, layout_score=3.0):
    """APIを呼び出して推定結果（first, second）を返すヘルパー"""
    def _val(name, default=None):
        if isinstance(property_obj, dict):
            return property_obj.get(name, default)
        return getattr(property_obj, name, default)

    ptype = _val("propertyType") or _val("property_type")
    if not ptype:
        model_name = property_obj.__class__.__name__
        company = "unknown"
        for c in ["mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1", "mizuho", "odakyu", "afr", "sekisui", "daiwa", "totate", "athome", "homes", "seibu", "keikyu", "sotetsu", "keisei", "daikyo", "rearie", "heim", "sumirin", "keio"]:
            if model_name.lower().startswith(c):
                company = c
                break
        ptype = model_name.lower().replace(company, "")
    
    if "kodate" in ptype:
        ptype = "kodate"
    elif "apartment" in ptype:
        ptype = "apartment"
        
    if ptype not in ["mansion", "kodate", "apartment", "tochi"]:
        ptype = "mansion"

    serialized = _serialize_property(property_obj, ptype)
    payload = {
        "property_data": serialized,
        "interior_score": float(interior_score),
        "layout_score": float(layout_score)
    }
    
    api_base_url = get_api_base_url()
    api_url = f"{api_base_url}{ptype}"
    
    try:
        import requests
        response = requests.post(api_url, json=payload, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            return (
                int(res_data.get("first_stage_predicted_price", 0)),
                int(res_data.get("second_stage_predicted_price", 0))
            )
        else:
            logging.error(f"API estimation failed: status={response.status_code}, response={response.text}")
    except Exception as e:
        # 接続不可時は警告を出さずにフォールバックできるようデバッグログにする
        logging.debug(f"API server not reachable, falling back to local prediction: {e}")
        
    return 0, 0

def predict_first_stage(property_obj) -> int:
    """
    一次理論価格予測 (画像なし予測) - API経由 (接続エラー時はローカルフォールバック)
    """
    pred1, _ = _call_predict_api(property_obj)
    if pred1 > 0:
        return pred1
    return predict_first_stage_local(property_obj)

def predict_second_stage(property_obj, interior_score: float, layout_score: float) -> int:
    """
    二次理論価格予測 (画像スコアを組み込んだ精密予測) - API経由 (接続エラー時はローカルフォールバック)
    """
    _, pred2 = _call_predict_api(property_obj, interior_score, layout_score)
    if pred2 > 0:
        return pred2
    return predict_second_stage_local(property_obj, interior_score, layout_score)

def predict_first_stage_local(property_obj) -> int:
    """
    一次理論価格予測 (ローカルフォールバック実装)
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

def predict_second_stage_local(property_obj, interior_score: float, layout_score: float) -> int:
    """
    二次理論価格予測 (ローカルフォールバック実装)
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

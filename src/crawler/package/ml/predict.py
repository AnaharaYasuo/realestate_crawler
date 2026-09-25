# -*- coding: utf-8 -*-
import os
import sys
import datetime
import pandas as pd
import numpy as np
import joblib
import logging
import warnings
import traceback
from sklearn.utils.parallel import config_context
from package.utils.property_type_detector import PropertyTypeDetector

def _custom_showwarning(message, category, filename, lineno, file=None, line=None):
    if "sklearn.utils.parallel" in str(message):
        tb = "".join(traceback.format_stack(limit=6))
        logging.warning(f"ML DETECTED SKLEARN WARNING: {category.__name__}: {message} at {filename}:{lineno}\nCall Stack:\n{tb}")
    else:
        sys.stderr.write(warnings.formatwarning(message, category, filename, lineno, line))

warnings.showwarning = _custom_showwarning

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
                logging.exception(f"ML: Failed to load market comparison master: {e}")
                _mkt_comparison_master = {}
        else:
            logging.warning("ML: Market comparison master not found. Run train.py first.")
            _mkt_comparison_master = {}
_smearing_factors = {}
_ensemble_weights = {}

def _load_smearing_factors(model_dir):
    global _smearing_factors
    if not _smearing_factors:
        path = os.path.join(model_dir, "smearing_factors.joblib")
        if os.path.exists(path):
            try:
                _smearing_factors = joblib.load(path)
                logging.info("ML: Loaded smearing factors.")
            except Exception as e:
                logging.exception(f"ML: Failed to load smearing factors: {e}")
                _smearing_factors = {}
    return _smearing_factors

def _load_ensemble_weights(model_dir):
    global _ensemble_weights
    if not _ensemble_weights:
        path = os.path.join(model_dir, "ensemble_weights.joblib")
        if os.path.exists(path):
            try:
                _ensemble_weights = joblib.load(path)
                logging.info("ML: Loaded dynamic ensemble weights.")
            except Exception as e:
                logging.exception(f"ML: Failed to load ensemble weights: {e}")
                _ensemble_weights = {}
    return _ensemble_weights

def _load_legacy_model(property_type, algo, stage, model_dir):
    if algo != 'lgb':
        return None
    legacy_path = os.path.join(model_dir, f"{property_type}_{stage}_model.joblib")
    if os.path.exists(legacy_path):
        try:
            model = joblib.load(legacy_path)
            logging.info(f"ML: Loaded {property_type} {stage} legacy model as lgb.")
            return model
        except Exception:
            pass
    return None

def _load_single_model(property_type, stage, algo, model_dir):
    path = os.path.join(model_dir, f"{property_type}_{stage}_{algo}.joblib")
    if os.path.exists(path):
        try:
            model = joblib.load(path)
            if hasattr(model, "set_params") and hasattr(model, "n_jobs"):
                try:
                    model.set_params(n_jobs=1)
                except Exception:
                    pass
            logging.info(f"ML: Loaded {property_type} {stage} {algo} model.")
            return model
        except Exception as e:
            logging.exception(f"ML: Failed to load {property_type} {stage} {algo} model: {e}")
    return _load_legacy_model(property_type, algo, stage, model_dir)

def _load_stage_models_dict(property_type, stage, model_dir):
    loaded_dict = {}
    for algo in ['lgb', 'xgb', 'cat', 'rf']:
        m = _load_single_model(property_type, stage, algo, model_dir)
        if m:
            loaded_dict[algo] = m
    return loaded_dict

def _load_first_stage_models(property_type, model_dir):
    global _first_stage_models
    if property_type not in _first_stage_models or not _first_stage_models[property_type]:
        _first_stage_models[property_type] = _load_stage_models_dict(property_type, "first_stage", model_dir)
    return _first_stage_models[property_type]

def _load_second_stage_models(property_type, model_dir):
    global _second_stage_models
    if property_type not in _second_stage_models or not _second_stage_models[property_type]:
        _second_stage_models[property_type] = _load_stage_models_dict(property_type, "second_stage", model_dir)
    return _second_stage_models[property_type]

def _get_models_and_master(property_type):
    """
    指定された物件種別のモデルと、共通の比準想定価格マスタをキャッシュロードする (アンサンブルモデル対応)
    """
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    master = _load_mkt_comparison_master(model_dir)
    first = _load_first_stage_models(property_type, model_dir)
    second = _load_second_stage_models(property_type, model_dir)
    
    # ロード失敗時の確実なフォールバック再試行
    if not first:
        _first_stage_models.pop(property_type, None)
        first = _load_first_stage_models(property_type, model_dir)
    if not second:
        _second_stage_models.pop(property_type, None)
        second = _load_second_stage_models(property_type, model_dir)
        
    return first, second, master

def preload_all_models():
    """
    アプリケーション起動時・初期化時に全物件種別のモデルをメモリへウォームアップロードする
    """
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    _load_mkt_comparison_master(model_dir)
    for ptype in ["mansion", "kodate", "apartment", "tochi"]:
        _load_first_stage_models(ptype, model_dir)
        _load_second_stage_models(ptype, model_dir)

def _detect_property_type_from_dict(property_obj):
    return PropertyTypeDetector._detect_from_dict(property_obj)

def _detect_property_type_from_django(property_obj):
    return PropertyTypeDetector._detect_from_django(property_obj)

def _detect_property_type(property_obj):
    """
    オブジェクト名または型から mansion / kodate / apartment / tochi の種別を自動判定
    (PropertyTypeDetector へ委譲・共通化)
    """
    return PropertyTypeDetector.detect_from_object(property_obj)

def _log_prediction_error(property_obj, property_type, predicted_price, actual_price, features):
    """
    乖離率が +-30% 以上の予測エラー物件をログファイルにCSV出力する (自己改善サイクルの基盤)
    """
    if not actual_price or float(actual_price) <= 0:
        return
        
    # 単位の同調: predicted_priceはモデル出力であり常に万円単位。
    # actual_price は 100,000 以上（10万円以上）の場合は円単位とみなし / 10000.0、それ未満は万円単位とみなす。
    predicted_price_man = float(predicted_price)
    actual_price_val = float(actual_price)
    actual_price_man = (actual_price_val / 10000.0) if actual_price_val >= 100_000.0 else actual_price_val
    
    # 面積0などの不正データのログ記録を除外
    area_val = features.get("area", 0) or features.get("tochi_menseki", 0)
    if not area_val or float(area_val) <= 0:
        return
        
    error_ratio = (predicted_price_man - actual_price_man) / actual_price_man
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
            logging.exception(f"ML: Failed to write prediction error log: {e}")

def _apply_rights_discount(_property_obj, predicted_price: float) -> int:
    """
    (廃止) 借地権・底地などの権利形態による価格ディスカウント補正を行う
    ※ 事後ディスカウント処理は廃止し、機械学習の特徴量（is_shigaika_chousei, is_saikenchiku_fuka, rights_ratio等）としてモデル自身に評価させるように移行しました。
    """
    return int(predicted_price)

def _extract_from_booster(model):
    booster = getattr(model, "booster_", None)
    if booster is not None:
        bfn = getattr(booster, "feature_name", None)
        if callable(bfn):
            try:
                res = bfn()
                if isinstance(res, (list, tuple)):
                    return list(res)
            except Exception:
                pass
    get_booster = getattr(model, "get_booster", None)
    if callable(get_booster):
        try:
            b_obj = get_booster()
            b_names = getattr(b_obj, "feature_names", None)
            if b_names is not None:
                return list(b_names)
        except Exception:
            pass
    return None

def _extract_expected_feature_names(model):
    for attr in ["feature_names_in_", "feature_names_", "feature_name_", "feature_names"]:
        val = getattr(model, attr, None)
        if val is not None:
            try:
                return list(val)
            except Exception:
                pass
    fn = getattr(model, "feature_name", None)
    if callable(fn):
        try:
            res = fn()
            if isinstance(res, (list, tuple)):
                return list(res)
        except Exception:
            pass
    return _extract_from_booster(model)

def _align_features(df, model):
    expected_features = _extract_expected_feature_names(model)
    if not expected_features:
        logging.warning("ML: Could not extract feature names from model. Using DataFrame columns as is.")
        return df
        
    df_aligned = df.copy()
    for col in expected_features:
        if col not in df_aligned.columns:
            df_aligned[col] = 0.0
    return df_aligned[expected_features]


def _apply_smearing_and_ensemble(preds_log_dict, weights, smearing_factor, areas):
    """
    複数アルゴリズムのlog予測値辞書に対し、スミアリング対数補正と正規化重みアンサンブルを適用して金額配列を算出
    """
    total_weight = sum(weights.get(algo, 0.0) for algo in preds_log_dict.keys())
    if total_weight <= 0:
        total_weight = 1.0
        
    num_samples = len(areas)
    ensemble_pred_units = np.zeros(num_samples, dtype=float)
    
    for algo, preds_log in preds_log_dict.items():
        w = weights.get(algo, 0.0) / total_weight
        if w > 0:
            pred_units = np.expm1(preds_log)
            pred_units = np.maximum(pred_units, 0.0)
            ensemble_pred_units += pred_units * w
            
    # スミアリング補正 (過小評価バイアス補正)
    s_factor = float(smearing_factor) if smearing_factor and smearing_factor > 0 else 1.0
    final_preds = ensemble_pred_units * s_factor * np.array(areas, dtype=float)
    return np.maximum(final_preds, 0.0)

def _ensemble_predict(models, df, weights, ptype, smearing_factor=1.0) -> float:
    loaded_weights = {algo: weights.get(algo, 0.25) for algo, model in models.items() if model}
            
    if not loaded_weights:
        logging.error(f"ML DEBUG: No models available for {ptype}. Models dict content: {models}")
        return 0.0
        
    preds_log_dict = {}
    with config_context(assume_finite=True):
        for algo in loaded_weights.keys():
            model = models[algo]
            df_for_pred = _align_features(df, model)
            pred_log = model.predict(df_for_pred)
            preds_log_dict[algo] = np.array(pred_log)
            
    areas = df["area"].values
    final_arr = _apply_smearing_and_ensemble(preds_log_dict, loaded_weights, smearing_factor, areas)
    return float(final_arr[0])

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

def _prop_val(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)

def _prop_to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None

def _serialize_chikunengetsu_field(item):
    chikunengetsu = _prop_val(item, "chikunengetsu", None)
    if not chikunengetsu:
        return _prop_val(item, "chikunengetsuStr", "")
    if hasattr(chikunengetsu, "strftime"):
        return chikunengetsu.strftime("%Y-%m-%d")
    return str(chikunengetsu)

def _serialize_type_specific_fields(data, item, ptype):
    if ptype == "mansion":
        data["senyuMenseki"] = _prop_to_float(_prop_val(item, "senyuMenseki"))
        data["kanrihi"] = _prop_val(item, "kanrihi", None)
        data["syuzenTsumitate"] = _prop_val(item, "syuzenTsumitate", None)
        return

    if ptype in ("kodate", "apartment", "tochi"):
        data["tochiMenseki"] = _prop_to_float(_prop_val(item, "tochiMenseki"))
        data["maguchi"] = _prop_to_float(_prop_val(item, "maguchi"))
        data["roadWidth"] = _prop_to_float(_prop_val(item, "roadWidth"))
        data["setsudou"] = _prop_val(item, "setsudou", "")

    if ptype in ("kodate", "apartment"):
        data["tatemonoMenseki"] = _prop_to_float(_prop_val(item, "tatemonoMenseki"))

    if ptype == "apartment":
        data["grossYield"] = _prop_to_float(_prop_val(item, "grossYield"))
        data["annualRent"] = _prop_val(item, "annualRent", None)

def _serialize_property(item, ptype):
    """Djangoモデルオブジェクトまたは辞書からAPI送信用のシリアライズ辞書を作成"""
    address = _prop_val(item, "address", "")
    if not address:
        addr1 = _prop_val(item, "address1", "") or ""
        addr2 = _prop_val(item, "address2", "") or ""
        address = f"{addr1}{addr2}".strip()

    data = {
        "price": _prop_val(item, "price", None),
        "address": address,
        "station1": _prop_val(item, "station1", ""),
        "railwayWalkMinute1": _prop_val(item, "railwayWalkMinute1", None),
        "kouzou": _prop_val(item, "kouzou", ""),
        "youseki": _prop_to_float(_prop_val(item, "youseki")),
        "kenpei": _prop_to_float(_prop_val(item, "kenpei")),
        "yousekiStr": str(_prop_val(item, "yousekiStr", "") or _prop_val(item, "youseki", "") or ""),
        "kenpeiStr": str(_prop_val(item, "kenpeiStr", "") or _prop_val(item, "kenpei", "") or ""),
        "tochikenri": _prop_val(item, "tochikenri", ""),
        "biko": _prop_val(item, "biko", ""),
        "chikunengetsuStr": _serialize_chikunengetsu_field(item),
    }
    
    _serialize_type_specific_fields(data, item, ptype)
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

def bulk_predict_first_stage(properties_list: list) -> list:
    """
    複数物件に対する一括ベクトル化推論 (一次理論価格)
    500〜1,000件単位で一括行列演算を行い、通信オーバーヘッドを排除します。
    """
    if not properties_list:
        return []
        
    from package.ml.features import FEATURE_SETS, build_features_batch
    
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    smearing_factors = _load_smearing_factors(model_dir)
    dynamic_weights = _load_ensemble_weights(model_dir)
    grouped_props = _group_properties_by_type(properties_list)
    final_results = [0] * len(properties_list)
    
    for ptype, items in grouped_props.items():
        first_models, _, mkt_master = _get_models_and_master(ptype)
        if not first_models:
            continue
            
        sub_indices = [idx for idx, _ in items]
        sub_props = [p for _, p in items]
        features_list = build_features_batch(sub_props, ptype, mkt_comparison_master=mkt_master)
        feature_cols = FEATURE_SETS.get(ptype, {}).get("first", [])
        df = _prepare_df_features(features_list, feature_cols)
        
        weights = dynamic_weights.get(ptype, {}).get("first") or _get_default_weights(ptype)
        smearing_factor = smearing_factors.get(ptype, {}).get("first", 1.0)
        
        preds_arr = _predict_batch_ensemble(first_models, weights, smearing_factor, df)
        for i, val in enumerate(preds_arr):
            original_idx = sub_indices[i]
            final_results[original_idx] = _apply_rights_discount(sub_props[i], int(max(0, val)))
            
    return final_results

def _get_default_weights(ptype):
    if ptype == 'mansion':
        return {'lgb': 0.35, 'xgb': 0.35, 'cat': 0.15, 'rf': 0.15}
    if ptype in ['kodate', 'apartment']:
        return {'lgb': 0.35, 'xgb': 0.45, 'cat': 0.1, 'rf': 0.1}
    return {'lgb': 0.3, 'xgb': 0.25, 'cat': 0.25, 'rf': 0.2}

def _prepare_df_features(features_list, feature_cols):
    df = pd.DataFrame(features_list)
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0
    df = df[feature_cols].copy()
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype('category').cat.codes
    return df

def _group_properties_by_type(properties_list):
    grouped = {}
    for idx, prop in enumerate(properties_list):
        ptype = _detect_property_type(prop)
        grouped.setdefault(ptype, []).append((idx, prop))
    return grouped

def _predict_batch_ensemble(models, weights, smearing_factor, df):
    preds_log_dict = {}
    with config_context(assume_finite=True):
        for algo, model in models.items():
            if model and weights.get(algo, 0) > 0:
                df_for_pred = _align_features(df, model)
                pred_log = model.predict(df_for_pred)
                preds_log_dict[algo] = np.array(pred_log)
    areas = df["area"].values
    return _apply_smearing_and_ensemble(preds_log_dict, weights, smearing_factor, areas)

def _attach_image_scores(features_list, sub_indices, interior_scores, layout_scores):
    for i, idx in enumerate(sub_indices):
        int_score = interior_scores[i] if interior_scores and i < len(interior_scores) else 3.0
        lay_score = layout_scores[i] if layout_scores and i < len(layout_scores) else 3.0
        features_list[i]["interior_score"] = float(int_score) if int_score is not None else 3.0
        features_list[i]["layout_score"] = float(lay_score) if lay_score is not None else 3.0

def bulk_predict_second_stage(properties_list: list, interior_scores=None, layout_scores=None) -> list:
    """
    複数物件に対する一括ベクトル化推論 (二次理論価格: 画像スコア込み)
    """
    if not properties_list:
        return []
        
    from package.ml.features import FEATURE_SETS, build_features_batch
    
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    smearing_factors = _load_smearing_factors(model_dir)
    dynamic_weights = _load_ensemble_weights(model_dir)
    grouped_props = _group_properties_by_type(properties_list)
    final_results = [0] * len(properties_list)
    
    for ptype, items in grouped_props.items():
        _, second_models, mkt_master = _get_models_and_master(ptype)
        if not second_models:
            continue
            
        sub_indices = [idx for idx, _ in items]
        sub_props = [p for _, p in items]
        features_list = build_features_batch(sub_props, ptype, mkt_comparison_master=mkt_master)
        _attach_image_scores(features_list, sub_indices, interior_scores, layout_scores)
        
        feature_cols = FEATURE_SETS.get(ptype, {}).get("second", [])
        df = _prepare_df_features(features_list, feature_cols)
        
        weights = dynamic_weights.get(ptype, {}).get("second") or _get_default_weights(ptype)
        smearing_factor = smearing_factors.get(ptype, {}).get("second", 1.0)
        
        preds_arr = _predict_batch_ensemble(second_models, weights, smearing_factor, df)
        for i, val in enumerate(preds_arr):
            original_idx = sub_indices[i]
            final_results[original_idx] = _apply_rights_discount(sub_props[i], int(max(0, val)))
            
    return final_results

def predict_first_stage_local(property_obj) -> int:
    """
    一次理論価格予測 (ローカル直接推論)
    """
    preds = bulk_predict_first_stage([property_obj])
    predicted_val = preds[0] if preds else 0
    
    ptype = _detect_property_type(property_obj)
    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)
    actual_price = get_attr(property_obj, 'price', 0)
    _log_prediction_error(property_obj, ptype, predicted_val, actual_price, {})
    
    return predicted_val

def predict_second_stage_local(property_obj, interior_score: float, layout_score: float) -> int:
    """
    二次理論価格予測 (ローカル直接推論)
    """
    preds = bulk_predict_second_stage([property_obj], [interior_score], [layout_score])
    predicted_val = preds[0] if preds else 0
    
    ptype = _detect_property_type(property_obj)
    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)
    actual_price = get_attr(property_obj, 'price', 0)
    _log_prediction_error(property_obj, ptype, predicted_val, actual_price, {"interior_score": interior_score, "layout_score": layout_score})
    
    return predicted_val

# -*- coding: utf-8 -*-
import os
import sys
import pandas as pd
import numpy as np
import joblib
import gc
from sklearn.model_selection import KFold
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoostRegressor

# Django設定のロード
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import realestateSettings
realestateSettings.configure()

import logging
from package.utils.logging_config import configure_logging
configure_logging()
logger = logging.getLogger(__name__)

def print(*args, **kwargs):
    kwargs.pop("flush", None)
    kwargs.pop("end", None)
    msg = " ".join(str(a) for a in args)
    logger.info(msg)

from package.models.evaluation import PropertyEvaluation
from package.ml.features import FEATURE_SETS, build_features, calculate_chikunen
from django.apps import apps
from scipy.optimize import minimize

COMPANIES = [
    "mitsui", "sumifu", "tokyu", "nomura", "misawa",
    "smtrc", "sumai1", "mizuho", "odakyu", "afr",
    "sekisui", "daiwa", "totate", "athome", "homes",
    "seibu", "keikyu", "sotetsu", "keisei", "daikyo",
    "rearie", "heim", "sumirin", "keio"
]

def calculate_mape(y_true, y_pred):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    y_true = np.where(y_true == 0, 1, y_true)
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100

def _load_company_properties(company, qs, duplicate_urls, eval_map):
    try:
        qs.count()
    except Exception:
        return []
        
    records = []
    for p in qs:
        price = getattr(p, 'price', 0)
        if not price or price <= 0:
            continue
        
        page_url = getattr(p, 'pageUrl', '')
        if page_url in duplicate_urls:
            continue
            
        price_man = float(price) / 10000.0
        interior_score, layout_score = eval_map.get(page_url, (3.0, 3.0))
        
        records.append({
            "obj": p,
            "price": price_man,
            "company": company,
            "interior_score": interior_score,
            "layout_score": layout_score
        })
    return records

def load_all_properties_from_db():
    """
    全24社の全物件種別のデータをDBから網羅的にロードする
    """
    print("Loading properties from DB (All 24 Portals)...")
    
    # N+1問題解消のため、評価レコードを一括ロードして辞書化
    print("Caching property evaluations...")
    eval_map = {}
    for e in PropertyEvaluation.objects.all().only("property_url", "interior_score", "layout_score"):
        eval_map[e.property_url] = (
            float(e.interior_score) if e.interior_score is not None else 3.0,
            float(e.layout_score) if e.layout_score is not None else 3.0
        )
    print(f"Cached {len(eval_map)} evaluations.")

    # 重複物件のURLキャッシュ (名寄せされた重複分を排除するため)
    print("Caching duplicate property URLs...")
    duplicate_urls = set(
        PropertyEvaluation.objects.filter(duplicate_of__isnull=False)
        .values_list("property_url", flat=True)
    )
    print(f"Found {len(duplicate_urls)} duplicate properties to exclude.")

    app_config = apps.get_app_config("package")
    queries = {
        "mansion": [],
        "kodate": [],
        "apartment": [],
        "tochi": []
    }
    
    for model in app_config.get_models():
        model_name = model.__name__.lower()
        matched_company = None
        for c in COMPANIES:
            if model_name.startswith(c):
                matched_company = c
                break
        if not matched_company:
            continue
            
        suffix = model_name[len(matched_company):]
        if "mansion" in suffix:
            queries["mansion"].append((matched_company, model.objects.all()))
        elif "apartment" in suffix:
            queries["apartment"].append((matched_company, model.objects.all()))
        elif "tochi" in suffix:
            queries["tochi"].append((matched_company, model.objects.all()))
        elif "kodate" in suffix:
            queries["kodate"].append((matched_company, model.objects.all()))
            
    data_by_type = {"mansion": [], "kodate": [], "apartment": [], "tochi": []}
    
    for ptype, list_qs in queries.items():
        for company, qs in list_qs:
            data_by_type[ptype].extend(_load_company_properties(company, qs, duplicate_urls, eval_map))
                
    print(f"Loaded Mansion: {len(data_by_type['mansion'])}, Kodate: {len(data_by_type['kodate'])}, Apartment: {len(data_by_type['apartment'])}, Tochi: {len(data_by_type['tochi'])}")
    return data_by_type

def _extract_unit_price_record(p, price, ptype):
    address1 = getattr(p, 'address1', '') or ''
    address2 = getattr(p, 'address2', '') or ''
    
    chikunengetsu = getattr(p, 'chikunengetsu', None)
    if not chikunengetsu:
        chikunengetsu = getattr(p, 'chikunengetsuStr', None)
    chikunen = calculate_chikunen(chikunengetsu)
    
    senyu_menseki = getattr(p, 'senyuMenseki', 0.0)
    tatemono_menseki = getattr(p, 'tatemonoMenseki', 0.0)
    tochi_menseki = getattr(p, 'tochiMenseki', 0.0)
    
    try:
        if ptype == 'tochi':
            eval_area = float(tochi_menseki) if tochi_menseki is not None else 0.0
        elif ptype == 'mansion':
            eval_area = float(senyu_menseki) if senyu_menseki is not None else 0.0
            if eval_area > 500.0:
                eval_area = 0.0
        else:
            eval_area = float(tatemono_menseki) if tatemono_menseki is not None else 0.0
    except (ValueError, TypeError):
        eval_area = 0.0
    
    if eval_area > 0 and price > 0:
        return {
            "pref": address1,
            "city": address2,
            "ptype": ptype,
            "age_band": int(chikunen // 10),
            "unit_price": price / eval_area
        }
    return None

def build_mkt_comparison_master(data_by_type):
    """
    ロードした全データからエリア別の「平均平米単価」マスタを作成
    """
    print("Building market comparison master...")
    all_units = []
    
    for ptype, items in data_by_type.items():
        for item in items:
            rec = _extract_unit_price_record(item["obj"], item["price"], ptype)
            if rec:
                all_units.append(rec)
                
    mkt_master = {}
    df = pd.DataFrame(all_units)
    if not df.empty:
        gp = df.groupby(["pref", "city", "ptype", "age_band"])["unit_price"].mean().reset_index()
        for _, row in gp.iterrows():
            key = (row["pref"], row["city"], row["ptype"], int(row["age_band"]))
            mkt_master[key] = row["unit_price"]
            
    print(f"Created market comparison master with {len(mkt_master)} entries.")
    return mkt_master

def _calculate_dummy_valuation_metrics(ptype, area, tochi_area, average_land_price, chikunen, rng):
    digest_volume_ratio = 0.0
    surplus_volume_potential = 0.0
    non_conforming_flag = 0
    if ptype in ['kodate', 'apartment']:
        digest_volume_ratio = (area / tochi_area) * 100.0
        surplus_volume_potential = max(0.0, 200.0 - digest_volume_ratio)
        if digest_volume_ratio > 200.0:
            non_conforming_flag = 1
            
    annual_rent = 0
    gross_yield = 0.0
    income_approach_value = 0
    if ptype in ['mansion', 'apartment']:
        gross_yield = rng.uniform(0.05, 0.15)
        annual_rent = int(area * rng.uniform(1.5, 3.5)) * 12
        income_approach_value = int(annual_rent / gross_yield)
        
    cost_unit = 25.0 if ptype == 'mansion' else 15.0
    lifespan = 47 if ptype == 'mansion' else 22
    remaining_rate = max(0.1, (lifespan - chikunen) / lifespan)
    
    if ptype == 'mansion':
        cost_approach_value = (area * 0.2) * (average_land_price / 10000.0) + (area * cost_unit * remaining_rate)
    elif ptype == 'tochi':
        cost_approach_value = tochi_area * (average_land_price / 10000.0)
    else:
        cost_approach_value = tochi_area * (average_land_price / 10000.0) + (area * cost_unit * remaining_rate)
        
    mkt_comparison_value = area * (average_land_price / 10000.0) * 0.95
    
    return {
        "digest_volume_ratio": digest_volume_ratio,
        "surplus_volume_potential": surplus_volume_potential,
        "non_conforming_flag": non_conforming_flag,
        "annual_rent": annual_rent,
        "gross_yield": gross_yield,
        "income_approach_value": income_approach_value,
        "cost_approach_value": cost_approach_value,
        "mkt_comparison_value": mkt_comparison_value,
    }

def _generate_single_dummy_record(ptype, rng):
    if ptype == 'tochi':
        tochi_area = rng.uniform(50.0, 300.0)
        area = tochi_area
    else:
        area = rng.uniform(25.0, 100.0) if ptype == 'mansion' else rng.uniform(60.0, 150.0)
        tochi_area = 0.0 if ptype == 'mansion' else rng.uniform(70.0, 200.0)
        
    chikunen = rng.uniform(1.0, 45.0)
    walk_min = rng.integers(1, 20)
    kanrihi = int(area * 200) if ptype == 'mansion' else 0
    syuzen = int(area * 150) if ptype == 'mansion' else 0
    pop_growth = rng.uniform(-1.0, 2.0)
    income = rng.integers(3000, 12000)
    passenger_volume = rng.integers(5000, 700000)
    average_land_price = rng.integers(150000, 3000000)
    interior_score = rng.uniform(1.5, 4.8)
    layout_score = rng.uniform(2.0, 4.8)
    
    metrics = _calculate_dummy_valuation_metrics(ptype, area, tochi_area, average_land_price, chikunen, rng)
    
    base_price = (area * (average_land_price / 10000.0)) - (chikunen * 40.0) - (walk_min * 50.0)
    area_multiplier = 1.0 + (income / 30000.0) + (passenger_volume / 5000000.0) + pop_growth * 0.05
    img_multiplier = 0.85 + (interior_score + layout_score) * 0.03
    
    if ptype == 'apartment':
        base_price = metrics["annual_rent"] * 10
        
    price = max(1000, int(base_price * area_multiplier * img_multiplier + rng.normal(0, 300)))
    
    rand_val = rng.random()
    if rand_val < 0.02:
        price = 5
    elif rand_val < 0.04:
        area = 1.0
        
    return {
        "price": price,
        "area": area,
        "tochi_menseki": tochi_area,
        "chikunen": chikunen,
        "walk_min": walk_min,
        "kanrihi": kanrihi,
        "syuzen": syuzen,
        "pop_growth": pop_growth,
        "income": income,
        "passenger_volume": passenger_volume,
        "average_land_price": average_land_price,
        "estimated_rosenka_price": int(average_land_price * 0.8),
        "estimated_fixed_asset_price": int(average_land_price * 0.7),
        "digest_volume_ratio": metrics["digest_volume_ratio"],
        "surplus_volume_potential": metrics["surplus_volume_potential"],
        "non_conforming_flag": metrics["non_conforming_flag"],
        "cost_approach_value": metrics["cost_approach_value"],
        "mkt_comparison_value": metrics["mkt_comparison_value"],
        "income_approach_value": metrics["income_approach_value"],
        "gross_yield": metrics["gross_yield"],
        "annual_rent": metrics["annual_rent"],
        "interior_score": interior_score,
        "layout_score": layout_score,
        "is_shin_taishin": 1 if chikunen <= 45.0 else 0,
        "flood_risk_level": rng.integers(0, 5),
        "landslide_risk_level": rng.integers(0, 3),
        "max_youseki": 200.0 if ptype == 'mansion' else rng.choice([100.0, 150.0, 200.0]),
        "max_kenpei": 60.0 if ptype == 'mansion' else rng.choice([40.0, 50.0, 60.0]),
        "prefecture": "東京都",
        "city": "世田谷区",
        "station": "世田谷駅",
        "company": "mitsui",
        "kouzou": "木造" if ptype == 'kodate' else "RC",
        "maguchi": rng.uniform(2.0, 10.0),
        "road_width": rng.uniform(3.0, 6.0),
        "setback_ratio": 0.0,
        "actual_volume_limit": 200.0,
        "volume_digest_factor": 1.0,
        "road_condition_factor": 1.0,
        "frontage_penalty_factor": 1.0,
        "residual_land_value": 0.0,
        "road_direction": "南",
        "road_type": "公道",
        "road_structure": "中間地",
        "max_building_area": area * 0.6,
        "max_floor_area": area * 2.0,
        "kagechi_ratio": 1.0,
        "total_population": 150000,
        "income_growth_rate": 0.5,
        "land_price_growth_rate": 1.2,
        "effective_walk_min": float(walk_min),
        "population_density": 5000.0,
        "kouzou_lifespan_ratio": min(2.0, chikunen / 30.0),
        "is_shigaika_chousei": 0.0,
        "is_saikenchiku_fuka": 0.0,
        "rights_ratio": 1.0,
        "potential_floor_area": area if ptype == 'mansion' else tochi_area * 2.0,
        "scale_discount": 1.0,
    }

def generate_dummy_data(ptype, num_records=500):
    """
    種別ごとのダミー学習データを生成
    """
    print(f"Generating dummy data for {ptype}...")
    rng = np.random.default_rng(42)
    records = [_generate_single_dummy_record(ptype, rng) for _ in range(num_records)]
    return pd.DataFrame(records)

def clean_training_data(df, ptype):
    """
    IQR法およびIsolation Forestを用いた学習データの自動クレンジング処理
    """
    initial_count = len(df)
    if initial_count == 0:
        return df
        
    print(f"Cleaning training data for {ptype} (initial records: {initial_count})...")
    
    # 1. 物理的な異常値の機械的除外
    df = df[(df["price"] > 50) & (df["area"] > 5.0) & (df["chikunen"] >= 0) & (df["chikunen"] < 100)].copy()
    physical_clean_count = len(df)
    if physical_clean_count < initial_count:
        print(f"  Removed {initial_count - physical_clean_count} records due to physical limit filters.")
        
    if len(df) < 20:
        # データが少なすぎる場合はそれ以上の統計的除外をスキップ
        return df

    # 2. IQR法による価格と面積の外れ値除外 (都心高級レジデンスの切り捨てを防ぐため3.5倍IQRおよび上限保証)
    for col in ["price", "area"]:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower_bound = max(0.0, q1 - 3.5 * iqr)
        upper_bound = q3 + 3.5 * iqr
        if col == "price":
            upper_bound = max(upper_bound, 60000.0)  # 6億円までは現実的な高級レジデンス・ビルとして学習
        elif col == "area" and ptype == "mansion":
            upper_bound = max(upper_bound, 250.0)   # 250㎡までのプレミアム住戸を学習に保持
        
        pre_count = len(df)
        df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)].copy()
        post_count = len(df)
        if post_count < pre_count:
            print(f"  [IQR] Removed {pre_count - post_count} outlier records based on '{col}' (Bounds: {lower_bound:.1f} - {upper_bound:.1f})")

    # 3. Isolation Forestによる多次元外れ値の検出と除外 (データ数が100件以上の場合のみ)
    if len(df) >= 100:
        from sklearn.ensemble import IsolationForest
        features_for_outlier = ["price", "area", "chikunen"]
        if "tochi_menseki" in df.columns and ptype != "mansion":
            features_for_outlier.append("tochi_menseki")
            
        iso = IsolationForest(contamination=0.02, random_state=42)
        x_outlier = df[features_for_outlier].fillna(0)
        
        preds = iso.fit_predict(x_outlier)
        pre_count = len(df)
        df = df[preds == 1].copy()
        post_count = len(df)
        if post_count < pre_count:
            print(f"  [IsolationForest] Removed {pre_count - post_count} multi-dimensional outlier records (contamination=2%).")
            
    print(f"Cleaned training data for {ptype}. Final records: {len(df)}")
    return df

def _get_regressor(name, params):
    ml_threads = int(os.getenv("ML_NUM_THREADS", "-1"))
    if name == "lgb":
        return lgb.LGBMRegressor(random_state=42, verbose=-1, n_jobs=ml_threads, n_estimators=100, **params)
    elif name == "xgb":
        return xgb.XGBRegressor(random_state=42, n_jobs=ml_threads, n_estimators=100, **params)
    elif name == "cat":
        return CatBoostRegressor(random_state=42, verbose=0, thread_count=ml_threads, iterations=200, **params)
    elif name == "rf":
        return RandomForestRegressor(
            random_state=42,
            n_jobs=ml_threads,
            n_estimators=params.get("n_estimators", 100),
            max_depth=params.get("max_depth", None),
            min_samples_leaf=params.get("min_samples_leaf", 5),
            max_features=params.get("max_features", "sqrt")
        )
    raise ValueError(f"Unknown algorithm: {name}")

def tune_hyperparameters(X, y, algo_name) -> dict:
    """
    簡易的なハイパーパラメータグリッドサーチを行い、
    3-Fold CV で最も MAPE が良かったパラメータの辞書を返します。
    """
    if len(X) > 5000:
        tune_idx = np.random.default_rng(42).choice(len(X), size=5000, replace=False)
        X_tune = X.iloc[tune_idx].reset_index(drop=True)
        y_tune = y.iloc[tune_idx].reset_index(drop=True)
    else:
        X_tune, y_tune = X.reset_index(drop=True), y.reset_index(drop=True)

    kf = KFold(n_splits=3, shuffle=True, random_state=42)
    best_params = {}
    best_mape = float('inf')
    
    grids = {
        "lgb": [
            {"learning_rate": 0.05, "num_leaves": 31, "max_depth": 6, "min_child_samples": 20},
            {"learning_rate": 0.1, "num_leaves": 63, "max_depth": 8, "min_child_samples": 10}
        ],
        "xgb": [
            {"learning_rate": 0.05, "max_depth": 6, "subsample": 0.8},
            {"learning_rate": 0.1, "max_depth": 6, "subsample": 0.9}
        ],
        "cat": [
            {"learning_rate": 0.08, "depth": 6, "l2_leaf_reg": 3}
        ],
        "rf": [
            {"n_estimators": 100, "max_depth": 15, "min_samples_leaf": 5}
        ]
    }
    
    param_grid = grids.get(algo_name, [{}])
    for params in param_grid:
        mapes = []
        for train_idx, val_idx in kf.split(X_tune):
            x_train, x_val = X_tune.iloc[train_idx], X_tune.iloc[val_idx]
            y_train, y_val = y_tune.iloc[train_idx], y_tune.iloc[val_idx]
            
            model = _get_regressor(algo_name, params)
            model.fit(x_train, y_train)
            preds_log = model.predict(x_val)
            val_areas = x_val["area"].values
            mapes.append(calculate_mape(np.expm1(y_val) * val_areas, np.expm1(preds_log) * val_areas))
            
        avg_mape = np.mean(mapes)
        if avg_mape < best_mape:
            best_mape = avg_mape
            best_params = params
            
    return best_params

def print_feature_importance(model, algo_name, feature_cols):
    """
    学習済みモデルから特徴量重要度を集計し、上位10項目を出力します。
    """
    try:
        if algo_name == "lgb":
            importances = model.feature_importances_
        elif algo_name == "xgb":
            importances = model.feature_importances_
        elif algo_name == "cat":
            importances = model.get_feature_importance()
        elif algo_name == "rf":
            importances = model.feature_importances_
        else:
            return
            
        feat_imp = pd.Series(importances, index=feature_cols).sort_values(ascending=False)
        print(f"  [{algo_name}] Feature Importance (Top 10):")
        for name, val in feat_imp.head(10).items():
            print(f"    - {name}: {val:.4f}")
    except Exception as e:
        print(f"  [{algo_name}] Failed to compute feature importance: {e}")

from sklearn.model_selection import RepeatedKFold

class TrainedEnsemble(dict):
    def __init__(self, models, weights=None, smearing_factor=1.0):
        super().__init__(models)
        self.weights = weights or {}
        self.smearing_factor = smearing_factor

def train_and_compare(df, feature_cols, stage_name) -> TrainedEnsemble:
    """
    指定された特徴量を用いてモデルをチューニング＆学習し、
    Repeated 5-Fold CV (計15サイクル) 評価を行った上で、全データで最終学習したモデル、
    データ駆動最適アンサンブル重み、およびDuan's Smearing補正係数を返します。
    """
    X = df[feature_cols].copy()
    y = np.log1p(df["price"] / df["area"]) # 平米単価の対数変換 (log1p) を施す
    
    # カテゴリカル変数の処理 (Label Encoding)
    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = X[col].astype('category').cat.codes
            
    # 大規模データセット（3,000件超）では 3-Fold CV で高速・高精度評価。極小テストデータ（50件未満）では 2-Fold で瞬時検証
    if len(df) > 3000:
        rkf = KFold(n_splits=3, shuffle=True, random_state=42)
        cv_desc = "3-Fold Fast CV"
    elif len(df) < 50:
        rkf = KFold(n_splits=2, shuffle=True, random_state=42)
        cv_desc = "2-Fold Quick CV"
    else:
        rkf = RepeatedKFold(n_splits=5, n_repeats=3, random_state=42)
        cv_desc = "15-Cycle Repeated CV"
    algos = ['lgb', 'xgb', 'cat', 'rf']
    
    print(f"\n--- Tuning & Cross-Validating models for Stage: {stage_name} ({cv_desc}) ---", flush=True)
    
    trained_models = {}
    best_params_dict = {}
    
    # 事前チューニングの実行（本番規模の十分なデータ数がある場合のみ）
    for name in algos:
        if len(df) >= 100:
            print(f"Tuning hyperparameters for {name}...", flush=True)
            best_params_dict[name] = tune_hyperparameters(X, y, name)
            print(f"Best params for {name}: {best_params_dict[name]}", flush=True)
        else:
            best_params_dict[name] = {}
            
    oof_preds = {name: np.zeros(len(df)) for name in algos}
    oof_counts = {name: np.zeros(len(df)) for name in algos}

    for name in algos:
        mapes = []
        maes = []
        r2s = []
        params = best_params_dict[name]
        
        for train_idx, val_idx in rkf.split(X):
            x_train, x_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            fold_model = _get_regressor(name, params)
            fold_model.fit(x_train, y_train)
            preds_log = fold_model.predict(x_val)
            
            oof_preds[name][val_idx] += preds_log
            oof_counts[name][val_idx] += 1
            
            # 元の万円スケールに逆対数変換 ＆ 面積乗算して総額に戻して評価
            val_areas = df.iloc[val_idx]["area"].values
            preds_actual = np.expm1(preds_log) * val_areas
            y_val_actual = np.expm1(y_val) * val_areas
            
            mapes.append(calculate_mape(y_val_actual, preds_actual))
            maes.append(mean_absolute_error(y_val_actual, preds_actual))
            r2s.append(r2_score(y_val_actual, preds_actual))
            
            del fold_model, x_train, x_val, y_train, y_val
            gc.collect()
            
        avg_mape = np.mean(mapes)
        avg_mae = np.mean(maes)
        avg_r2 = np.mean(r2s)
        print(f"[{name}] 5-Fold CV Scores:")
        print(f"  - MAPE: {avg_mape:.2f}%")
        print(f"  - MAE:  {avg_mae:.2f}万円")
        print(f"  - R2:   {avg_r2:.4f}")
        
        # 全データで本番学習
        final_model = _get_regressor(name, params)
            
        final_model.fit(X, y)
        print_feature_importance(final_model, name, feature_cols)
        trained_models[name] = final_model
        
    for name in algos:
        oof_preds[name] /= np.maximum(1, oof_counts[name])
        
    # OOF予測に基づく最適アンサンブル重みのデータ駆動算出 (SLSQP minimizer)
    oof_unit_preds = np.column_stack([np.maximum(0, np.expm1(oof_preds[name])) for name in algos])
    val_areas = df["area"].values
    y_actual = df["price"].values
    
    def objective(weights):
        w = np.array(weights)
        s = np.sum(w)
        if s <= 0: return 9999.0
        w_norm = w / s
        pred_price = val_areas * (oof_unit_preds @ w_norm)
        return calculate_mape(y_actual, pred_price)
        
    init_weights = [1.0 / len(algos)] * len(algos)
    bounds = [(0.0, 1.0)] * len(algos)
    constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})
    
    try:
        res = minimize(objective, init_weights, method='SLSQP', bounds=bounds, constraints=constraints)
        if res.success:
            opt_w = res.x / np.sum(res.x)
        else:
            opt_w = np.array(init_weights)
    except Exception as e:
        print(f"Ensemble weight optimization fallback: {e}")
        opt_w = np.array(init_weights)
        
    optimal_weights = {algos[i]: float(opt_w[i]) for i in range(len(algos))}
    print(f"Optimized Ensemble Weights: {optimal_weights}")
    
    # Duan's Smearing Estimator (対数変換過小予測バイアス厳密数理補正: E[Y] = exp(mu + sigma^2/2))
    ensemble_pred_units = oof_unit_preds @ opt_w
    actual_unit_prices = df["price"].values / np.maximum(0.1, df["area"].values)
    log_residuals = np.log(np.maximum(0.1, actual_unit_prices)) - np.log(np.maximum(0.1, ensemble_pred_units))
    if len(log_residuals) >= 10:
        clean_log_res = log_residuals[(log_residuals >= np.percentile(log_residuals, 2)) & (log_residuals <= np.percentile(log_residuals, 98))]
    else:
        clean_log_res = log_residuals
    mean_bias = float(np.mean(clean_log_res)) if len(clean_log_res) > 0 else 0.0
    var_res = float(np.var(clean_log_res)) if len(clean_log_res) > 0 else 0.0
    smearing_factor = float(np.exp(mean_bias + var_res / 2.0))
    smearing_factor = max(0.90, min(1.40, smearing_factor))
    print(f"Duan's Smearing Correction Factor (mean_bias={mean_bias:.4f}, var={var_res:.4f}): {smearing_factor:.4f}")
    
    return TrainedEnsemble(trained_models, optimal_weights, smearing_factor)

def main():
    data_by_type = load_all_properties_from_db()
    
    # 統計マスタの構築
    mkt_master = build_mkt_comparison_master(data_by_type)
    
    # 保存ディレクトリの設定 (相対パス解決)
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    os.makedirs(model_dir, exist_ok=True)
    
    # マスタの保存
    joblib.dump(mkt_master, os.path.join(model_dir, "mkt_comparison_master.joblib"))
    
    # 物件種別ごとの特徴量セット定義 (features.pyから一元参照)
    feature_sets = FEATURE_SETS
    
    all_ensemble_weights = {}
    all_smearing_factors = {}
    
    # 各物件種別の学習を実行
    ptypes = list(data_by_type.keys())
    for ptype in ptypes:
        items = data_by_type[ptype]
        if len(items) > 15000:
            print(f"Sampling 15,000 representative properties from {len(items):,} total records for efficient training...", flush=True)
            rng = np.random.default_rng(42)
            indices = rng.choice(len(items), size=15000, replace=False)
            items = [items[i] for i in indices]

        print("\n=========================================", flush=True)
        print(f"Training models for Property Type: {ptype} (records: {len(items):,})", flush=True)
        print("=========================================", flush=True)
        
        # DBデータをもとに特徴量データフレームを作成
        records = []
        for i, item in enumerate(items):
            p = item["obj"]
            feats = build_features(p, ptype, mkt_comparison_master=mkt_master)
            feats["price"] = item["price"]
            feats["interior_score"] = item["interior_score"]
            feats["layout_score"] = item["layout_score"]
            records.append(feats)
            if (i + 1) % 5000 == 0:
                print(f"  Extracted features for {i+1:,}/{len(items):,} items...", flush=True)
            
        df = pd.DataFrame(records)
        
        # 件数が少ない場合はダミーデータを適用
        if len(df) < 10:
            print(f"Not enough real data for {ptype} in DB. Generating dummy data.")
            df = generate_dummy_data(ptype)
            
        # 学習データのクレンジング（外れ値の自動除外）を実行
        df = clean_training_data(df, ptype)
            
        # 一次モデルの訓練と保存 (LGB, XGB, Cat, RF)
        first_cols = feature_sets[ptype]["first"]
        first_ensemble = train_and_compare(df, first_cols, f"{ptype} - First Stage (No Image)")
        all_ensemble_weights.setdefault(ptype, {})["first"] = first_ensemble.weights
        all_smearing_factors.setdefault(ptype, {})["first"] = first_ensemble.smearing_factor
        for algo, model in first_ensemble.items():
            joblib.dump(model, os.path.join(model_dir, f"{ptype}_first_stage_{algo}.joblib"))
        
        # 二次モデルの訓練と保存 (LGB, XGB, Cat, RF)
        second_cols = feature_sets[ptype]["second"]
        second_ensemble = train_and_compare(df, second_cols, f"{ptype} - Second Stage (With Image)")
        all_ensemble_weights.setdefault(ptype, {})["second"] = second_ensemble.weights
        all_smearing_factors.setdefault(ptype, {})["second"] = second_ensemble.smearing_factor
        for algo, model in second_ensemble.items():
            joblib.dump(model, os.path.join(model_dir, f"{ptype}_second_stage_{algo}.joblib"))
            
        # メモリ解放
        data_by_type[ptype] = []
        del items, df, records, first_ensemble, second_ensemble
        gc.collect()
        
    joblib.dump(all_ensemble_weights, os.path.join(model_dir, "ensemble_weights.joblib"))
    joblib.dump(all_smearing_factors, os.path.join(model_dir, "smearing_factors.joblib"))
    print("\nMachine learning training pipeline completed successfully for all property types with ensemble support, optimal weights, and smearing bias correction!")

if __name__ == "__main__":
    main()


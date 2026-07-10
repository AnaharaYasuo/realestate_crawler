# -*- coding: utf-8 -*-
import os
import sys
import datetime
import pandas as pd
import numpy as np
import joblib
import gc
from sklearn.model_selection import KFold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoostRegressor

# Django設定のロード
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import realestateSettings
realestateSettings.configure()

from package.models.mitsui import MitsuiMansion, MitsuiKodate, MitsuiInvestmentKodate, MitsuiInvestmentApartment
from package.models.sumifu import SumifuMansion, SumifuKodate, SumifuInvestmentKodate, SumifuInvestmentApartment
from package.models.tokyu import TokyuMansion, TokyuKodate, TokyuInvestmentKodate, TokyuInvestmentApartment
from package.models.nomura import NomuraMansion, NomuraKodate, NomuraInvestmentKodate, NomuraInvestmentApartment
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaInvestmentKodate, MisawaInvestmentApartment
from package.models.evaluation import PropertyEvaluation
from package.ml.features import build_features, calculate_chikunen

def calculate_mape(y_true, y_pred):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    y_true = np.where(y_true == 0, 1, y_true)
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100

def load_all_properties_from_db():
    """
    全5社の全物件種別のデータをDBからロードする
    """
    print("Loading properties from DB...")
    
    # N+1問題解消のため、評価レコードを一括ロードして辞書化
    print("Caching property evaluations...")
    eval_map = {}
    for e in PropertyEvaluation.objects.all().only("property_url", "interior_score", "layout_score"):
        eval_map[e.property_url] = (
            float(e.interior_score) if e.interior_score is not None else 3.0,
            float(e.layout_score) if e.layout_score is not None else 3.0
        )
    print(f"Cached {len(eval_map)} evaluations.")

    queries = {
        "mansion": [
            ("mitsui", MitsuiMansion.objects.all()),
            ("sumifu", SumifuMansion.objects.all()),
            ("tokyu", TokyuMansion.objects.all()),
            ("nomura", NomuraMansion.objects.all()),
            ("misawa", MisawaMansion.objects.all())
        ],
        "kodate": [
            ("mitsui", MitsuiKodate.objects.all()),
            ("sumifu", SumifuKodate.objects.all()),
            ("tokyu", TokyuKodate.objects.all()),
            ("nomura", NomuraKodate.objects.all()),
            ("misawa", MisawaKodate.objects.all()),
            ("mitsui_inv", MitsuiInvestmentKodate.objects.all()),
            ("sumifu_inv", SumifuInvestmentKodate.objects.all()),
            ("tokyu_inv", TokyuInvestmentKodate.objects.all()),
            ("nomura_inv", NomuraInvestmentKodate.objects.all()),
            ("misawa_inv", MisawaInvestmentKodate.objects.all())
        ],
        "apartment": [
            ("mitsui_inv", MitsuiInvestmentApartment.objects.all()),
            ("sumifu_inv", SumifuInvestmentApartment.objects.all()),
            ("tokyu_inv", TokyuInvestmentApartment.objects.all()),
            ("nomura_inv", NomuraInvestmentApartment.objects.all()),
            ("misawa_inv", MisawaInvestmentApartment.objects.all())
        ]
    }
    
    data_by_type = {"mansion": [], "kodate": [], "apartment": []}
    
    for ptype, list_qs in queries.items():
        for company, qs in list_qs:
            for p in qs:
                price = getattr(p, 'price', 0)
                if not price or price <= 0:
                    continue
                
                # DB上の「円」単位の価格を「万円」単位に変換
                price_man = float(price) / 10000.0
                
                page_url = getattr(p, 'pageUrl', '')
                interior_score = 3.0
                layout_score = 3.0
                if page_url in eval_map:
                    interior_score, layout_score = eval_map[page_url]
                
                data_by_type[ptype].append({
                    "obj": p,
                    "price": price_man,
                    "company": company,
                    "interior_score": interior_score,
                    "layout_score": layout_score
                })
                
    print(f"Loaded Mansion: {len(data_by_type['mansion'])}, Kodate: {len(data_by_type['kodate'])}, Apartment: {len(data_by_type['apartment'])}")
    return data_by_type

def build_mkt_comparison_master(data_by_type):
    """
    ロードした全データからエリア別の「平均平米単価」マスタを作成
    """
    print("Building market comparison master...")
    mkt_master = {}
    
    all_units = []
    
    for ptype, items in data_by_type.items():
        for item in items:
            p = item["obj"]
            price = item["price"]
            
            address1 = getattr(p, 'address1', '') or ''
            address2 = getattr(p, 'address2', '') or ''
            
            chikunengetsu = getattr(p, 'chikunengetsu', None)
            if not chikunengetsu:
                chikunengetsu = getattr(p, 'chikunengetsuStr', None)
            chikunen = calculate_chikunen(chikunengetsu)
            
            senyu_menseki = getattr(p, 'senyuMenseki', 0.0)
            tatemono_menseki = getattr(p, 'tatemonoMenseki', 0.0)
            eval_area = float(senyu_menseki) if ptype == 'mansion' else float(tatemono_menseki)
            
            if eval_area > 0 and price > 0:
                age_band = int(chikunen // 10)
                unit_price = price / eval_area
                all_units.append({
                    "pref": address1,
                    "city": address2,
                    "ptype": ptype,
                    "age_band": age_band,
                    "unit_price": unit_price
                })
                
    df = pd.DataFrame(all_units)
    if not df.empty:
        gp = df.groupby(["pref", "city", "ptype", "age_band"])["unit_price"].mean().reset_index()
        for _, row in gp.iterrows():
            key = (row["pref"], row["city"], row["ptype"], int(row["age_band"]))
            mkt_master[key] = row["unit_price"]
            
    print(f"Created market comparison master with {len(mkt_master)} entries.")
    return mkt_master

def generate_dummy_data(ptype, num_records=500):
    """
    種別ごとのダミー学習データを生成
    """
    print(f"Generating dummy data for {ptype}...")
    np.random.seed(42)
    records = []
    
    for _ in range(num_records):
        area = np.random.uniform(25.0, 100.0) if ptype == 'mansion' else np.random.uniform(60.0, 150.0)
        tochi_area = 0.0 if ptype == 'mansion' else np.random.uniform(70.0, 200.0)
        chikunen = np.random.uniform(1.0, 45.0)
        walk_min = np.random.randint(1, 20)
        kanrihi = int(area * 200) if ptype == 'mansion' else 0
        syuzen = int(area * 150) if ptype == 'mansion' else 0
        pop_growth = np.random.uniform(-1.0, 2.0)
        income = np.random.randint(3000, 12000)
        passenger_volume = np.random.randint(5000, 700000)
        average_land_price = np.random.randint(150000, 3000000)
        interior_score = np.random.uniform(1.5, 4.8)
        layout_score = np.random.uniform(2.0, 4.8)
        
        # 最有効利用の計算
        digest_volume_ratio = 0.0
        surplus_volume_potential = 0.0
        non_conforming_flag = 0
        if ptype in ['kodate', 'apartment']:
            digest_volume_ratio = (area / tochi_area) * 100.0
            surplus_volume_potential = max(0.0, 200.0 - digest_volume_ratio)
            if digest_volume_ratio > 200.0:
                non_conforming_flag = 1
                
        # メタ特徴量算出
        cost_unit = 25.0 if ptype == 'mansion' else 15.0
        lifespan = 47 if ptype == 'mansion' else 22
        remaining_rate = max(0.1, (lifespan - chikunen) / lifespan)
        
        if ptype == 'mansion':
            cost_approach_value = (area * 0.2) * (average_land_price / 10000.0) + (area * cost_unit * remaining_rate)
        else:
            cost_approach_value = tochi_area * (average_land_price / 10000.0) + (area * cost_unit * remaining_rate)
            
        mkt_comparison_value = area * (average_land_price / 10000.0) * 0.95
        
        gross_yield = 0.0
        annual_rent = 0.0
        if ptype == 'apartment':
            gross_yield = np.random.uniform(4.5, 12.0)
            annual_rent = area * (average_land_price / 10000.0) * (gross_yield / 100.0)
            income_approach_value = annual_rent / (gross_yield / 100.0)
        else:
            rent = area * (average_land_price / 10000.0) * 0.05
            income_approach_value = rent / 0.06
            
        base_price = (area * (average_land_price / 10000.0)) - (chikunen * 40.0) - (walk_min * 50.0)
        area_multiplier = 1.0 + (income / 30000.0) + (passenger_volume / 5000000.0) + pop_growth * 0.05
        img_multiplier = 0.85 + (interior_score + layout_score) * 0.03
        
        if ptype == 'apartment':
            base_price = annual_rent * 10
            
        price = max(1000, int(base_price * area_multiplier * img_multiplier + np.random.normal(0, 300)))
        
        # 稀に異常値を混ぜる (クレンジング動作の検証用)
        if np.random.rand() < 0.02:
            price = 5  # 5万円 (異常に安い)
        elif np.random.rand() < 0.02:
            area = 1.0  # 1㎡ (異常に狭い)
        
        records.append({
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
            "digest_volume_ratio": digest_volume_ratio,
            "surplus_volume_potential": surplus_volume_potential,
            "non_conforming_flag": non_conforming_flag,
            "cost_approach_value": cost_approach_value,
            "mkt_comparison_value": mkt_comparison_value,
            "income_approach_value": income_approach_value,
            "gross_yield": gross_yield,
            "annual_rent": annual_rent,
            "interior_score": interior_score,
            "layout_score": layout_score,
            "is_shin_taishin": 1 if chikunen <= 45.0 else 0,
            "flood_risk_level": np.random.randint(0, 5),
            "landslide_risk_level": np.random.randint(0, 3),
            "max_youseki": 200.0 if ptype == 'mansion' else np.random.choice([100.0, 150.0, 200.0]),
            "max_kenpei": 60.0 if ptype == 'mansion' else np.random.choice([40.0, 50.0, 60.0]),
            "prefecture": "東京都",
            "city": "世田谷区",
            "station": "世田谷駅",
            "company": "mitsui",
            "kouzou": "木造" if ptype == 'kodate' else "RC"
        })
        
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

    # 2. IQR法による価格と面積の外れ値除外 (外れ値判定を2.5倍IQRとする)
    for col in ["price", "area"]:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 2.5 * iqr
        upper_bound = q3 + 2.5 * iqr
        
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
        X_outlier = df[features_for_outlier].fillna(0)
        
        preds = iso.fit_predict(X_outlier)
        pre_count = len(df)
        df = df[preds == 1].copy()
        post_count = len(df)
        if post_count < pre_count:
            print(f"  [IsolationForest] Removed {pre_count - post_count} multi-dimensional outlier records (contamination=2%).")
            
    print(f"Cleaned training data for {ptype}. Final records: {len(df)}")
    return df

def tune_hyperparameters(X, y, algo_name) -> dict:
    """
    簡易的なハイパーパラメータグリッドサーチを行い、
    3-Fold CV で最も MAPE が良かったパラメータの辞書を返します。
    """
    kf = KFold(n_splits=3, shuffle=True, random_state=42)
    best_params = {}
    best_mape = float('inf')
    
    if algo_name == "lgb":
        param_grid = [
            {"learning_rate": 0.05, "num_leaves": 31, "max_depth": 6, "min_child_samples": 20},
            {"learning_rate": 0.05, "num_leaves": 63, "max_depth": 8, "min_child_samples": 10},
            {"learning_rate": 0.1, "num_leaves": 31, "max_depth": 6, "min_child_samples": 20},
            {"learning_rate": 0.1, "num_leaves": 63, "max_depth": 8, "min_child_samples": 10}
        ]
        for params in param_grid:
            mapes = []
            for train_idx, val_idx in kf.split(X):
                X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
                
                model = lgb.LGBMRegressor(random_state=42, verbose=-1, n_jobs=1, n_estimators=100, **params)
                model.fit(X_train, y_train)
                preds = model.predict(X_val)
                mapes.append(calculate_mape(y_val, preds))
            
            avg_mape = np.mean(mapes)
            if avg_mape < best_mape:
                best_mape = avg_mape
                best_params = params
                
    elif algo_name == "xgb":
        param_grid = [
            {"learning_rate": 0.05, "max_depth": 5, "subsample": 0.8},
            {"learning_rate": 0.05, "max_depth": 7, "subsample": 0.9},
            {"learning_rate": 0.1, "max_depth": 5, "subsample": 0.8},
            {"learning_rate": 0.1, "max_depth": 7, "subsample": 0.9}
        ]
        for params in param_grid:
            mapes = []
            for train_idx, val_idx in kf.split(X):
                X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
                
                model = xgb.XGBRegressor(random_state=42, n_jobs=1, n_estimators=100, **params)
                model.fit(X_train, y_train)
                preds = model.predict(X_val)
                mapes.append(calculate_mape(y_val, preds))
                
            avg_mape = np.mean(mapes)
            if avg_mape < best_mape:
                best_mape = avg_mape
                best_params = params
                
    elif algo_name == "cat":
        param_grid = [
            {"learning_rate": 0.05, "depth": 6, "l2_leaf_reg": 3},
            {"learning_rate": 0.05, "depth": 8, "l2_leaf_reg": 5},
            {"learning_rate": 0.1, "depth": 6, "l2_leaf_reg": 3},
            {"learning_rate": 0.1, "depth": 8, "l2_leaf_reg": 5}
        ]
        for params in param_grid:
            mapes = []
            for train_idx, val_idx in kf.split(X):
                X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
                
                model = CatBoostRegressor(random_state=42, verbose=0, thread_count=1, iterations=200, **params)
                model.fit(X_train, y_train)
                preds = model.predict(X_val)
                mapes.append(calculate_mape(y_val, preds))
                
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
        else:
            return
            
        feat_imp = pd.Series(importances, index=feature_cols).sort_values(ascending=False)
        print(f"  [{algo_name}] Feature Importance (Top 10):")
        for name, val in feat_imp.head(10).items():
            print(f"    - {name}: {val:.4f}")
    except Exception as e:
        print(f"  [{algo_name}] Failed to compute feature importance: {e}")

def train_and_compare(df, feature_cols, stage_name) -> dict:
    """
    指定された特徴量を用いて3つのモデルをチューニング＆学習し、
    クロスバリデーション(5-Fold)評価を行った上で、全データで最終学習したモデルを返します。
    """
    X = df[feature_cols].copy()
    y = df["price"]
    
    # カテゴリカル変数の処理 (Label Encoding)
    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = X[col].astype('category').cat.codes
            
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    algos = ['lgb', 'xgb', 'cat']
    
    print(f"\n--- Tuning & Cross-Validating models for Stage: {stage_name} ---")
    
    trained_models = {}
    best_params_dict = {}
    
    # 事前チューニングの実行（データ数が多い場合のみ）
    for name in algos:
        if len(df) >= 30:
            print(f"Tuning hyperparameters for {name}...")
            best_params_dict[name] = tune_hyperparameters(X, y, name)
            print(f"Best params for {name}: {best_params_dict[name]}")
        else:
            best_params_dict[name] = {}
            
    for name in algos:
        mapes = []
        maes = []
        r2s = []
        params = best_params_dict[name]
        
        for train_idx, val_idx in kf.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            if name == "lgb":
                fold_model = lgb.LGBMRegressor(random_state=42, verbose=-1, n_jobs=1, n_estimators=100, **params)
            elif name == "xgb":
                fold_model = xgb.XGBRegressor(random_state=42, n_jobs=1, n_estimators=100, **params)
            elif name == "cat":
                fold_model = CatBoostRegressor(random_state=42, verbose=0, thread_count=1, iterations=200, **params)
            else:
                raise ValueError(f"Unknown algorithm: {name}")
                
            fold_model.fit(X_train, y_train)
            preds = fold_model.predict(X_val)
            
            mapes.append(calculate_mape(y_val, preds))
            maes.append(mean_absolute_error(y_val, preds))
            r2s.append(r2_score(y_val, preds))
            
            del fold_model, X_train, X_val, y_train, y_val
            gc.collect()
            
        avg_mape = np.mean(mapes)
        avg_mae = np.mean(maes)
        avg_r2 = np.mean(r2s)
        print(f"[{name}] 5-Fold CV Scores:")
        print(f"  - MAPE: {avg_mape:.2f}%")
        print(f"  - MAE:  {avg_mae:.2f}万円")
        print(f"  - R2:   {avg_r2:.4f}")
        
        # 全データで本番学習
        if name == "lgb":
            final_model = lgb.LGBMRegressor(random_state=42, verbose=-1, n_jobs=1, n_estimators=100, **params)
        elif name == "xgb":
            final_model = xgb.XGBRegressor(random_state=42, n_jobs=1, n_estimators=100, **params)
        elif name == "cat":
            final_model = CatBoostRegressor(random_state=42, verbose=0, thread_count=1, iterations=200, **params)
        else:
            raise ValueError(f"Unknown algorithm: {name}")
            
        final_model.fit(X, y)
        print_feature_importance(final_model, name, feature_cols)
        trained_models[name] = final_model
        
    return trained_models

def main():
    data_by_type = load_all_properties_from_db()
    
    # 統計マスタの構築
    mkt_master = build_mkt_comparison_master(data_by_type)
    
    # 保存ディレクトリの設定 (相対パス解決)
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    os.makedirs(model_dir, exist_ok=True)
    
    # マスタの保存
    joblib.dump(mkt_master, os.path.join(model_dir, "mkt_comparison_master.joblib"))
    
    # 物件種別ごとの特徴量セット定義
    feature_sets = {
        "mansion": {
            "first": [
                "area", "chikunen", "walk_min", "kanrihi", "syuzen",
                "pop_growth", "income", "passenger_volume", "average_land_price",
                "estimated_rosenka_price", "estimated_fixed_asset_price",
                "cost_approach_value", "mkt_comparison_value", "income_approach_value",
                "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
                "max_youseki", "max_kenpei"
            ],
            "second": [
                "area", "chikunen", "walk_min", "kanrihi", "syuzen",
                "pop_growth", "income", "passenger_volume", "average_land_price",
                "estimated_rosenka_price", "estimated_fixed_asset_price",
                "cost_approach_value", "mkt_comparison_value", "income_approach_value",
                "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
                "max_youseki", "max_kenpei", "interior_score", "layout_score"
            ]
        },
        "kodate": {
            "first": [
                "area", "tochi_menseki", "chikunen", "walk_min",
                "pop_growth", "income", "passenger_volume", "average_land_price",
                "estimated_rosenka_price", "estimated_fixed_asset_price",
                "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
                "cost_approach_value", "mkt_comparison_value", "income_approach_value",
                "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
                "max_youseki", "max_kenpei"
            ],
            "second": [
                "area", "tochi_menseki", "chikunen", "walk_min",
                "pop_growth", "income", "passenger_volume", "average_land_price",
                "estimated_rosenka_price", "estimated_fixed_asset_price",
                "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
                "cost_approach_value", "mkt_comparison_value", "income_approach_value",
                "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
                "max_youseki", "max_kenpei", "interior_score", "layout_score"
            ]
        },
        "apartment": {
            "first": [
                "area", "tochi_menseki", "chikunen", "walk_min",
                "pop_growth", "income", "passenger_volume", "average_land_price",
                "estimated_rosenka_price", "estimated_fixed_asset_price",
                "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
                "gross_yield", "annual_rent",
                "cost_approach_value", "mkt_comparison_value", "income_approach_value",
                "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
                "max_youseki", "max_kenpei"
            ],
            "second": [
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
    }
    
    # 各物件種別の学習を実行
    ptypes = list(data_by_type.keys())
    for ptype in ptypes:
        items = data_by_type[ptype]
        print(f"\n=========================================")
        print(f"Training models for Property Type: {ptype}")
        print(f"=========================================")
        
        # DBデータをもとに特徴量データフレームを作成
        records = []
        for item in items:
            p = item["obj"]
            feats = build_features(p, ptype, mkt_comparison_master=mkt_master)
            feats["price"] = item["price"]
            feats["interior_score"] = item["interior_score"]
            feats["layout_score"] = item["layout_score"]
            records.append(feats)
            
        df = pd.DataFrame(records)
        
        # 件数が少ない場合はダミーデータを適用
        if len(df) < 10:
            print(f"Not enough real data for {ptype} in DB. Generating dummy data.")
            df = generate_dummy_data(ptype)
            
        # 学習データのクレンジング（外れ値の自動除外）を実行
        df = clean_training_data(df, ptype)
            
        # 一次モデルの訓練と保存 (LGB, XGB, Cat)
        first_cols = feature_sets[ptype]["first"]
        first_models = train_and_compare(df, first_cols, f"{ptype} - First Stage (No Image)")
        for algo, model in first_models.items():
            joblib.dump(model, os.path.join(model_dir, f"{ptype}_first_stage_{algo}.joblib"))
        
        # 二次モデルの訓練と保存 (LGB, XGB, Cat)
        second_cols = feature_sets[ptype]["second"]
        second_models = train_and_compare(df, second_cols, f"{ptype} - Second Stage (With Image)")
        for algo, model in second_models.items():
            joblib.dump(model, os.path.join(model_dir, f"{ptype}_second_stage_{algo}.joblib"))
            
        # メモリ解放
        data_by_type[ptype] = []
        del items, df, records, first_models, second_models
        gc.collect()
        
    print("\nMachine learning training pipeline completed successfully for all property types with ensemble support!")

if __name__ == "__main__":
    main()

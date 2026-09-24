# -*- coding: utf-8 -*-
"""
マクロ時系列トレンド予測モジュール (Macro Time Series Forecaster)

不動産価格指数 (REPI)、10年国債利回り、日経平均、REIT指数、建設物価指数の
時系列データを正則化自己回帰 (Ridge VAR) およびモメンタム解析によりモデル化し、
相場トレンド予測およびモメンタム特徴量を生成します。
"""
import logging
import datetime
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

logger = logging.getLogger(__name__)

MACRO_COLUMNS = [
    "repi_mansion",
    "repi_kodate",
    "repi_tochi",
    "jgb_10y_yield",
    "nikkei_225",
    "tse_reit_index",
    "construction_cost_index"
]


class MacroTrendForecaster:
    """
    正則化自己回帰 (Ridge Vector Autoregression) によるマクロ時系列トレンド予測モデル
    """

    def __init__(self, lags: int = 3, alpha: float = 1.0):
        self.lags = lags
        self.alpha = alpha
        self.models = {}  # 各マクロ変数ごとの Ridge モデル
        self.df_history = None
        self.is_fitted = False
        self._feature_cache = {}

    def fit_from_db(self):
        """DB上の MacroEconomicIndex から全件ロードして学習"""
        try:
            from package.models.evaluation import MacroEconomicIndex
            records = list(MacroEconomicIndex.objects.order_by("year_month").values(
                "year_month", *MACRO_COLUMNS
            ))
            if not records:
                logger.warning("No MacroEconomicIndex records in DB to fit forecaster.")
                return self

            df = pd.DataFrame(records)
            return self.fit(df)
        except Exception as e:
            logger.exception(f"Failed to fit MacroTrendForecaster from DB: {e}")
            return self

    def fit(self, df: pd.DataFrame):
        """
        時系列 DataFrame を用いて自己回帰係数を推定
        df: columns に 'year_month' と MACRO_COLUMNS を含む DataFrame
        """
        df = df.sort_values(by="year_month").copy().reset_index(drop=True)
        self.df_history = df.set_index("year_month")[MACRO_COLUMNS].astype(float)

        n_samples = len(self.df_history)
        if n_samples <= self.lags:
            logger.warning(f"Insufficient history ({n_samples}) for lags={self.lags}.")
            self.is_fitted = False
            return self

        # ラグ特徴量行列の構築
        X, Y = [], {col: [] for col in MACRO_COLUMNS}
        for t in range(self.lags, n_samples):
            lag_values = []
            for lag in range(1, self.lags + 1):
                lag_values.extend(self.df_history.iloc[t - lag].values)
            X.append(lag_values)
            for col in MACRO_COLUMNS:
                Y[col].append(self.df_history.iloc[t][col])

        X = np.array(X)
        for col in MACRO_COLUMNS:
            y = np.array(Y[col])
            ridge = Ridge(alpha=self.alpha)
            ridge.fit(X, y)
            self.models[col] = ridge

        self.is_fitted = True
        self._feature_cache.clear()
        logger.info(f"MacroTrendForecaster fitted on {n_samples} historical months.")
        return self

    def predict_future(self, steps: int = 6) -> pd.DataFrame:
        """
        最新月を起点に、将来 steps ヶ月先までのマクロ指標を逐次予測
        """
        if not self.is_fitted or self.df_history is None:
            return pd.DataFrame(columns=["year_month"] + MACRO_COLUMNS)

        last_ym = self.df_history.index[-1]
        last_date = datetime.datetime.strptime(last_ym + "-01", "%Y-%m-%d").date()

        current_window = [self.df_history.iloc[-lag].values for lag in range(self.lags, 0, -1)]

        predictions = []
        for step in range(1, steps + 1):
            # 次月の日付算出
            next_month = (last_date.month + step - 1) % 12 + 1
            next_year = last_date.year + (last_date.month + step - 1) // 12
            next_ym = f"{next_year:04d}-{next_month:02d}"

            # ラグベクトルの平坦化 (lag1, lag2, ..., lagP の順)
            flat_lag = []
            for lag_idx in range(self.lags, 0, -1):
                flat_lag.extend(current_window[-lag_idx])

            pred_row = {"year_month": next_ym}
            new_pred_values = []
            for col in MACRO_COLUMNS:
                pred_val = float(self.models[col].predict([flat_lag])[0])
                # 理論的下限ガード
                if "repi" in col or "nikkei" in col or "reit" in col or "cost" in col:
                    pred_val = max(10.0, pred_val)
                pred_row[col] = round(pred_val, 2)
                new_pred_values.append(pred_val)

            predictions.append(pred_row)
            # ウィンドウの更新
            current_window.append(np.array(new_pred_values))

        return pd.DataFrame(predictions)

    def get_features_for_month(self, year_month: str, ptype: str = "mansion") -> dict:
        """
        指定年月のマクロモメンタムおよびトレンド特徴量を返却
        """
        cache_key = (year_month, ptype)
        if cache_key in self._feature_cache:
            return self._feature_cache[cache_key]

        defaults = {
            "repi_growth_3m": 0.0,
            "repi_growth_6m": 0.0,
            "jgb_diff_3m": 0.0,
            "reit_growth_3m": 0.0,
            "const_growth_6m": 0.0,
            "macro_regime_score": 0.0
        }

        if not self.is_fitted or self.df_history is None or year_month not in self.df_history.index:
            return defaults

        # 対象物件種別に応じた REPI カラム
        repi_col = "repi_mansion"
        if ptype == "kodate":
            repi_col = "repi_kodate"
        elif ptype == "tochi":
            repi_col = "repi_tochi"

        idx = self.df_history.index.get_loc(year_month)

        def _growth(col, lag):
            if idx >= lag:
                prev = self.df_history.iloc[idx - lag][col]
                curr = self.df_history.iloc[idx][col]
                return float((curr - prev) / prev * 100.0) if prev > 0 else 0.0
            return 0.0

        def _diff(col, lag):
            if idx >= lag:
                prev = self.df_history.iloc[idx - lag][col]
                curr = self.df_history.iloc[idx][col]
                return float(curr - prev)
            return 0.0

        repi_3m = _growth(repi_col, 3)
        repi_6m = _growth(repi_col, 6)
        jgb_diff = _diff("jgb_10y_yield", 3)
        reit_3m = _growth("tse_reit_index", 3)
        const_6m = _growth("construction_cost_index", 6)

        # レジームスコア: 価格上昇(+), REIT上昇(+), 金利上昇(-) の合成 (シグモイド正規化: -1.0 ~ +1.0)
        raw_regime = (repi_3m * 0.4) + (reit_3m * 0.3) - (jgb_diff * 1.5)
        regime_score = float(np.clip(raw_regime / 10.0, -1.0, 1.0))

        feats = {
            "repi_growth_3m": round(repi_3m, 2),
            "repi_growth_6m": round(repi_6m, 2),
            "jgb_diff_3m": round(jgb_diff, 2),
            "reit_growth_3m": round(reit_3m, 2),
            "const_growth_6m": round(const_6m, 2),
            "macro_regime_score": round(regime_score, 3)
        }
        self._feature_cache[cache_key] = feats
        return feats


# シングルトンインスタンス
_global_forecaster = None

def get_global_macro_forecaster() -> MacroTrendForecaster:
    global _global_forecaster
    if _global_forecaster is None:
        _global_forecaster = MacroTrendForecaster(lags=3, alpha=1.0)
        _global_forecaster.fit_from_db()
    return _global_forecaster

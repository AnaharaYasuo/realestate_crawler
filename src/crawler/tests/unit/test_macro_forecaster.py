# -*- coding: utf-8 -*-
import pytest
import pandas as pd
import numpy as np

from package.ml.macro_forecaster import MacroTrendForecaster


@pytest.fixture
def sample_macro_df():
    """過去36ヶ月分のダミーマクロ経済データ"""
    dates = pd.date_range(start="2023-01-01", periods=36, freq="MS")
    records = []
    base_repi = 150.0
    base_jgb = 0.5
    for i, dt in enumerate(dates):
        ym = dt.strftime("%Y-%m")
        # 緩やかな上昇トレンド
        repi_m = base_repi + i * 1.2 + np.sin(i / 2.0)
        repi_k = base_repi + i * 0.8
        repi_t = base_repi + i * 0.5
        jgb = base_jgb + i * 0.02
        nikkei = 30000.0 + i * 300.0
        reit = 1800.0 + np.cos(i) * 50.0
        const = 110.0 + i * 0.3
        records.append({
            "year_month": ym,
            "repi_mansion": repi_m,
            "repi_kodate": repi_k,
            "repi_tochi": repi_t,
            "jgb_10y_yield": jgb,
            "nikkei_225": nikkei,
            "tse_reit_index": reit,
            "construction_cost_index": const
        })
    return pd.DataFrame(records)


class TestMacroTrendForecaster:
    """マクロ時系列予測モデルのテスト"""

    def test_fit_and_predict_future(self, sample_macro_df):
        forecaster = MacroTrendForecaster(lags=3, alpha=1.0)
        forecaster.fit(sample_macro_df)

        assert forecaster.is_fitted is True

        future_preds = forecaster.predict_future(steps=6)
        assert len(future_preds) == 6
        assert "year_month" in future_preds.columns
        assert "repi_mansion" in future_preds.columns
        assert "jgb_10y_yield" in future_preds.columns

        # 将来予測値が NaN でないこと、妥当な正の範囲内であること
        assert not future_preds["repi_mansion"].isna().any()
        assert (future_preds["repi_mansion"] > 100.0).all()

    def test_get_features_for_month(self, sample_macro_df):
        forecaster = MacroTrendForecaster(lags=3)
        forecaster.fit(sample_macro_df)

        target_ym = "2025-06"
        feats = forecaster.get_features_for_month(target_ym, ptype="mansion")

        assert isinstance(feats, dict)
        assert "repi_growth_3m" in feats
        assert "repi_growth_6m" in feats
        assert "jgb_diff_3m" in feats
        assert "macro_regime_score" in feats

        # 3ヶ月成長率が float 型で計算されていること
        assert isinstance(feats["repi_growth_3m"], float)
        assert -1.0 <= feats["macro_regime_score"] <= 1.0

    def test_fallback_on_unfitted_or_missing(self):
        """未学習状態または存在しない年月での安全なフォールバック"""
        forecaster = MacroTrendForecaster()
        feats = forecaster.get_features_for_month("2099-12", ptype="kodate")

        assert isinstance(feats, dict)
        assert feats["repi_growth_3m"] == 0.0
        assert feats["jgb_diff_3m"] == 0.0
        assert feats["macro_regime_score"] == 0.0

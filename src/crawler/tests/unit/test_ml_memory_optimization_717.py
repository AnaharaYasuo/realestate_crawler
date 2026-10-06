# -*- coding: utf-8 -*-
"""
Issue #717 参照マスタ軽量化・推論メモリ削減の単体テスト
"""

from unittest.mock import MagicMock, patch

from django.db import models
import numpy as np
import pandas as pd

from package.ml.features.reference_data import (
    _hazard_cache,
    _init_global_caches,
    _lp_cache,
    _macro_cache,
    _muni_cache,
    _station_cache,
    _zone_cache,
    reset_reference_caches,
)
from package.ml.inference.ensemble import align_features
from package.ml.inference.predictor import (
    predict_both_stages,
    prepare_df_features,
)


def test_reference_master_cache_not_django_models():
    """参照マスタキャッシュに Django モデルインスタンスが保持されていないこと（受入基準 1）"""
    reset_reference_caches()
    with patch("package.models.evaluation.MunicipalPotential.objects.values") as mock_muni, \
         patch("package.models.evaluation.LandPricePotential.objects.values") as mock_lp, \
         patch("package.models.evaluation.StationPotential.objects.values") as mock_st, \
         patch("package.models.evaluation.HazardMapPotential.objects.values") as mock_hz, \
         patch("package.models.evaluation.UrbanPlanningZonePotential.objects.values") as mock_zn, \
         patch("package.models.evaluation.MacroEconomicIndex.objects.values") as mock_mc:

        mock_muni.return_value = [{
            "prefecture": "東京都", "city": "千代田区", "population_growth_rate": "1.5",
            "average_income": 8000, "total_population": 65000, "income_growth_rate": "0.5",
            "population_density": "5000.0",
        }]
        mock_lp.return_value = [{
            "prefecture": "東京都", "city": "千代田区", "average_land_price": 2000000,
            "estimated_rosenka_price": 1600000, "estimated_fixed_asset_price": 1400000,
            "land_price_growth_rate": "3.2", "land_use": "residential",
        }]
        mock_st.return_value = [{"station_name": "東京", "passenger_volume": 450000}]
        mock_hz.return_value = [{"prefecture": "東京都", "city": "千代田区", "flood_risk_level": 1, "landslide_risk_level": 0}]
        mock_zn.return_value = [{"zone_name": "商業地域", "max_kenpei": 80, "max_youseki": 500}]
        mock_mc.return_value = [{
            "year_month": "2026-10", "repi_mansion": 120.0, "repi_kodate": 110.0,
            "repi_tochi": 105.0, "jgb_10y_yield": 0.8, "nikkei_225": 38000.0,
            "tse_reit_index": 1950.0, "construction_cost_index": 125.0,
        }]

        _init_global_caches(force_refresh=True)

        for cache_dict in (_muni_cache, _station_cache, _lp_cache, _hazard_cache, _zone_cache, _macro_cache):
            for key, rec in cache_dict.items():
                assert not isinstance(rec, models.Model), f"Record {key} must not be a Django Model"
                assert hasattr(rec, "__slots__"), f"Record {key} must have __slots__"


def test_align_features_no_copy_and_correct_reindex():
    """推論の特徴量整列で DataFrame の copy() が行われないこと（受入基準 3）"""
    df = pd.DataFrame({"col_a": [1.0, 2.0], "col_b": [3.0, 4.0]})
    mock_model = MagicMock()
    mock_model.feature_names_in_ = ["col_b", "col_a", "col_c"]

    with patch.object(df, "copy") as mock_copy:
        aligned = align_features(df, mock_model)
        mock_copy.assert_not_called()
        assert list(aligned.columns) == ["col_b", "col_a", "col_c"]
        assert aligned["col_c"].iloc[0] == 0.0


def test_prepare_df_features_float32():
    """prepare_df_features が float64 を float32 へキャストしてメモリ削減すること"""
    data = [{"feature1": 100.5, "feature2": 200, "text_col": "123"}]
    cols = ["feature1", "feature2", "feature3"]
    df = prepare_df_features(data, cols)

    assert df["feature1"].dtype == np.float32
    assert df["feature3"].dtype == np.float32 or df["feature3"].iloc[0] == 0.0


def test_predict_both_stages_single_build_features_batch():
    """一次・二次を両方算出する経路で build_features_batch の呼び出しが 1 回であること（受入基準 4）"""
    props = [{"address": "東京都千代田区", "menseki": 50.0, "propertyType": "mansion"}]
    with patch("package.ml.inference.predictor.build_features_batch") as mock_build, \
         patch("package.ml.inference.predictor.predict_batch_ensemble") as mock_ensemble:

        mock_build.return_value = [{"area": 50.0}]
        mock_ensemble.return_value = np.array([5000.0])

        mock_reg = MagicMock()
        mock_reg.models.side_effect = lambda ptype, stage: {"rf": MagicMock()} if stage in ("first", "second") else {}
        mock_reg.market_master.return_value = {}
        mock_reg.weights.return_value = {"rf": 1.0}
        mock_reg.smearing.return_value = 1.0

        results = predict_both_stages(props, [4.0], [4.0], registry=mock_reg)

        assert mock_build.call_count == 1
        assert len(results) == 1
        assert results[0] == (5000, 5000)

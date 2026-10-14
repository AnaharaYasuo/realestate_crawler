# -*- coding: utf-8 -*-
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

from package.ml.features import FEATURE_SETS, build_features
from package.ml.predict import (
    bulk_predict_first_stage,
    predict_first_stage_local,
    _apply_smearing_and_ensemble
)

def test_feature_sets_consistency():
    """全4種別のfirst/second特徴量セット定義の完全性と整合性を検証"""
    expected_types = ["mansion", "kodate", "apartment", "tochi"]
    for ptype in expected_types:
        assert ptype in FEATURE_SETS, f"Missing {ptype} in FEATURE_SETS"
        assert "first" in FEATURE_SETS[ptype], f"Missing 'first' in {ptype}"
        assert "second" in FEATURE_SETS[ptype], f"Missing 'second' in {ptype}"
        
        first_cols = FEATURE_SETS[ptype]["first"]
        second_cols = FEATURE_SETS[ptype]["second"]
        
        assert len(first_cols) > 0
        assert len(second_cols) >= len(first_cols)
        
        # secondはfirstの全特徴量を包含し、かつ画像スコアを含むこと
        for col in first_cols:
            assert col in second_cols, f"{col} in first but not in second for {ptype}"
        assert "interior_score" in second_cols
        assert "layout_score" in second_cols

def test_build_features_contains_all_feature_set_cols():
    """build_featuresが各物件種別のFEATURE_SETSで必要な列を漏れなく出力することを検証"""
    dummy_mansion = {
        "propertyName": "テストマンション",
        "price": 50000000,
        "address1": "東京都",
        "address2": "世田谷区",
        "station1": "経堂駅",
        "senyuMenseki": 70.0,
        "chikunengetsuStr": "2018-05-01",
        "railwayWalkMinute1": 5,
        "kouzou": "RC",
        "kanrihi": 12000,
        "syuzenTsumitate": 15000,
        "propertyType": "mansion"
    }
    feats = build_features(dummy_mansion, "mansion")
    for col in FEATURE_SETS["mansion"]["first"]:
        assert col in feats, f"Feature column '{col}' missing from build_features output for mansion"

def test_apply_smearing_and_ensemble():
    """スミアリング補正および重み付きアンサンブル集計の計算整合性を検証"""
    # 2サンプルの対数予測モック
    preds_log_dict = {
        "lgb": np.array([np.log(100.0), np.log(200.0)]),
        "xgb": np.array([np.log(105.0), np.log(195.0)]),
        "cat": np.array([np.log(98.0), np.log(202.0)]),
        "rf":  np.array([np.log(102.0), np.log(198.0)])
    }
    weights = {"lgb": 0.4, "xgb": 0.3, "cat": 0.2, "rf": 0.1}
    smearing_factor = 1.02
    areas = np.array([50.0, 70.0])
    
    final_preds = _apply_smearing_and_ensemble(preds_log_dict, weights, smearing_factor, areas)
    
    assert len(final_preds) == 2
    assert final_preds[0] > 0
    assert final_preds[1] > 0
    # 面積50㎡ * 単価約100万円/㎡ * スミアリング1.02 ≒ 5100万円規模
    assert 4800 <= final_preds[0] <= 5500
    # 面積70㎡ * 単価約200万円/㎡ * スミアリング1.02 ≒ 14280万円規模
    assert 13500 <= final_preds[1] <= 15000

def test_bulk_predict_first_stage_empty():
    """空リスト入力時に空リストを即座に安全に返すこと"""
    res = bulk_predict_first_stage([])
    assert res == []

def test_bulk_predict_first_stage_with_mock_models():
    """モックモデルを用いてbulk_predict_first_stageのベクトル化推論が正常に件数一致で返ることを検証"""
    dummy_properties = [
        {
            "propertyName": f"テスト物件{i}",
            "price": 40000000 + i * 1000000,
            "address1": "東京都",
            "address2": "世田谷区",
            "station1": "経堂駅",
            "senyuMenseki": 60.0 + i * 5,
            "chikunengetsuStr": "2015-01-01",
            "railwayWalkMinute1": 6,
            "kouzou": "RC",
            "propertyType": "mansion"
        }
        for i in range(5)
    ]
    
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([np.log(80.0)] * 5)
    mock_model.feature_names_in_ = FEATURE_SETS["mansion"]["first"]
    
    with patch("package.ml.predict._get_models_and_master") as mock_get_models:
        mock_get_models.return_value = (
            {"lgb": mock_model},
            {},
            {}
        )
        preds = bulk_predict_first_stage(dummy_properties)
        
        assert len(preds) == 5
        for p in preds:
            assert isinstance(p, int)
            assert p > 0

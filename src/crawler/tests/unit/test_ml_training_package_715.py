"""
Phase 4 (#715) 分割パッケージ package.ml.training のユニットテスト。
sample_weights, market_master, regressors, tuning, artifacts, data_loader, pipeline 総合検証。
"""

import datetime
import os
import tempfile
import numpy as np
import pandas as pd

from package.ml.training.sample_weights import calculate_time_decay_weights
from package.ml.training.metrics import calculate_mape
from package.ml.training.regressors import get_regressor, PARAM_GRIDS
from package.ml.training.tuning import tune_hyperparameters
from package.ml.training.artifacts import save_metadata, upload_models_to_storage
from package.ml.training.market_master import (
    extract_unit_price_record,
    build_mkt_comparison_master,
)


def test_calculate_time_decay_weights_vectorized():
    base = datetime.date(2025, 1, 1)
    dates = [
        datetime.date(2025, 1, 1),        # 0 days
        datetime.date(2024, 1, 1),        # ~366 days
        "2023-01-01",                     # ~731 days
        None,                             # NaN
        "invalid-date",                   # NaN
    ]
    weights = calculate_time_decay_weights(dates, base_date=base, decay_rate=0.0005, min_weight=0.20)
    assert len(weights) == 5
    assert np.isclose(weights[0], 1.0)
    assert 0.20 <= weights[1] < 1.0
    assert 0.20 <= weights[2] < weights[1]
    assert np.isclose(weights[3], 0.20)
    assert np.isclose(weights[4], 0.20)


def test_calculate_mape():
    y_true = np.array([100.0, 200.0, 300.0])
    y_pred = np.array([110.0, 190.0, 300.0])
    mape = calculate_mape(y_true, y_pred)
    expected = np.mean([10.0 / 100.0, 10.0 / 200.0, 0.0]) * 100.0
    assert np.isclose(mape, expected)


def test_regressors_and_tuning():
    for algo in ["lgb", "rf"]:
        model = get_regressor(algo)
        assert model is not None
        assert algo in PARAM_GRIDS

    # 非定数ターゲットデータでのチューニング動作確認
    np.random.seed(42)
    areas = np.random.uniform(20, 100, size=30)
    chikunens = np.random.uniform(0, 30, size=30)
    # 面積と築年数に依存する非定数価格
    prices = areas * 80.0 - chikunens * 20.0 + np.random.normal(0, 5, size=30)
    X = pd.DataFrame({"area": areas, "chikunen": chikunens})
    y = pd.Series(np.log1p(np.maximum(10.0, prices)))

    best_params = tune_hyperparameters(X, y, "rf")
    assert isinstance(best_params, dict)
    assert len(best_params) > 0
    # チューニングされたパラメータ辞書が PARAM_GRIDS['rf'] の候補辞書のいずれかと一致することを検証
    assert best_params in PARAM_GRIDS["rf"]


def test_market_master_helpers():
    class DummyObj:
        address1 = "東京都"
        address2 = "渋谷区"
        line = "山手線"
        station = "渋谷"
        toho = 5
        senyuMenseki = 50.0
        chikunengetsu = "2015-01"

    obj = DummyObj()
    rec = extract_unit_price_record(obj, 5000.0, "mansion")
    assert rec is not None
    assert rec["unit_price"] == 100.0  # 5000 / 50
    assert rec["ptype"] == "mansion"

    mkt = build_mkt_comparison_master({
        "mansion": [{"obj": obj, "price": 5000.0}],
    })
    assert len(mkt) > 0
    # 年数に応じた age_band
    found = any(k[0] == "東京都" and k[1] == "渋谷区" and k[2] == "mansion" for k in mkt)
    assert found


def test_artifacts_saving_and_roundtrip():
    import joblib

    with tempfile.TemporaryDirectory() as tmpdir:
        expected_weights = {"mansion": {"lgb": 0.5, "rf": 0.5}}
        expected_smearing = {"mansion": 1.05}
        expected_mkt = {("東京都", "渋谷区", "mansion", 1): 100.0}

        save_metadata(
            model_dir=tmpdir,
            all_ensemble_weights=expected_weights,
            all_smearing_factors=expected_smearing,
            mkt_master=expected_mkt,
        )
        weights_path = os.path.join(tmpdir, "ensemble_weights.joblib")
        smearing_path = os.path.join(tmpdir, "smearing_factors.joblib")
        mkt_path = os.path.join(tmpdir, "mkt_comparison_master.joblib")

        assert os.path.exists(weights_path)
        assert os.path.exists(smearing_path)
        assert os.path.exists(mkt_path)

        # 内容のラウンドトリップ検証
        assert joblib.load(weights_path) == expected_weights
        assert joblib.load(smearing_path) == expected_smearing
        assert joblib.load(mkt_path) == expected_mkt

        # upload_models_to_storage: GCS 未設定時は 0 件
        count = upload_models_to_storage(tmpdir)
        assert count == 0


def test_train_property_type_rejects_fallback_in_prod(monkeypatch):
    from package.ml.constants import PROPERTY_TYPES
    from package.ml.features import FEATURE_SETS
    from package.ml.training.pipeline import train_property_type
    import pytest

    monkeypatch.delenv("ALLOW_DUMMY_DATA", raising=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(RuntimeError, match="Dummy data generation is disallowed"):
            train_property_type(
                ptype=PROPERTY_TYPES[0],
                features_iterator=iter([]),
                feature_sets=FEATURE_SETS,
                model_dir=tmpdir,
                all_ensemble_weights={},
                all_smearing_factors={},
                allow_dummy_fallback=False,
            )

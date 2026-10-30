"""Unit tests for Phase 6: ML Price Prediction & Risk-Adjusted Bargain Score Upgrade (Issue #1151)."""
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, KFold

import setup_env  # noqa: F401
from package.ml.inference.ensemble import (
    compute_prediction_interval_p10,
    compute_risk_adjusted_bargain_score,
)
from package.ml.training.ensemble import (
    compute_oof_chome_encoding,
    compute_smearing_factor,
    get_cv_strategy,
    optimize_ensemble_weights,
)
from package.ml.training.pipeline import DEFAULT_MAX_TRAINING_ITEMS


class TestPhase6MlValuationUpgrade:
    def test_training_cap_raised_to_50000(self):
        """Training pipeline default max_items cap must be raised from 15000 to 50000."""
        assert DEFAULT_MAX_TRAINING_ITEMS == 50000

    def test_get_cv_strategy_uses_group_kfold_for_building_groups(self):
        """When multiple units belong to the same condo building/address, GroupKFold is selected to prevent leakage."""
        df = pd.DataFrame({
            "building_group": ["bldg_A", "bldg_A", "bldg_B", "bldg_B", "bldg_C", "bldg_C"],
            "price": [5000, 5100, 6000, 6200, 7000, 7100],
            "area": [60.0, 62.0, 70.0, 72.0, 80.0, 82.0],
        })
        cv, desc = get_cv_strategy(df)
        assert isinstance(cv, GroupKFold)
        assert "GroupKFold" in desc

        # Backward compatibility with integer length
        cv_int, _ = get_cv_strategy(20)
        assert isinstance(cv_int, KFold)

    def test_compute_oof_chome_encoding_prevents_target_leakage(self):
        """Out-of-fold Chome target encoding computes smoothed encodings strictly from training folds."""
        df = pd.DataFrame({
            "chome_group": ["港区赤坂1", "港区赤坂1", "港区赤坂1", "世田谷区玉川1", "世田谷区玉川1", "世田谷区玉川1"],
            "building_group": ["b1", "b2", "b3", "b4", "b5", "b6"],
            "price": [12000, 12500, 11800, 6000, 6200, 5800],
            "area": [60.0, 60.0, 60.0, 60.0, 60.0, 60.0],
        })
        y = pd.Series(np.log1p(df["price"] / df["area"]))
        cv = KFold(n_splits=3, shuffle=True, random_state=42)
        encoded = compute_oof_chome_encoding(df, y, cv, smoothing=2.0)
        assert len(encoded) == 6
        assert np.all(np.isfinite(encoded))
        # High-price Chome should have higher OOF encoding than lower-price Chome
        assert float(np.mean(encoded[:3])) > float(np.mean(encoded[3:]))

    def test_sample_weighted_ensemble_weights_and_smearing(self):
        """optimize_ensemble_weights and compute_smearing_factor honor sample_weight."""
        df = pd.DataFrame({
            "price": [5000.0, 6000.0, 7000.0, 8000.0],
            "area": [50.0, 60.0, 70.0, 80.0],
        })
        # Unit price is 100.0 across all 4 rows.
        # lgb is accurate on rows 2, 3 (recent, high weight) and inaccurate on rows 0, 1.
        oof_preds = {
            "lgb": np.log1p(np.array([140.0, 140.0, 100.0, 100.0])),
            "xgb": np.log1p(np.array([100.0, 100.0, 140.0, 140.0])),
        }
        oof_counts = {
            "lgb": np.ones(4),
            "xgb": np.ones(4),
        }
        sample_weights = np.array([0.1, 0.1, 5.0, 5.0])
        opt_weights, opt_w, oof_unit_preds = optimize_ensemble_weights(
            df, oof_preds, oof_counts, ["lgb", "xgb"], sample_weight=sample_weights
        )
        assert opt_weights["lgb"] > opt_weights["xgb"]

        smearing = compute_smearing_factor(df, oof_unit_preds, opt_w, sample_weight=sample_weights)
        assert 0.90 <= smearing <= 1.40

    def test_p10_prediction_interval_and_risk_adjusted_bargain_score(self):
        """High inter-model disagreement lowers P10 conservative bound and suppresses false-positive bargains."""
        areas = np.array([60.0, 60.0])
        weights = {"lgb": 0.5, "xgb": 0.5}
        # Property 0: tight agreement around 100万円/㎡ (~6000万円)
        # Property 1: huge disagreement (50 vs 150万円/㎡) -> high uncertainty -> lower P10
        preds_log_dict = {
            "lgb": np.array([np.log1p(100.0), np.log1p(50.0)]),
            "xgb": np.array([np.log1p(100.0), np.log1p(150.0)]),
        }
        point_preds, p10_preds = compute_prediction_interval_p10(
            preds_log_dict, weights, smearing_factor=1.0, areas=areas
        )
        assert np.all(p10_preds < point_preds)
        assert p10_preds[0] > p10_preds[1]

        # Actual listing price = 4800万円 for both properties
        # Property 0 has a high P10 (~5600万円), so it is a true risk-adjusted bargain.
        # Property 1 has a low P10 due to high model disagreement, so its bargain score is much lower or 0.
        scores = compute_risk_adjusted_bargain_score(
            actual_price=np.array([4800.0, 4800.0]),
            predicted_price=point_preds,
            p10_price=p10_preds,
        )
        assert scores[0] > scores[1]
        assert scores[0] > 0.10

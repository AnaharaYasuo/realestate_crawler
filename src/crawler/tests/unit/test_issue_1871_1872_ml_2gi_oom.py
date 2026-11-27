"""Unit tests for Issues #1871 & #1872: 2GiB RAM OOM prevention in ML training and bulk evaluation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_training_memory_caps_for_2gi_ram():
    """Verify Issue #1871: training item cap and RandomForest grid are sized for 2GiB RAM."""
    from package.ml.training.pipeline import DEFAULT_MAX_TRAINING_ITEMS
    from package.ml.training.regressors import PARAM_GRIDS

    assert DEFAULT_MAX_TRAINING_ITEMS <= 25000
    rf_grid = PARAM_GRIDS["rf"][0]
    assert rf_grid["n_estimators"] <= 60
    assert rf_grid["max_depth"] <= 12
    assert rf_grid["min_samples_leaf"] >= 8


def test_first_stage_provider_does_not_load_second_stage_models():
    """Verify Issue #1872: first-stage bulk prediction only loads first_stage models."""
    from package.ml import predict

    mock_reg = MagicMock()
    mock_reg.models.return_value = {"lgb": object()}
    mock_reg.market_master.return_value = {}

    with patch.object(predict, "get_default_registry", return_value=mock_reg):
        first, second, master = predict._get_first_stage_models_and_master("kodate")

    assert "lgb" in first
    assert second == {}
    assert master == {}
    mock_reg.models.assert_called_once_with("kodate", "first_stage")


def test_model_registry_clear_models_empties_caches():
    """Verify Issue #1872: ModelRegistry.clear_models releases cached stage and p10 models."""
    from package.ml.inference.model_registry import ModelRegistry

    reg = ModelRegistry()
    reg._models[("kodate", "first_stage")] = {"lgb": object()}
    reg._p10_models[("kodate", "first_stage")] = object()

    reg.clear_models()

    assert reg._models == {}
    assert reg._p10_models == {}


def test_bulk_evaluation_groups_by_property_type_and_clears_models_between_groups():
    """Verify Issue #1872: run_bulk_evaluation clears model cache after each property_type group."""
    from package.ml.evaluation import runner

    m1 = type("SumifuMansion", (), {})
    m2 = type("MitsuiKodate", (), {})
    m3 = type("NomuraMansion", (), {})

    mock_reg = MagicMock()
    mock_qs = MagicMock()
    mock_qs.only.return_value = []

    with (
        patch.object(runner.PropertyEvaluation.objects, "all", return_value=mock_qs),
        patch.object(runner, "get_all_property_models", return_value=[m1, m2, m3]),
        patch.object(runner, "evaluate_single_model", return_value=(1, 0, 0, 0)),
        patch.object(runner, "notify_slack"),
        patch.object(runner, "clear_real_property_cache"),
        patch.object(runner, "clear_candidate_pool_cache"),
        patch("package.ml.inference.model_registry.get_default_registry", return_value=mock_reg),
    ):
        runner.run_bulk_evaluation(concurrency=1)

    # mansion group and kodate group -> clear_models called twice
    assert mock_reg.clear_models.call_count == 2


def test_heim_parser_skips_undecided_price_cleanly():
    """Verify HeimParser raises SkipPropertyException for undecided price (販売価格: 未定)."""
    import pytest
    from bs4 import BeautifulSoup
    from package.parser.baseParser import SkipPropertyException
    from package.parser.heimParser import HeimTochiParser

    parser = HeimTochiParser()
    soup = BeautifulSoup("<table><tr><td>販売価格</td><td>未定</td></tr></table>", "html.parser")
    with pytest.raises(SkipPropertyException):
        parser._parsePrice(soup, specs={"販売価格": "未定"})


def test_catboost_disables_file_writing_for_2gi_ram():
    """Verify Issue #1871: CatBoostRegressor disables file writing to reduce memory/IO overhead."""
    from package.ml.training.regressors import get_regressor

    reg = get_regressor("cat", use_anchor_residual=False)
    assert reg.get_params().get("allow_writing_files") is False


def test_train_property_type_invokes_on_stream_consumed_before_training():
    """Verify Issue #1871: train_property_type releases upstream caches via callback before fitting."""
    import pandas as pd
    from package.ml.training import pipeline

    call_order: list[str] = []

    def _on_consumed():
        call_order.append("consumed")

    def _fake_clean(df, ptype):
        call_order.append("clean")
        return df

    dummy_df = pd.DataFrame([{"price": 5000.0, "input_date": "2026-11-28"} for _ in range(15)])
    fake_ensemble = MagicMock(weights={}, smearing_factor=1.0, location_encoder=None, p10_conformal_offset=0.0)

    with (
        patch.object(pipeline, "_resolve_input_dataframe", return_value=dummy_df),
        patch.object(pipeline, "clean_training_data", side_effect=_fake_clean),
        patch.object(pipeline, "calculate_time_decay_weights", return_value=None),
        patch.object(pipeline, "train_and_compare", return_value=fake_ensemble),
        patch.object(pipeline, "save_stage_models"),
        patch.object(pipeline, "_read_host_memory_fallback", return_value=(0, 0, 0)),
        patch.object(pipeline, "_read_cpu_metrics", return_value={}),
    ):
        pipeline.train_property_type(
            "apartment",
            iter([]),
            {"apartment": {"first": ["price"], "second": ["price"]}},
            model_dir="Temp",
            all_ensemble_weights={},
            all_smearing_factors={},
            on_stream_consumed=_on_consumed,
        )

    assert call_order == ["consumed", "clean"]

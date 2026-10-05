# -*- coding: utf-8 -*-
import os
import sys
from unittest.mock import MagicMock, patch
import pytest

from scripts.ops import run_ml_pipeline
from package.ml import predict


def test_run_ml_pipeline_skip_train_arg(monkeypatch):
    """--skip-train 引数指定時に train.py の実行がスキップされること"""
    commands_run = []

    def mock_run_command(cmd, desc):
        commands_run.append((cmd, desc))

    monkeypatch.setattr(run_ml_pipeline, "run_command", mock_run_command)
    monkeypatch.setattr(run_ml_pipeline, "start_on_demand_resources", lambda dry_run=False: None)
    monkeypatch.setattr(run_ml_pipeline, "verify_barrier_completion", lambda: (True, []))
    monkeypatch.setattr(run_ml_pipeline, "send_aggregated_crawl_report", lambda: None)

    exit_code = run_ml_pipeline.main(["--dry-run", "--skip-train"])
    assert exit_code == 0

    train_calls = [desc for cmd, desc in commands_run if "train.py" in " ".join(cmd)]
    assert len(train_calls) == 0, "train.py should NOT be executed when --skip-train is passed"

    bulk_calls = [desc for cmd, desc in commands_run if "run_bulk_ml_evaluation.py" in " ".join(cmd)]
    assert len(bulk_calls) == 1, "run_bulk_ml_evaluation.py should be executed"


def test_run_ml_pipeline_skip_train_env(monkeypatch):
    """ML_PIPELINE_SKIP_TRAIN=true 環境変数指定時に train.py の実行がスキップされること"""
    commands_run = []

    def mock_run_command(cmd, desc):
        commands_run.append((cmd, desc))

    monkeypatch.setattr(run_ml_pipeline, "run_command", mock_run_command)
    monkeypatch.setattr(run_ml_pipeline, "start_on_demand_resources", lambda dry_run=False: None)
    monkeypatch.setattr(run_ml_pipeline, "verify_barrier_completion", lambda: (True, []))
    monkeypatch.setattr(run_ml_pipeline, "send_aggregated_crawl_report", lambda: None)
    monkeypatch.setenv("ML_PIPELINE_SKIP_TRAIN", "true")

    exit_code = run_ml_pipeline.main(["--dry-run"])
    assert exit_code == 0

    train_calls = [desc for cmd, desc in commands_run if "train.py" in " ".join(cmd)]
    assert len(train_calls) == 0, "train.py should NOT be executed when ML_PIPELINE_SKIP_TRAIN is true"


def test_predict_ensure_models_available_downloads_from_storage(tmp_path, monkeypatch):
    """ローカルにモデルが存在しない場合、ストレージから自動ダウンロードされること"""
    mock_storage = MagicMock()
    mock_storage.list_files.return_value = ["ml_models/mansion_first_stage_lgb.joblib", "ml_models/other.txt"]

    monkeypatch.setattr(predict, "get_storage_manager", lambda: mock_storage)

    model_dir = str(tmp_path / "models")
    predict.ensure_models_available(model_dir)

    assert mock_storage.list_files.called
    assert mock_storage.download_file.called
    call_args = mock_storage.download_file.call_args[0]
    assert call_args[0] == "ml_models/mansion_first_stage_lgb.joblib"
    assert call_args[1] == os.path.join(model_dir, "mansion_first_stage_lgb.joblib")

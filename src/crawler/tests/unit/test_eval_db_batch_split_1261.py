"""Issue #1261: 評価系DBバッチサイズは書き込み(100)と読み込み(1000)を別定数に分離する"""
import inspect

import pytest

from package.ml import constants
from package.ml.constants import EVAL_DB_READ_CHUNK_SIZE, EVAL_DB_WRITE_BATCH_SIZE
from package.ml.evaluation import persistence, runner, targets


def test_write_batch_size_is_100_and_read_chunk_size_is_1000():
    assert EVAL_DB_WRITE_BATCH_SIZE == 100
    assert EVAL_DB_READ_CHUNK_SIZE == 1000


def test_legacy_shared_constant_is_removed():
    assert not hasattr(constants, "EVAL_DB_BATCH_SIZE")


def test_persistence_uses_write_batch_size():
    sig = inspect.signature(persistence.bulk_update_evaluation_records)
    assert sig.parameters["batch_size"].default == EVAL_DB_WRITE_BATCH_SIZE


def test_runner_defaults_are_separated():
    assert runner.DEFAULT_WRITE_BATCH_SIZE == EVAL_DB_WRITE_BATCH_SIZE
    assert runner.DEFAULT_READ_CHUNK_SIZE == EVAL_DB_READ_CHUNK_SIZE
    sig = inspect.signature(runner.evaluate_single_model)
    assert sig.parameters["batch_size"].default == EVAL_DB_WRITE_BATCH_SIZE
    assert sig.parameters["chunk_size"].default == EVAL_DB_READ_CHUNK_SIZE


def test_targets_chunk_size_uses_read_chunk_size():
    sig = inspect.signature(targets.iter_unprocessed_chunks)
    assert sig.parameters["chunk_size"].default == EVAL_DB_READ_CHUNK_SIZE


def test_evaluate_single_model_passes_read_and_write_sizes_separately(monkeypatch):
    captured = {}

    def fake_iter(**kwargs):
        captured["chunk_size"] = kwargs["chunk_size"]
        return iter([([object()], 0)])

    def fake_save(chunk, preds, eval_map, company, ptype, **kwargs):
        captured["batch_size"] = kwargs["batch_size"]
        return 1, 0

    monkeypatch.setattr(runner, "iter_unprocessed_chunks", fake_iter)
    monkeypatch.setattr(runner, "bulk_predict_first_stage", lambda chunk: [1.0] * len(chunk))
    monkeypatch.setattr(runner, "save_chunk", fake_save)
    monkeypatch.setattr(runner, "close_old_connections", lambda: None)
    monkeypatch.setattr(runner, "resolve_company_and_type", lambda name: ("c", "mansion"))

    class DummyModel:
        pass

    runner.evaluate_single_model(DummyModel, {}, False, None, batch_size=100, chunk_size=1000)
    assert captured == {"chunk_size": 1000, "batch_size": 100}


@pytest.mark.parametrize("script", [
    "scripts.ops.fast_reevaluate_evaluations",
    "scripts.maintenance.repair_anomalous_predictions",
    "scripts.maintenance.resolve_duplicate_evaluations",
])
def test_scripts_do_not_reference_legacy_constant(script):
    import importlib.util
    spec = importlib.util.find_spec(script)
    source = open(spec.origin, encoding="utf-8").read()
    assert "EVAL_DB_BATCH_SIZE" not in source
    assert "EVAL_DB_WRITE_BATCH_SIZE" in source

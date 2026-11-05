"""Issue #1258: 評価系 DB 一括書き込みバッチサイズは EVAL_DB_BATCH_SIZE (=100) に一元化する"""
import inspect

from package.ml.constants import EVAL_DB_BATCH_SIZE
from package.ml.evaluation import persistence, runner, targets


def test_eval_db_batch_size_is_100():
    assert EVAL_DB_BATCH_SIZE == 100


def test_runner_default_batch_size_references_constant():
    assert runner.DEFAULT_BATCH_SIZE == EVAL_DB_BATCH_SIZE
    sig = inspect.signature(runner.evaluate_single_model)
    assert sig.parameters["batch_size"].default == EVAL_DB_BATCH_SIZE


def test_persistence_default_batch_size_references_constant():
    sig = inspect.signature(persistence.bulk_update_evaluation_records)
    assert sig.parameters["batch_size"].default == EVAL_DB_BATCH_SIZE


def test_targets_chunk_size_references_constant():
    sources = [
        inspect.signature(fn).parameters["chunk_size"].default
        for fn in vars(targets).values()
        if inspect.isfunction(fn) and "chunk_size" in inspect.signature(fn).parameters
    ]
    assert EVAL_DB_BATCH_SIZE in sources

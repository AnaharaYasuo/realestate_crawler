"""
Unit tests for Issue #795: Adaptive Concurrency and DB Overload Throttling
"""
import os
import time
from unittest.mock import patch
from django.db import OperationalError

from package.api.adaptive_concurrency import AdaptiveConcurrencyController


def test_job_parallel_default_is_9():
    """アクセプタンス基準1: run_all_crawlers.py のデフォルト並行度が 9 であること"""
    from scripts.ops.run_all_crawlers import parse_args
    with patch("sys.argv", ["run_all_crawlers.py"]):
        args = parse_args()
        assert args.parallel == 9
        assert args.playwright_parallel == 3


def test_adaptive_concurrency_allocation_by_active_jobs():
    """アクセプタンス基準2: 稼働中ジョブ数に応じた詳細並行度のアロケーション"""
    # 1ジョブ（単独実行時）は最大高速化（15並行）
    assert AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=1) == 15

    # 2ジョブ（少数実行時）は 12並行
    assert AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=2) == 12

    # 4ジョブは 8並行
    assert AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=4) == 8

    # 6ジョブは 5並行
    assert AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=6) == 5

    # 8ジョブ以上（多数並行時）は安全下限（4並行）
    assert AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=8) == 4
    assert AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=12) == 4


def test_cloud_detail_concurrency_env_overrides():
    """環境変数 CLOUD_DETAIL_CONCURRENCY が設定されている場合は優先されること"""
    with patch.dict(os.environ, {"CLOUD_DETAIL_CONCURRENCY": "7"}):
        assert AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=1) == 7
        assert AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=8) == 7


def test_db_overload_error_detection():
    """アクセプタンス基準3: DB過負荷エラー（1040, 2006, 1205等）の判定"""
    err_1040 = OperationalError(1040, "Too many connections")
    err_2006 = OperationalError(2006, "MySQL server has gone away")
    err_1205 = OperationalError(1205, "Lock wait timeout exceeded")
    err_other = OperationalError(1054, "Unknown column 'foo' in 'field list'")

    assert AdaptiveConcurrencyController.is_db_overload_error(err_1040) is True
    assert AdaptiveConcurrencyController.is_db_overload_error(err_2006) is True
    assert AdaptiveConcurrencyController.is_db_overload_error(err_1205) is True
    assert AdaptiveConcurrencyController.is_db_overload_error(err_other) is False


def test_db_overload_throttling_and_recovery(tmp_path):
    """アクセプタンス基準3: DB過負荷発生時に最小並行度（2）へスロットリングされ、時間経過で復帰すること"""
    state_file = str(tmp_path / "test_concurrency_state.json")
    with patch.object(AdaptiveConcurrencyController, "STATE_FILE", state_file):
        # 初期状態はスロットリングなし
        assert AdaptiveConcurrencyController.is_throttled() is False
        assert AdaptiveConcurrencyController.get_effective_concurrency(active_jobs=1) == 15

        # 過負荷を記録
        AdaptiveConcurrencyController.record_db_overload("Too many connections")
        assert AdaptiveConcurrencyController.is_throttled() is True

        # スロットリング中は強制的に最小値（2）となる
        assert AdaptiveConcurrencyController.get_effective_concurrency(active_jobs=1) == 2

        # クールダウン時間を経過させた場合は復帰
        with patch.object(AdaptiveConcurrencyController, "_get_current_time", return_value=time.time() + 70):
            assert AdaptiveConcurrencyController.is_throttled() is False
            assert AdaptiveConcurrencyController.get_effective_concurrency(active_jobs=1) == 15

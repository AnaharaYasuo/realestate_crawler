from unittest.mock import patch
import pytest

from scripts.ops import run_ml_pipeline


def test_can_stop_shared_proxysql_returns_false_when_not_cloud(monkeypatch):
    """ローカル環境 (IS_CLOUD 未設定) の場合は停止拒否して Safety-Net に委譲すること"""
    monkeypatch.delenv("IS_CLOUD", raising=False)
    assert run_ml_pipeline._can_stop_shared_proxysql() is False


def test_can_stop_shared_proxysql_returns_false_when_other_cloud_run_active(monkeypatch):
    """クラウド環境でも他に実行中ジョブがある場合は停止拒否すること"""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "ml-job-exec-1")

    with patch.object(run_ml_pipeline, "has_active_other_cloud_run_executions", return_value=True) as mock_check:
        assert run_ml_pipeline._can_stop_shared_proxysql() is False
        mock_check.assert_called_once_with(current_execution_id="ml-job-exec-1")


def test_can_stop_shared_proxysql_returns_true_when_cloud_and_no_other_job(monkeypatch):
    """クラウド環境かつ他に実行中ジョブがない場合は停止許可すること"""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "ml-job-exec-1")

    with patch.object(run_ml_pipeline, "has_active_other_cloud_run_executions", return_value=False) as mock_check:
        assert run_ml_pipeline._can_stop_shared_proxysql() is True
        mock_check.assert_called_once_with(current_execution_id="ml-job-exec-1")


def test_teardown_skips_scaling_when_guard_returns_false(monkeypatch):
    """_can_stop_shared_proxysql が False の場合は scale_proxysql_mig が呼ばれないこと"""
    monkeypatch.delenv("IS_CLOUD", raising=False)

    with patch.object(run_ml_pipeline, "_can_stop_shared_proxysql", return_value=False), \
         patch.object(run_ml_pipeline, "scale_proxysql_mig") as mock_scale, \
         patch.object(run_ml_pipeline, "run_command", side_effect=RuntimeError("Pipeline failed")):
        
        with pytest.raises(RuntimeError, match="Pipeline failed"):
            # main() を引数模倣で実行
            with patch("sys.argv", ["run_ml_pipeline.py", "--dry-run"]):
                run_ml_pipeline.main()

        mock_scale.assert_not_called()


def test_teardown_calls_scaling_when_guard_returns_true(monkeypatch):
    """_can_stop_shared_proxysql が True の場合は scale_proxysql_mig が呼ばれること"""
    with patch.object(run_ml_pipeline, "_can_stop_shared_proxysql", return_value=True), \
         patch.object(run_ml_pipeline, "scale_proxysql_mig") as mock_scale, \
         patch.object(run_ml_pipeline, "run_command", side_effect=RuntimeError("Pipeline failed")):
        
        with pytest.raises(RuntimeError, match="Pipeline failed"):
            with patch("sys.argv", ["run_ml_pipeline.py", "--dry-run"]):
                run_ml_pipeline.main()

        mock_scale.assert_called_once_with(target_size=0, dry_run=True)

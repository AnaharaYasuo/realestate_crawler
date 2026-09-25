"""
Unit tests for Cloud Run Coordinator timeout resilience and ProxySQL MIG teardown (Issue #444).
Guarantees ProxySQL MIG is safely scaled down to 0 on SIGTERM or when task deadline approaches.
"""

import os
import signal
from unittest.mock import MagicMock, patch

import pytest

CRAWLER_SCRIPTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../scripts")
)
TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../terraform")
)


def test_scheduler_tf_has_hourly_safety_net():
    """Verify terraform/scheduler.tf schedules safety net hourly during night batch hours (17-21 UTC)."""
    scheduler_tf = os.path.join(TERRAFORM_DIR, "scheduler.tf")
    with open(scheduler_tf, "r", encoding="utf-8") as f:
        content = f.read()

    assert "crawler_safety_net_trigger" in content
    assert 'schedule         = "0 17-21 * * *"' in content or 'schedule = "0 17-21 * * *"' in content, \
        "Safety net must be scheduled hourly (0 17-21 * * *) during night batch window."


def test_run_pipeline_registers_signal_and_atexit_handlers():
    """Verify run_pipeline.py registers SIGTERM/SIGINT and atexit handlers."""
    pipeline_py = os.path.join(CRAWLER_SCRIPTS_DIR, "ops", "run_pipeline.py")
    with open(pipeline_py, "r", encoding="utf-8") as f:
        content = f.read()

    assert "signal.signal(signal.SIGTERM" in content, "run_pipeline.py must register SIGTERM handler"
    assert "signal.signal(signal.SIGINT" in content, "run_pipeline.py must register SIGINT handler"
    assert "atexit.register" in content, "run_pipeline.py must register atexit teardown handler"


def test_sigterm_handler_kills_active_proc_and_scales_down_mig(monkeypatch):
    """Verify SIGTERM handler terminates any active subprocess and scales down ProxySQL MIG."""
    from scripts.ops import run_pipeline

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # Process is running
    monkeypatch.setattr(run_pipeline, "_active_proc", mock_proc)
    monkeypatch.setattr(run_pipeline, "_is_coordinator", True)
    monkeypatch.setenv("IS_CLOUD", "true")

    with patch.object(run_pipeline, "scale_proxysql_mig") as mock_scale, \
         pytest.raises(SystemExit) as exc_info:
        run_pipeline._sigterm_handler(signal.SIGTERM, None)

    # Active child process must be terminated
    assert mock_proc.terminate.called or mock_proc.kill.called
    # ProxySQL MIG must be scaled down to 0
    mock_scale.assert_called_with(target_size=0)
    # Exit with code 128 + SIGTERM (143)
    assert exc_info.value.code == 128 + signal.SIGTERM


def test_execute_safety_teardown_invokes_inline_scale_proxysql_mig(monkeypatch):
    """Verify _execute_safety_teardown calls scale_proxysql_mig(target_size=0) directly inline."""
    from scripts.ops import run_pipeline

    monkeypatch.setenv("IS_CLOUD", "true")

    with patch.object(run_pipeline, "scale_proxysql_mig") as mock_scale, \
         patch.object(run_pipeline, "patch_proxysql_autoscaler") as mock_patch, \
         patch.object(run_pipeline, "run_command") as mock_cmd:
        run_pipeline._execute_safety_teardown(is_coordinator=True, scripts_dir="/fake/dir")

        mock_scale.assert_called_with(target_size=0)
        mock_patch.assert_called_with(min_replicas=0, max_replicas=0)
        assert mock_cmd.called


def test_wait_for_all_tasks_timeout_bounded_by_remaining_time(monkeypatch):
    """Verify wait_for_all_tasks dynamically constrains timeout based on remaining pipeline time."""
    from scripts.ops import run_pipeline

    monkeypatch.setenv("IS_CLOUD", "true")
    # Set maximum pipeline duration to 1000s, elapsed time 600s -> remaining time 400s
    monkeypatch.setattr(run_pipeline, "_pipeline_start_time", 1000.0)
    monkeypatch.setattr(run_pipeline, "get_remaining_pipeline_time", lambda: 400.0)

    with patch.object(run_pipeline, "wait_for_all_tasks") as mock_wait, \
         patch.object(run_pipeline, "run_command"):
        mock_wait.return_value = (True, [])
        run_pipeline._run_crawler_step(
            is_task_array=True,
            is_coordinator=True,
            task_index=0,
            task_count=2,
            ops_dir="/fake/ops",
            skip_portals=False,
        )

        assert mock_wait.called
        call_kwargs = mock_wait.call_args.kwargs
        # The timeout passed must be bounded by remaining time (400 - safe_buffer) or <= 400
        assert call_kwargs["timeout_sec"] <= 400


def test_self_graceful_shutdown_when_timeout_approaching(monkeypatch):
    """Verify pipeline initiates self graceful shutdown if remaining time is below safe threshold."""
    from scripts.ops import run_pipeline

    # Simulate remaining time is critically low (< SAFE_SHUTDOWN_BUFFER_SEC)
    monkeypatch.setattr(run_pipeline, "is_deadline_approaching", lambda buffer=300: True)

    with pytest.raises(TimeoutError) as exc_info:
        run_pipeline.check_deadline_or_raise("Next Step")

    assert "approaching Cloud Run timeout" in str(exc_info.value)

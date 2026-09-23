"""
Unit tests for run_pipeline.py teardown behavior in finally block.
"""
from unittest.mock import patch
import pytest

from scripts.ops import run_pipeline


def test_pipeline_crash_triggers_finally_teardown():
    """When a pipeline step crashes in cloud coordinator mode, ensure_resources_stopped is executed in finally."""
    with patch.dict("os.environ", {"IS_CLOUD": "true"}), \
         patch("sys.argv", ["run_pipeline.py"]), \
         patch("scripts.ops.run_pipeline.get_task_config", return_value=(0, 1)), \
         patch("scripts.ops.run_pipeline.run_command") as mock_run_cmd:

        # Let the first command (Step 0) raise an exception
        mock_run_cmd.side_effect = [
            RuntimeError("Step failed!"),  # Step 0 crashes
            None,                          # Teardown in finally succeeds
        ]

        with pytest.raises(SystemExit) as exc_info:
            run_pipeline.main()

        assert exc_info.value.code == 1
        # Check that teardown was called in finally
        assert mock_run_cmd.call_count == 2
        teardown_call = mock_run_cmd.call_args_list[-1]
        assert "ensure_resources_stopped.py" in teardown_call[0][0][1]
        assert "Teardown" in teardown_call[0][1]
        assert teardown_call[1].get("timeout") == 60


def test_pipeline_non_cloud_skips_teardown():
    """When running locally (IS_CLOUD not set), teardown is skipped on crash."""
    with patch.dict("os.environ", {}, clear=True), \
         patch("sys.argv", ["run_pipeline.py"]), \
         patch("scripts.ops.run_pipeline.get_task_config", return_value=(0, 1)), \
         patch("scripts.ops.run_pipeline.run_command") as mock_run_cmd:

        mock_run_cmd.side_effect = RuntimeError("Step failed!")

        with pytest.raises(SystemExit) as exc_info:
            run_pipeline.main()

        assert exc_info.value.code == 1
        # Only the crashing step was called; no teardown
        assert mock_run_cmd.call_count == 1


def test_run_command_timeout_terminates_child_process():
    """run_command terminates child process and raises TimeoutError when timeout expires."""
    import sys
    # Subprocess sleeping longer than timeout
    sleep_cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    with pytest.raises(TimeoutError) as exc_info:
        run_pipeline.run_command(sleep_cmd, "Test Sleep Timeout", timeout=0.2)

    assert "timed out after 0.2s" in str(exc_info.value)


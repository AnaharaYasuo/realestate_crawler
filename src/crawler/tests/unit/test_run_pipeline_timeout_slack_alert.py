# -*- coding: utf-8 -*-
"""
Issue #635: 親プロセス (run_pipeline.py) でクローラーがタイムアウトまたは強制終了した際に、
Slack (#property_alert, #dev-agent) へ即座に通知が発報されることのテスト。
"""
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from scripts.ops import run_pipeline


@pytest.mark.asyncio
async def test_notify_pipeline_timeout_sends_slack_alert():
    mock_send_summary = AsyncMock(return_value=True)
    mock_send_dev = AsyncMock(return_value=True)

    with patch.object(run_pipeline.slack_module, "send_crawling_summary_alert", mock_send_summary), \
         patch.object(run_pipeline.slack_module, "send_dev_report", mock_send_dev):
        await run_pipeline.notify_pipeline_timeout(
            task_index=1,
            task_count=8,
            desc="Step 1/6: Parallel Crawling [Task 1/8]",
            reason="Timeout after 14400s",
        )
        assert mock_send_summary.called or mock_send_dev.called
        call_msg = (mock_send_summary.call_args or mock_send_dev.call_args)[0][0]
        assert "タイムアウト" in call_msg or "Timeout" in call_msg or "TIMEOUT" in call_msg
        assert "Task 1/8" in call_msg


def test_run_command_raises_timeout_and_triggers_alert():
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.wait.side_effect = [
        subprocess.TimeoutExpired(cmd=["sleep", "100"], timeout=0.01),
        0,
    ]
    mock_proc.stdout.readline.return_value = ""
    mock_notify = MagicMock()

    with patch.object(run_pipeline, "notify_pipeline_timeout_sync", mock_notify), \
         patch.object(run_pipeline.subprocess, "Popen", return_value=mock_proc):
        with pytest.raises(TimeoutError):
            run_pipeline.run_command(["sleep", "100"], "Test Command", timeout=0.01)
        mock_notify.assert_called_once()


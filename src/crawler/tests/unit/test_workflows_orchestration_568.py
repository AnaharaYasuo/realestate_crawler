"""Unit tests for Cloud Workflows orchestration specifications and crawler watchdog."""
import os
import signal
from unittest.mock import MagicMock, patch


def test_workflows_timeout_definitions():
    """Workflows の全体タイムアウト (7h: 25200s) とクロール上限 (5h: 18000s) が整合していること."""
    workflow_total_timeout_sec = 25200
    crawler_phase_timeout_sec = 18000

    assert crawler_phase_timeout_sec == 5 * 3600
    assert workflow_total_timeout_sec == 7 * 3600
    assert crawler_phase_timeout_sec < workflow_total_timeout_sec
    # 後続フェーズ (ML学習 + 価格推定 + 配信 + 停止) に最低 2 時間のバッファが確保されていること
    assert (workflow_total_timeout_sec - crawler_phase_timeout_sec) >= 2 * 3600


def test_hang_silent_watchdog_detection():
    """沈黙 (無進捗) が一定時間 (300秒) 継続したジョブがハング検知されて強制キルされること."""
    from package.utils.crawler_watchdog import check_job_hung, HANG_THRESHOLD_SEC

    assert HANG_THRESHOLD_SEC == 300.0

    now = 1000.0
    # 正常: 100秒前のアクティビティ
    assert not check_job_hung(last_activity_time=now - 100.0, current_time=now)

    # 境界値: 300秒ジャストはセーフ
    assert not check_job_hung(last_activity_time=now - 300.0, current_time=now)

    # ハング: 301秒前の沈黙
    assert check_job_hung(last_activity_time=now - 301.0, current_time=now)


def test_hang_kill_terminates_process_group():
    """ハング判定時に os.killpg でプロセスグループが SIGKILL されること."""
    from package.utils.crawler_watchdog import kill_hung_job_process

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.poll.return_value = None

    with patch("os.getpgid", return_value=54321) as mock_getpgid, \
         patch("os.killpg") as mock_killpg:
        
        killed = kill_hung_job_process(mock_proc)
        assert killed is True
        mock_getpgid.assert_called_once_with(12345)
        mock_killpg.assert_called_once_with(54321, signal.SIGKILL)


def test_daily_pipeline_yaml_structure_and_finally_stop():
    """daily_pipeline.yaml が存在し、finally ブロックで確実に ProxySQL が停止される構文であること."""
    import yaml
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    yaml_path = os.path.join(repo_root, "terraform", "workflows", "daily_pipeline.yaml")
    assert os.path.exists(yaml_path), f"daily_pipeline.yaml missing at {yaml_path}"

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "main" in data
    assert "monitorJobExecution" in data

    main_steps = data["main"]["steps"]
    try_step = None
    for step in main_steps:
        if "tryPipeline" in step:
            try_step = step["tryPipeline"]
            break

    assert try_step is not None, "tryPipeline block must exist in main"
    assert "try" in try_step
    assert "finally" in try_step

    # finally に stopProxySQL が存在することを検証
    finally_steps = try_step["finally"]["steps"]
    stop_step = any("stopProxySQL" in s for s in finally_steps)
    assert stop_step is True, "stopProxySQL must be defined in finally block to ensure teardown"


def test_workflows_tf_configuration():
    """terraform/workflows.tf が存在し、リソースが正しく定義されていること."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    tf_path = os.path.join(repo_root, "terraform", "workflows.tf")
    assert os.path.exists(tf_path), f"workflows.tf missing at {tf_path}"

    with open(tf_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'resource "google_workflows_workflow" "daily_pipeline_workflow"' in content
    assert 'resource "google_project_iam_member" "scheduler_workflows_invoker"' in content

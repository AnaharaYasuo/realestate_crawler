"""Unit tests for Cloud Workflows orchestration specifications and crawler watchdog."""
import os
import signal
from unittest.mock import MagicMock, patch


def test_workflows_timeout_definitions():
    """Workflows の全体タイムアウト (7h: 25200s) とクロール上限 (5h: 18000s) が YAML 定義から正しく取得・整合していること."""
    import re
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    yaml_path = os.path.join(repo_root, "terraform", "workflows", "daily_pipeline.yaml")
    assert os.path.exists(yaml_path), f"daily_pipeline.yaml missing at {yaml_path}"

    with open(yaml_path, "r", encoding="utf-8") as f:
        content = f.read()

    # YAMLから動的に maxPipelineDurationSec と crawlTimeoutSec の設定値を抽出
    max_duration_match = re.search(r"maxPipelineDurationSec:\s*(\d+)", content)
    crawl_timeout_match = re.search(r"crawlTimeoutSec[^\n\r]*?(\d{4,6})", content)

    assert max_duration_match is not None, "maxPipelineDurationSec must be defined in daily_pipeline.yaml"
    assert crawl_timeout_match is not None, "crawlTimeoutSec must be defined in daily_pipeline.yaml"

    workflow_total_timeout_sec = int(max_duration_match.group(1))
    crawler_phase_timeout_sec = int(crawl_timeout_match.group(1))

    assert crawler_phase_timeout_sec == 5 * 3600, f"Expected 18000, got {crawler_phase_timeout_sec}"
    assert workflow_total_timeout_sec == 7 * 3600, f"Expected 25200, got {workflow_total_timeout_sec}"
    assert crawler_phase_timeout_sec < workflow_total_timeout_sec
    # 後続フェーズ (ML学習 + 価格推定 + 配信 + 停止) に最低 2 時間のバッファが確保されていること
    assert (workflow_total_timeout_sec - crawler_phase_timeout_sec) >= 2 * 3600


def test_hang_silent_watchdog_detection():
    """沈黙 (無進捗) 判定で閾値0以下は無効化され、正の閾値設定時のみハング検知されること."""
    from package.utils.crawler_watchdog import check_job_hung

    now = 1000.0
    # 閾値 0.0 (デフォルト無効化): いかに時間が経過していてもハング検知されないこと
    assert not check_job_hung(last_activity_time=now - 10000.0, current_time=now, threshold_sec=0.0)

    # 有効化時 (300秒)
    # 正常: 100秒前のアクティビティ
    assert not check_job_hung(last_activity_time=now - 100.0, current_time=now, threshold_sec=300.0)

    # 境界値: 300秒ジャストはセーフ
    assert not check_job_hung(last_activity_time=now - 300.0, current_time=now, threshold_sec=300.0)

    # ハング: 301秒前の沈黙
    assert check_job_hung(last_activity_time=now - 301.0, current_time=now, threshold_sec=300.0)


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


def test_daily_pipeline_yaml_structure_and_cleanup():
    """daily_pipeline.yaml が存在し、正常時・異常時の両方で確実に ProxySQL が停止される構文であること."""
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
    assert "except" in try_step

    # except に stopProxySQLOnError が存在することを検証
    except_steps = try_step["except"]["steps"]
    stop_on_err = any("stopProxySQLOnError" in s for s in except_steps)
    assert stop_on_err is True, "stopProxySQLOnError must be defined in except block to ensure teardown on error"

    # 正常系フロー末尾に stopProxySQLOnSuccess が存在することを検証
    stop_on_succ = any("stopProxySQLOnSuccess" in s for s in main_steps)
    assert stop_on_succ is True, "stopProxySQLOnSuccess must be defined in main steps for clean teardown"


def test_workflows_tf_configuration():
    """terraform/workflows.tf が存在し、リソースが正しく定義されていること."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    tf_path = os.path.join(repo_root, "terraform", "workflows.tf")
    assert os.path.exists(tf_path), f"workflows.tf missing at {tf_path}"

    with open(tf_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'resource "google_workflows_workflow" "daily_pipeline_workflow"' in content
    assert 'resource "google_project_iam_member" "scheduler_workflows_invoker"' in content

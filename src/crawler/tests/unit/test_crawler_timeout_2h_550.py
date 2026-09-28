# -*- coding: utf-8 -*-
"""
Issue #550: クローラーパイプライン Cloud Run Job のタスク上限 1 時間 -> 2 時間延長と、
内部締め切り・Safety-Net・ML 起動・バックアップ時刻の連動修正の回帰テスト。
"""
import inspect
import os
import re
import shutil
import subprocess
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from scripts import ensure_resources_stopped
from scripts.ops import run_pipeline

TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "terraform")
)
WORKFLOW_PATH = os.path.join(TERRAFORM_DIR, "..", ".github", "workflows", "deploy-production.yml")
CLOUD_RUN_JOBS_MAX_TIMEOUT_SEC = 86400
HUNG_GRACE_SEC = 600


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _strip_comments(content):
    return "\n".join(re.sub(r"\s#.*$", "", line) for line in content.splitlines() if not line.lstrip().startswith("#"))


def _variable_block(name):
    content = _read(os.path.join(TERRAFORM_DIR, "variables.tf"))
    head = f'variable "{name}"'
    assert head in content
    return content.split(head, 1)[1].split("\nvariable ", 1)[0]


def _var_default(name):
    return re.search(r'default\s*=\s*"([^"]+)"', _variable_block(name)).group(1)


def _crawler_timeout_sec():
    return int(_var_default("crawler_timeout").rstrip("s"))


def _job_block(name):
    content = _strip_comments(_read(os.path.join(TERRAFORM_DIR, "cloud_run_job.tf")))
    head = f'resource "google_cloud_run_v2_job" "{name}"'
    assert head in content
    return content.split(head, 1)[1].split("\nresource ", 1)[0]


def _cron_seconds(cron):
    minute, hour = (int(v) for v in cron.split()[:2])
    return hour * 3600 + minute * 60


def _crawler_latest_end_sec():
    return _cron_seconds(_var_default("schedule_cron")) + _crawler_timeout_sec()


def _ml_latest_end_sec():
    ml_timeout = int(re.search(r'timeout\s*=\s*"(\d+)s"', _job_block("ml_pipeline_job")).group(1))
    return _cron_seconds(_var_default("ml_pipeline_schedule_cron")) + ml_timeout


def _deploy_step(job_name):
    content = _strip_comments(_read(WORKFLOW_PATH))
    head = f"gcloud run jobs update {job_name} "
    assert head in content
    return content.split(head, 1)[1].split("- name:", 1)[0]


# ---------------------------------------------------------------------------
# 基準1: crawler_timeout のデフォルト 7200s と変数説明
# ---------------------------------------------------------------------------


def test_crawler_timeout_default_is_two_hours():
    assert _var_default("crawler_timeout") == "7200s"


def test_crawler_timeout_description_matches_cloud_run_limit():
    block = _variable_block("crawler_timeout")
    description = re.search(r'description\s*=\s*"([^"]+)"', block).group(1)
    assert "up to 1h" not in description
    assert str(CLOUD_RUN_JOBS_MAX_TIMEOUT_SEC) in description


def _validation_upper_bound():
    block = _variable_block("crawler_timeout")
    condition = re.search(r"validation\s*\{[^}]*?condition\s*=\s*(.+)", block, re.DOTALL).group(1).splitlines()[0]
    return int(re.search(r'trimsuffix\(var\.crawler_timeout,\s*"s"\)\)\s*<=\s*(\d+)', condition).group(1))


def test_crawler_timeout_validation_within_cloud_run_limit():
    upper = _validation_upper_bound()
    assert 0 < _crawler_timeout_sec() <= upper <= CLOUD_RUN_JOBS_MAX_TIMEOUT_SEC


def test_crawler_timeout_validation_cannot_exceed_hung_threshold():
    assert _validation_upper_bound() + HUNG_GRACE_SEC <= ensure_resources_stopped.DEFAULT_HUNG_THRESHOLD_SEC


def test_crawler_timeout_validation_cannot_overlap_ml_start():
    latest = _cron_seconds(_var_default("schedule_cron")) + _validation_upper_bound()
    assert latest < _cron_seconds(_var_default("ml_pipeline_schedule_cron"))


def test_crawler_job_uses_crawler_timeout_variable():
    assert re.search(r"timeout\s*=\s*var\.crawler_timeout", _job_block("crawler_pipeline_job"))


# ---------------------------------------------------------------------------
# 基準2: CLOUD_RUN_JOB_TIMEOUT_SEC の伝達と内部締め切りの一致
# ---------------------------------------------------------------------------


def test_crawler_job_passes_timeout_env_derived_from_variable():
    assert re.search(
        r'name\s*=\s*"CLOUD_RUN_JOB_TIMEOUT_SEC"\s*\n\s*value\s*=\s*trimsuffix\(var\.crawler_timeout,\s*"s"\)',
        _job_block("crawler_pipeline_job"),
    )


def _deploy_run_block(job_name):
    content = _read(WORKFLOW_PATH)
    head = f"gcloud run jobs update {job_name} "
    return content.split(head, 1)[0].rsplit("run: |", 1)[1] + head + _deploy_step(job_name)


def test_deploy_applies_crawler_timeout_and_env_from_variable():
    step = _deploy_step("realestate-crawler-pipeline-prod")
    assert "--task-timeout=${CRAWLER_TIMEOUT_SEC}s" in step
    assert "--update-env-vars=CLOUD_RUN_JOB_TIMEOUT_SEC=${CRAWLER_TIMEOUT_SEC}" in step


@pytest.mark.skipif(shutil.which("awk") is None, reason="awk not available")
def test_deploy_extracts_crawler_timeout_from_terraform():
    block = _deploy_run_block("realestate-crawler-pipeline-prod")
    command = re.search(r"CRAWLER_TIMEOUT_SEC=\$\((awk .+ terraform/variables\.tf)\)", block).group(1)
    assert 'test -n "$CRAWLER_TIMEOUT_SEC"' in block
    result = subprocess.run(
        ["sh", "-c", command],
        cwd=os.path.join(TERRAFORM_DIR, ".."),
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert result.stdout.strip() == str(_crawler_timeout_sec())


def test_run_pipeline_default_timeout_matches_crawler_timeout():
    assert run_pipeline.DEFAULT_TIMEOUT_SEC == _crawler_timeout_sec()


def _remaining(monkeypatch, env):
    monkeypatch.delenv("CLOUD_RUN_JOB_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("PIPELINE_TIMEOUT_SEC", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    now = time.time()
    monkeypatch.setattr(run_pipeline, "_pipeline_start_time", now)
    with patch.object(run_pipeline.time, "time", return_value=now):
        return run_pipeline.get_remaining_pipeline_time()


def test_internal_deadline_uses_env_passed_by_terraform(monkeypatch):
    timeout = _crawler_timeout_sec()
    assert _remaining(monkeypatch, {"CLOUD_RUN_JOB_TIMEOUT_SEC": str(timeout)}) == timeout


def test_internal_deadline_without_env_matches_crawler_timeout(monkeypatch):
    assert _remaining(monkeypatch, {}) == _crawler_timeout_sec()


def test_deadline_not_approaching_before_two_hour_limit(monkeypatch):
    """旧上限 (3600s - 300s) を超えた時点でも自己打ち切りしないこと"""
    timeout = _crawler_timeout_sec()
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("CLOUD_RUN_JOB_TIMEOUT_SEC", str(timeout))
    now = time.time()
    monkeypatch.setattr(run_pipeline, "_pipeline_start_time", now - 3400)
    with patch.object(run_pipeline.time, "time", return_value=now):
        assert run_pipeline.is_deadline_approaching() is False
    monkeypatch.setattr(run_pipeline, "_pipeline_start_time", now - (timeout - 299))
    with patch.object(run_pipeline.time, "time", return_value=now):
        assert run_pipeline.is_deadline_approaching() is True


# ---------------------------------------------------------------------------
# 基準3: Safety-Net の hung 判定閾値
# ---------------------------------------------------------------------------


def test_hung_threshold_covers_longest_job_timeout_plus_grace():
    assert ensure_resources_stopped.DEFAULT_HUNG_THRESHOLD_SEC >= _crawler_timeout_sec() + HUNG_GRACE_SEC


@pytest.mark.parametrize(
    "func",
    [ensure_resources_stopped.check_and_stop_proxysql_mig, ensure_resources_stopped.check_and_stop_proxysql_instance],
)
def test_check_functions_default_to_hung_threshold(func):
    default = inspect.signature(func).parameters["timeout_threshold_sec"].default
    assert default == ensure_resources_stopped.DEFAULT_HUNG_THRESHOLD_SEC


def test_cli_default_hung_threshold(monkeypatch):
    monkeypatch.setattr("sys.argv", ["ensure_resources_stopped.py", "--instance-name=proxysql-instance-prod"])
    check = MagicMock(return_value=SimpleNamespace(was_leaked=False))
    monkeypatch.setattr(ensure_resources_stopped, "check_and_stop_proxysql_instance", check)
    assert ensure_resources_stopped.main() == 0
    assert check.call_args.kwargs["timeout_threshold_sec"] == ensure_resources_stopped.DEFAULT_HUNG_THRESHOLD_SEC


def _inspect_with_elapsed(elapsed_sec):
    igm = MagicMock(target_size=1, status=MagicMock(autoscaler=None))
    client = MagicMock()
    client.get.return_value = igm
    execution = MagicMock(elapsed_sec=elapsed_sec, job_name="realestate-crawler-pipeline-prod")
    execution.name = "projects/p/locations/r/jobs/realestate-crawler-pipeline-prod/executions/e"
    compute = MagicMock(RegionInstanceGroupManagersClient=lambda: client)
    with patch.object(ensure_resources_stopped, "compute_v1", compute), \
         patch.object(ensure_resources_stopped, "send_slack_alert"), \
         patch.object(ensure_resources_stopped, "_get_mig_uptime_seconds", return_value=elapsed_sec + 60), \
         patch.object(ensure_resources_stopped, "_get_active_cloud_run_executions", return_value=([execution], None)), \
         patch.object(ensure_resources_stopped, "_cancel_cloud_run_execution", return_value="") as cancel:
        result = ensure_resources_stopped.check_and_stop_proxysql_mig(
            project_id="p", region="r", mig_name="proxysql-mig-prod"
        )
    return result, cancel


def test_running_crawler_within_two_hours_is_not_cancelled():
    result, cancel = _inspect_with_elapsed(float(_crawler_timeout_sec()))
    assert result.skipped_reason == "job_running"
    assert result.forced_stop is False
    cancel.assert_not_called()


def test_crawler_beyond_hung_threshold_is_cancelled():
    result, cancel = _inspect_with_elapsed(ensure_resources_stopped.DEFAULT_HUNG_THRESHOLD_SEC + 1)
    assert result.forced_stop is True
    cancel.assert_called_once()


def test_ml_pipeline_timeout_below_hung_threshold():
    ml_timeout = int(re.search(r'timeout\s*=\s*"(\d+)s"', _job_block("ml_pipeline_job")).group(1))
    assert ml_timeout < ensure_resources_stopped.DEFAULT_HUNG_THRESHOLD_SEC


# ---------------------------------------------------------------------------
# 基準4: Safety-Net / ML パイプラインのスケジュール
# ---------------------------------------------------------------------------


def _safety_net_hours():
    scheduler = _strip_comments(_read(os.path.join(TERRAFORM_DIR, "scheduler.tf")))
    block = scheduler.split('"crawler_safety_net_trigger"', 1)[1]
    first, last = re.search(r'schedule\s*=\s*"\d+ (\d+)-(\d+) ', block).groups()
    return int(first), int(last)


def test_safety_net_runs_after_latest_crawler_and_ml_end():
    first, last = _safety_net_hours()
    assert first * 3600 > _cron_seconds(_var_default("schedule_cron"))
    assert last * 3600 >= _crawler_latest_end_sec()
    assert last * 3600 >= _ml_latest_end_sec()


def test_ml_pipeline_starts_after_two_hour_crawler_deadline():
    assert _cron_seconds(_var_default("ml_pipeline_schedule_cron")) > _crawler_latest_end_sec()
    assert _var_default("ml_pipeline_schedule_cron") == "10 18 * * *"


# ---------------------------------------------------------------------------
# 基準5: Cloud SQL バックアップ開始時刻
# ---------------------------------------------------------------------------


def _backup_start_sec():
    database = _strip_comments(_read(os.path.join(TERRAFORM_DIR, "database.tf")))
    hour, minute = re.search(r'start_time\s*=\s*"(\d{2}):(\d{2})"', database).groups()
    return int(hour) * 3600 + int(minute) * 60


def test_backup_starts_after_latest_crawler_end():
    assert _backup_start_sec() >= _crawler_latest_end_sec()


def test_backup_starts_after_latest_ml_pipeline_end():
    assert _backup_start_sec() >= _ml_latest_end_sec()


def test_backup_start_time_is_on_the_hour_before_next_crawl():
    start = _backup_start_sec()
    assert start % 3600 == 0
    assert start < 24 * 3600

# -*- coding: utf-8 -*-
"""
Issue #549: クローラージョブと ML Pipeline Job の分離、および自動再実行 (max_retries) 禁止の回帰テスト。
"""
import asyncio
import datetime
import inspect
import os
import re
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from package.utils import pipeline_coordinator
from scripts import ensure_resources_stopped
from scripts.ops import run_ml_pipeline, run_pipeline

TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "terraform")
)


def _read(name):
    with open(os.path.join(TERRAFORM_DIR, name), encoding="utf-8") as f:
        return f.read()


def _strip_comments(content):
    return "\n".join(re.sub(r"\s#.*$", "", line) for line in content.splitlines() if not line.lstrip().startswith("#"))


def _resource_block(content, resource_type, resource_name):
    head = f'resource "{resource_type}" "{resource_name}"'
    content = _strip_comments(content)
    assert head in content, f"{head} must be defined"
    return content.split(head, 1)[1].split("\nresource ", 1)[0]


def _job_block(name):
    return _resource_block(_read("cloud_run_job.tf"), "google_cloud_run_v2_job", name)


def _max_retries(block):
    return int(re.search(r"max_retries\s*=\s*(\d+)", block).group(1))


def _timeout_sec(block):
    return int(re.search(r'timeout\s*=\s*"(\d+)s"', block).group(1))


def _var_default(name):
    m = re.search(
        r'variable\s+"' + name + r'"\s*\{[^}]*?default\s*=\s*"([^"]+)"',
        _read("variables.tf"),
        re.DOTALL,
    )
    assert m, f"variable {name} default not found"
    return m.group(1)


# ---------------------------------------------------------------------------
# 基準1 / 基準4: Terraform (再実行禁止・ML ジョブ設定・スケジュール)
# ---------------------------------------------------------------------------


def test_crawler_job_does_not_retry():
    assert _max_retries(_job_block("crawler_pipeline_job")) == 0


def test_ml_pipeline_job_does_not_retry():
    assert _max_retries(_job_block("ml_pipeline_job")) == 0


def test_ml_pipeline_timeout_is_below_safety_net_hung_threshold():
    threshold = inspect.signature(
        ensure_resources_stopped.check_and_stop_proxysql_mig
    ).parameters["timeout_threshold_sec"].default
    timeout = _timeout_sec(_job_block("ml_pipeline_job"))
    assert timeout == 3600
    assert timeout < threshold


def test_ml_pipeline_job_runs_with_force_arg():
    block = _job_block("ml_pipeline_job")
    assert re.search(r'args\s*=\s*\["--force"\]', block)
    assert "template[0].template[0].containers[0].args" not in block


@pytest.mark.parametrize(
    "env_name",
    [
        "SLACK_CHANNEL_ID",
        "SLACK_DEV_CHANNEL",
        "SLACK_ALERT_PROPERTY_ALERT",
        "SLACK_RECOMMEND_MANSION",
        "SLACK_RECOMMEND_KODATE",
        "SLACK_RECOMMEND_TOCHI",
        "SLACK_RECOMMEND_INVEST_APARTMENT",
        "SLACK_RECOMMEND_INVEST_KODATE",
        "PROXYSQL_INSTANCE_NAME",
        "PROXYSQL_ZONE",
        "CLOUDSQL_INSTANCE_NAME",
        "STORAGE_BACKEND",
        "STORAGE_BUCKET",
        "ML_NUM_THREADS",
        "BULK_EVAL_CONCURRENCY",
    ],
)
def test_ml_pipeline_job_defines_env_required_by_steps(env_name):
    assert f'name  = "{env_name}"' in _job_block("ml_pipeline_job")


def test_ml_pipeline_scheduler_triggers_ml_job_after_crawler_deadline():
    block = _resource_block(
        _read("scheduler.tf"), "google_cloud_scheduler_job", "ml_pipeline_daily_trigger"
    )
    assert "google_cloud_run_v2_job.ml_pipeline_job.name}:run" in block
    assert "var.ml_pipeline_schedule_cron" in block

    ml_minute, ml_hour = (int(v) for v in _var_default("ml_pipeline_schedule_cron").split()[:2])
    crawler_minute, crawler_hour = (int(v) for v in _var_default("schedule_cron").split()[:2])
    crawler_timeout = int(_var_default("crawler_timeout").rstrip("s"))
    crawler_deadline = crawler_hour * 3600 + crawler_minute * 60 + crawler_timeout
    assert ml_hour * 3600 + ml_minute * 60 > crawler_deadline
    assert _var_default("ml_pipeline_schedule_cron") == "10 20 * * *"


def test_scheduler_can_invoke_ml_pipeline_job():
    block = _resource_block(
        _read("iam.tf"), "google_cloud_run_v2_job_iam_member", "ml_pipeline_run_invoker"
    )
    assert "google_cloud_run_v2_job.ml_pipeline_job.name" in block
    assert 'role     = "roles/run.invoker"' in block
    assert "google_service_account.scheduler_invoker.email" in block


def test_safety_net_runs_after_latest_possible_ml_pipeline_end():
    scheduler = _read("scheduler.tf")
    safety = _resource_block(scheduler, "google_cloud_scheduler_job", "crawler_safety_net_trigger")
    schedule = re.search(r'schedule\s*=\s*"([^"]+)"', safety).group(1)
    hour_field = schedule.split()[1]
    if hour_field == "*":
        # Hourly 24/7 guarantees execution after latest ML pipeline end
        assert True
    else:
        last_hour = int(re.search(r'\d+-(\d+)', hour_field).group(1))
        ml_minute, ml_hour = (int(v) for v in _var_default("ml_pipeline_schedule_cron").split()[:2])
        ml_end = ml_hour * 3600 + ml_minute * 60 + _timeout_sec(_job_block("ml_pipeline_job"))
        assert last_hour * 3600 >= ml_end


def _deploy_step(job_name):
    workflow_path = os.path.join(TERRAFORM_DIR, "..", ".github", "workflows", "deploy-production.yml")
    with open(workflow_path, encoding="utf-8") as f:
        content = _strip_comments(f.read())
    head = f"gcloud run jobs update {job_name} "
    assert head in content, f"{head} must be defined"
    return content.split(head, 1)[1].split("- name:", 1)[0]


def test_deploy_disables_crawler_retries():
    assert "--max-retries=0" in _deploy_step("realestate-crawler-pipeline-prod")


@pytest.mark.parametrize("flag", ["--args=--force", "--max-retries=0", "--task-timeout=3600s"])
def test_deploy_applies_ml_pipeline_job_settings(flag):
    assert flag in _deploy_step("realestate-ml-pipeline-prod")


# ---------------------------------------------------------------------------
# 基準2: タスクアレイではクロールのみ実行して終了する
# ---------------------------------------------------------------------------


def _run_step(is_task_array, is_coordinator, task_index, task_count):
    return run_pipeline._run_crawler_step(
        is_task_array=is_task_array,
        is_coordinator=is_coordinator,
        task_index=task_index,
        task_count=task_count,
        ops_dir="/tmp/ops",
        skip_portals=False,
    )


@pytest.mark.parametrize("task_index", [0, 3])
def test_task_array_task_exits_after_own_crawl(task_index):
    with patch.object(run_pipeline, "run_command") as mock_cmd:
        assert _run_step(True, task_index == 0, task_index, 8) == (False, True)
    mock_cmd.assert_called_once()
    cmd, desc = mock_cmd.call_args.args[:2]
    assert cmd == [sys.executable, os.path.join("/tmp/ops", "run_all_crawlers.py")]
    assert f"[Task {task_index}/8]" in desc


def test_task_array_coordinator_crawl_failure_reconciles_and_exits():
    with patch.object(run_pipeline, "run_command", side_effect=RuntimeError("exit code 1")), \
         patch.object(run_pipeline, "reconcile_aborted_task_execution") as mock_reconcile:
        assert _run_step(True, True, 0, 8) == (False, False)
    mock_reconcile.assert_called_once_with(0)


@pytest.mark.parametrize(
    "name", ["wait_for_all_tasks", "send_crawling_summary_alert", "aggregate_task_array_reports"]
)
def test_crawler_pipeline_no_longer_waits_or_reports(name):
    assert not hasattr(run_pipeline, name)


def test_single_run_still_continues_to_post_crawl():
    with patch.object(run_pipeline, "run_command"):
        assert _run_step(False, True, None, 1) == (True, True)


@pytest.fixture
def pipeline_main(monkeypatch):
    monkeypatch.setattr("sys.argv", ["run_pipeline.py"])
    monkeypatch.setattr(run_pipeline, "pin_execution_date", lambda: None)
    for name in ("_is_coordinator", "_task_index", "_task_count"):
        monkeypatch.setattr(run_pipeline, name, getattr(run_pipeline, name))
    mocks = SimpleNamespace(
        run_command=MagicMock(),
        startup=MagicMock(),
        post_crawl=MagicMock(return_value=[]),
        teardown=MagicMock(),
    )
    monkeypatch.setattr(run_pipeline, "run_command", mocks.run_command)
    monkeypatch.setattr(run_pipeline, "_execute_startup_resources", mocks.startup)
    monkeypatch.setattr(run_pipeline, "_run_post_crawl_pipeline", mocks.post_crawl)
    monkeypatch.setattr(run_pipeline, "_execute_safety_teardown", mocks.teardown)
    monkeypatch.setattr(run_pipeline, "_check_failed_slack_notifications", MagicMock())
    return mocks


def test_task_array_coordinator_main_skips_post_crawl_pipeline(pipeline_main, monkeypatch):
    monkeypatch.setattr(run_pipeline, "get_task_config", lambda: (0, 8))
    run_pipeline.main()
    pipeline_main.post_crawl.assert_not_called()
    pipeline_main.teardown.assert_called_once()
    assert pipeline_main.teardown.call_args.args[0] is True


@pytest.mark.parametrize("task_index", [0, 3])
def test_task_array_crawl_failure_exits_non_zero_after_teardown(pipeline_main, monkeypatch, task_index):
    monkeypatch.setattr(run_pipeline, "get_task_config", lambda: (task_index, 8))
    monkeypatch.setattr(run_pipeline, "_run_crawler_step", MagicMock(return_value=(False, False)))
    with pytest.raises(SystemExit) as exc:
        run_pipeline.main()
    assert exc.value.code == 1
    pipeline_main.post_crawl.assert_not_called()
    pipeline_main.teardown.assert_called_once()


def test_single_run_main_runs_post_crawl_pipeline(pipeline_main, monkeypatch):
    monkeypatch.setattr(run_pipeline, "get_task_config", lambda: (None, 1))
    run_pipeline.main()
    pipeline_main.post_crawl.assert_called_once()


def test_ml_pipeline_uses_shared_aggregator():
    assert run_ml_pipeline.aggregate_task_array_reports is pipeline_coordinator.aggregate_task_array_reports


# ---------------------------------------------------------------------------
# 基準3: ML Pipeline Job の起動・集約レポート・停止
# ---------------------------------------------------------------------------


@pytest.fixture
def ml_resources(monkeypatch):
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.delenv("PROXYSQL_INSTANCE_NAME", raising=False)
    mocks = SimpleNamespace(
        sql=MagicMock(return_value=(True, "RUNNABLE")),
        autoscaler=MagicMock(return_value=True),
        scale=MagicMock(return_value=True),
        health=MagicMock(return_value=True),
    )
    monkeypatch.setattr(run_ml_pipeline, "check_cloud_sql_status", mocks.sql)
    monkeypatch.setattr(run_ml_pipeline, "patch_proxysql_autoscaler", mocks.autoscaler)
    monkeypatch.setattr(run_ml_pipeline, "scale_proxysql_mig", mocks.scale)
    monkeypatch.setattr(run_ml_pipeline, "wait_for_proxysql_health", mocks.health)
    return mocks


def test_ml_startup_brings_up_proxysql(ml_resources):
    run_ml_pipeline.start_on_demand_resources()
    ml_resources.sql.assert_called_once()
    ml_resources.autoscaler.assert_called_once_with(min_replicas=1, max_replicas=2)
    ml_resources.scale.assert_called_once_with(target_size=1, dry_run=False)
    ml_resources.health.assert_called_once_with(timeout_sec=240)


def test_ml_startup_skips_autoscaler_for_single_instance(ml_resources, monkeypatch):
    monkeypatch.setenv("PROXYSQL_INSTANCE_NAME", "proxysql-instance-prod")
    run_ml_pipeline.start_on_demand_resources()
    ml_resources.autoscaler.assert_not_called()
    ml_resources.scale.assert_called_once_with(target_size=1, dry_run=False)


def test_ml_startup_is_noop_outside_cloud(ml_resources, monkeypatch):
    monkeypatch.delenv("IS_CLOUD", raising=False)
    run_ml_pipeline.start_on_demand_resources()
    ml_resources.sql.assert_not_called()
    ml_resources.scale.assert_not_called()


def test_ml_startup_dry_run_does_not_modify_resources(ml_resources):
    run_ml_pipeline.start_on_demand_resources(dry_run=True)
    ml_resources.autoscaler.assert_not_called()
    ml_resources.scale.assert_called_once_with(target_size=1, dry_run=True)
    ml_resources.health.assert_not_called()


@pytest.mark.parametrize(
    "failing, value",
    [
        ("sql", (False, "STOPPED")),
        ("autoscaler", False),
        ("scale", False),
        ("health", False),
    ],
)
def test_ml_startup_raises_when_resource_unavailable(ml_resources, failing, value):
    getattr(ml_resources, failing).return_value = value
    with pytest.raises(RuntimeError):
        run_ml_pipeline.start_on_demand_resources()


@pytest.fixture
def ml_main(monkeypatch):
    calls = []
    monkeypatch.setattr(run_ml_pipeline, "start_on_demand_resources", lambda dry_run=False: calls.append("startup"))
    monkeypatch.setattr(run_ml_pipeline, "run_command", lambda cmd, desc: calls.append(os.path.basename(cmd[1])))
    monkeypatch.setattr(run_ml_pipeline, "verify_barrier_completion", lambda: calls.append("barrier") or (False, ["3"]))
    monkeypatch.setattr(run_ml_pipeline, "send_aggregated_crawl_report", lambda: calls.append("report"))
    monkeypatch.setattr(run_ml_pipeline, "scale_proxysql_mig", lambda target_size, dry_run: calls.append(f"scale:{target_size}"))
    return calls


def test_ml_main_order_with_force(ml_main):
    assert run_ml_pipeline.main(argv=["--force"]) == 0
    assert ml_main == [
        "startup",
        "wait_for_db.py",
        "barrier",
        "report",
        "validate_data.py",
        "auto_heal_parsers.py",
        "train.py",
        "run_bulk_ml_evaluation.py",
        "send_recommendations.py",
        "run_daily_prediction_diagnostics.py",
        "scale:0",
    ]


def test_ml_main_aborts_on_barrier_without_force_but_reports_and_stops_proxysql(ml_main):
    assert run_ml_pipeline.main(argv=[]) == 1
    assert ml_main == ["startup", "wait_for_db.py", "barrier", "report", "scale:0"]


def test_ml_main_startup_failure_skips_steps_and_stops_proxysql(ml_main, monkeypatch):
    monkeypatch.setattr(
        run_ml_pipeline, "start_on_demand_resources",
        MagicMock(side_effect=RuntimeError("ProxySQL startup failed.")),
    )
    with pytest.raises(RuntimeError):
        run_ml_pipeline.main(argv=["--force"])
    assert ml_main == ["scale:0"]


TARGET_DATE = datetime.date(2026, 9, 29)


def _task(index, results):
    return SimpleNamespace(task_index=index, status="COMPLETED", results_json=results)


def test_aggregated_report_sent_once_for_latest_execution(monkeypatch):
    rows = [
        _task(0, [{"company": "mitsui", "property_type": "mansion", "status": "success"}]),
        _task(1, [{"company": "tokyu", "property_type": "tochi", "status": "timeout", "exit_code": -1}]),
    ]
    latest = MagicMock(return_value=rows)
    dev_slack = AsyncMock(return_value=True)
    alert_slack = AsyncMock(return_value=True)
    monkeypatch.setattr(run_ml_pipeline, "_latest_execution_tasks", latest)
    monkeypatch.setattr(run_ml_pipeline, "send_dev_report", dev_slack)
    monkeypatch.setattr(run_ml_pipeline, "send_crawling_summary_alert", alert_slack)

    assert run_ml_pipeline.send_aggregated_crawl_report(TARGET_DATE) is True

    latest.assert_called_once_with(TARGET_DATE)
    dev_slack.assert_awaited_once()
    alert_slack.assert_awaited_once()
    message = dev_slack.await_args.args[0]
    assert "全タスク集約レポート" in message
    assert "実行タスク数: 2 タスク" in message
    assert "tokyu - tochi: timeout" in message


@pytest.mark.parametrize("rows", [[], None])
def test_aggregated_report_not_sent_without_identifiable_execution(monkeypatch, rows):
    slack = AsyncMock()
    monkeypatch.setattr(run_ml_pipeline, "_latest_execution_tasks", MagicMock(return_value=rows))
    monkeypatch.setattr(run_ml_pipeline, "send_dev_report", slack)
    assert run_ml_pipeline.send_aggregated_crawl_report(TARGET_DATE) is False
    slack.assert_not_called()


def test_aggregated_report_orders_tasks_by_index(monkeypatch):
    rows = [_task(1, []), _task(0, [])]
    aggregate = MagicMock(return_value={"slack_message": "msg", "total_jobs": 89, "executed_jobs": 0, "success_jobs": 0, "failed_jobs": 0})
    monkeypatch.setattr(run_ml_pipeline, "_latest_execution_tasks", MagicMock(return_value=rows))
    monkeypatch.setattr(run_ml_pipeline, "aggregate_task_array_reports", aggregate)
    monkeypatch.setattr(run_ml_pipeline, "send_dev_report", AsyncMock(return_value=True))
    run_ml_pipeline.send_aggregated_crawl_report(TARGET_DATE)
    assert [r.task_index for r in aggregate.call_args.args[0]] == [0, 1]
    assert aggregate.call_args.kwargs == {"total_jobs": 89}


def test_aggregated_report_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(run_ml_pipeline, "_latest_execution_tasks", MagicMock(side_effect=RuntimeError("db down")))
    slack = AsyncMock()
    monkeypatch.setattr(run_ml_pipeline, "send_dev_report", slack)
    assert run_ml_pipeline.send_aggregated_crawl_report(TARGET_DATE) is False
    slack.assert_not_called()


def test_aggregated_report_returns_false_when_slack_delivery_fails(monkeypatch):
    monkeypatch.setattr(run_ml_pipeline, "_latest_execution_tasks", MagicMock(return_value=[_task(0, [])]))
    monkeypatch.setattr(run_ml_pipeline, "send_dev_report", AsyncMock(return_value=False))
    assert run_ml_pipeline.send_aggregated_crawl_report(TARGET_DATE) is False


def test_aggregated_report_slack_send_is_time_bounded(monkeypatch):
    async def never_returns(_message):
        await asyncio.sleep(3600)

    monkeypatch.setattr(run_ml_pipeline, "_latest_execution_tasks", MagicMock(return_value=[_task(0, [])]))
    monkeypatch.setattr(run_ml_pipeline, "send_dev_report", never_returns)
    monkeypatch.setattr(run_ml_pipeline, "SLACK_REPORT_TIMEOUT_SEC", 0.05)
    assert run_ml_pipeline.send_aggregated_crawl_report(TARGET_DATE) is False


def test_aggregated_report_timeout_is_finite_and_within_limit():
    assert 0 < run_ml_pipeline.SLACK_REPORT_TIMEOUT_SEC <= 10


def test_aggregator_does_not_claim_all_success_when_jobs_missing():
    aggregated = pipeline_coordinator.aggregate_task_array_reports(
        [_task(0, [{"company": "mitsui", "property_type": "mansion", "status": "success"}])], total_jobs=3
    )
    message = aggregated["slack_message"]
    assert "正常に実行・完了しました" not in message
    assert "未実行ジョブが 2 件あります" in message


def test_aggregator_skips_unsupported_records():
    aggregated = pipeline_coordinator.aggregate_task_array_reports(
        [object(), {"task_index": 1, "status": "COMPLETED", "results_json": [{"status": "success"}]}], total_jobs=1
    )
    assert aggregated["task_stats"] == [{"task_index": 1, "status": "COMPLETED", "job_count": 1}]
    assert aggregated["success_jobs"] == 1


def test_aggregator_treats_null_results_json_in_dict_as_empty():
    aggregated = pipeline_coordinator.aggregate_task_array_reports(
        [{"task_index": 0, "results_json": None}], total_jobs=89
    )
    assert aggregated["executed_jobs"] == 0
    assert aggregated["total_jobs"] == 89

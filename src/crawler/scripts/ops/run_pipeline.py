# ruff: noqa: E402, F401
import os
import sys
import subprocess
import time
import logging
import threading
import json
import argparse
import signal
import atexit
import asyncio

_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env

        break
    _cur = _parent

from package.utils.newrelic_helper import init_new_relic
init_new_relic()

import datetime
from package.utils.logging_config import configure_logging
from package.utils.task_distribution import get_task_config
from package.utils.pipeline_coordinator import wait_for_all_tasks
from package.models.crawler_task_execution import CrawlerTaskExecution
from package.utils.slack import send_crawling_summary_alert
from package.utils.gcp_resources import (
    check_cloud_sql_status,
    patch_proxysql_autoscaler,
    scale_proxysql_mig,
    wait_for_proxysql_health,
)

configure_logging()
logger = logging.getLogger(__name__)

# Global runtime state for graceful shutdown and signal handling (Issue #444)
_active_proc: subprocess.Popen | None = None
_is_coordinator: bool = False
_teardown_done: bool = False
_pipeline_start_time: float = time.time()
DEFAULT_TIMEOUT_SEC: float = 3600.0
SAFE_SHUTDOWN_BUFFER_SEC: float = 300.0


def get_remaining_pipeline_time() -> float:
    """Calculate remaining seconds before Cloud Run job timeout deadline."""
    try:
        total_limit = float(
            os.environ.get("CLOUD_RUN_JOB_TIMEOUT_SEC")
            or os.environ.get("PIPELINE_TIMEOUT_SEC")
            or DEFAULT_TIMEOUT_SEC
        )
    except (ValueError, TypeError):
        total_limit = DEFAULT_TIMEOUT_SEC
    elapsed = time.time() - _pipeline_start_time
    return max(0.0, total_limit - elapsed)


def is_deadline_approaching(buffer: float = SAFE_SHUTDOWN_BUFFER_SEC) -> bool:
    """Check if remaining execution time is below safe shutdown buffer."""
    if not os.environ.get("IS_CLOUD"):
        return False
    return get_remaining_pipeline_time() <= buffer


def check_deadline_or_raise(desc: str) -> None:
    """Raise TimeoutError if approaching deadline to trigger graceful self-teardown."""
    if is_deadline_approaching():
        rem = int(get_remaining_pipeline_time())
        logger.warning(
            f"⚠️ [Deadline Warning] Remaining time ({rem}s) is below safe shutdown buffer ({int(SAFE_SHUTDOWN_BUFFER_SEC)}s). "
            f"Aborting before Cloud Run force termination for step: '{desc}'"
        )
        raise TimeoutError(
            f"Step '{desc}' skipped: approaching Cloud Run timeout (remaining: {rem}s)"
        )


def _inline_stop_proxysql() -> None:
    """Directly scales down ProxySQL MIG/Instance and Autoscaler to 0 inline without subprocess overhead."""
    try:
        logger.info(
            "🛑 [Emergency/Inline Teardown] Scaling down ProxySQL MIG/Instance & Autoscaler to 0..."
        )
        if not os.environ.get("PROXYSQL_INSTANCE_NAME"):
            patch_proxysql_autoscaler(min_replicas=0, max_replicas=0)
        scale_proxysql_mig(target_size=0)
        logger.info(
            "✔ [Emergency/Inline Teardown] Successfully scaled down ProxySQL MIG/Instance & Autoscaler to 0."
        )
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"❌ [Emergency/Inline Teardown Error] Failed to scale down ProxySQL: {e}"
        )


def _sigterm_handler(signum: int, frame: object) -> None:
    """Handles SIGTERM / SIGINT signals (e.g. from Cloud Run timeout) to enforce teardown."""
    global _teardown_done
    logger.warning(
        f"⚠️ [Signal Received] Caught signal {signum}. Initiating emergency teardown..."
    )
    if _active_proc is not None and _active_proc.poll() is None:
        try:
            logger.info(f"Terminating active subprocess PID {_active_proc.pid}...")
            _active_proc.terminate()
            try:
                _active_proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                _active_proc.kill()
                _active_proc.wait(timeout=2.0)
        except Exception as proc_err:  # noqa: BLE001
            logger.warning(f"Error terminating active subprocess: {proc_err}")

    if _is_coordinator and os.environ.get("IS_CLOUD") and not _teardown_done:
        _inline_stop_proxysql()
        _teardown_done = True

    sys.exit(128 + signum)


def _atexit_teardown() -> None:
    """Atexit handler as the ultimate safety net for unhandled exits."""
    global _teardown_done
    if _is_coordinator and os.environ.get("IS_CLOUD") and not _teardown_done:
        logger.info("🧹 [Atexit Guard] Executing safety teardown via atexit...")
        _inline_stop_proxysql()
        _teardown_done = True


signal.signal(signal.SIGTERM, _sigterm_handler)
signal.signal(signal.SIGINT, _sigterm_handler)
atexit.register(_atexit_teardown)


def run_command(cmd, desc, timeout: float | None = None):
    global _active_proc
    check_deadline_or_raise(desc)
    if os.environ.get("IS_CLOUD"):
        budget = max(1.0, get_remaining_pipeline_time() - SAFE_SHUTDOWN_BUFFER_SEC)
        timeout = budget if timeout is None else min(timeout, budget)
    logger.info(f"=== [START] {desc} ===")
    logger.info(f"Command: {' '.join(cmd)}")
    start_time = time.time()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    _active_proc = proc

    def _reader():
        if proc.stdout is not None:
            for line in iter(proc.stdout.readline, ""):
                print(line, end="", flush=True)
            proc.stdout.close()

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()

    try:
        proc.wait(timeout=timeout)
        reader_thread.join(timeout=2.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        reader_thread.join(timeout=2.0)
        elapsed = time.time() - start_time
        logger.error(
            f"=== [TIMEOUT] {desc} timed out after {timeout}s (elapsed: {int(elapsed)}s) ==="
        )
        raise TimeoutError(f"Step '{desc}' timed out after {timeout}s")
    finally:
        _active_proc = None

    elapsed = time.time() - start_time

    if proc.returncode != 0:
        logger.error(
            f"=== [FAILED] {desc} (Exit Code: {proc.returncode}, Time: {int(elapsed)}s) ==="
        )
        raise RuntimeError(f"Step '{desc}' failed with exit code {proc.returncode}")

    logger.info(f"=== [SUCCESS] {desc} (Time: {int(elapsed)}s) ===")


BORDER_LINE = "============================================================="


def _check_failed_slack_notifications(failed_slack_file: str) -> None:
    if not os.path.exists(failed_slack_file):
        return
    with open(failed_slack_file, "r", encoding="utf-8") as f:
        failed_msgs = json.load(f)
    if failed_msgs:
        logger.critical(
            f"❌ 【深刻なエラー】 パイプライン中に送信されるべき Slack メッセージが不達となっています（計 {len(failed_msgs)} 件）。"
        )
        for m in failed_msgs:
            t = str(m.get("timestamp", "")).replace("\r", " ").replace("\n", " ")
            c = str(m.get("channel", "")).replace("\r", " ").replace("\n", " ")
            e = str(m.get("error", "")).replace("\r", " ").replace("\n", " ")
            p = str(m.get("message_preview", "")).replace("\r", " ").replace("\n", " ")
            logger.critical(
                "  - [%s] Channel: %s | Error: %s | Preview: %s", t, c, e, p
            )
        raise RuntimeError(
            "Pipeline finished but some Slack notifications were not delivered successfully."
        )


def _execute_startup_resources(is_coordinator: bool) -> None:
    if not os.environ.get("IS_CLOUD"):
        return
    if is_coordinator:
        logger.info("🔍 [Startup: Coordinator] Verifying Cloud SQL instance status...")
        csql_ok, csql_status = check_cloud_sql_status()
        if not csql_ok:
            logger.error(f"❌ [Startup Error] Cloud SQL is not RUNNABLE: {csql_status}")
            raise RuntimeError(f"Cloud SQL pre-flight check failed: {csql_status}")
        if not os.environ.get("PROXYSQL_INSTANCE_NAME"):
            logger.info(
                "🚀 [Startup: Coordinator] Restoring ProxySQL Autoscaler (min=1, max=2)..."
            )
            if not patch_proxysql_autoscaler(min_replicas=1, max_replicas=2):
                logger.error(
                    "❌ [Startup Error] Failed to restore ProxySQL Autoscaler."
                )
                raise RuntimeError("ProxySQL Autoscaler restore failed.")
        logger.info("🚀 [Startup: Coordinator] Scaling ProxySQL (0 -> 1)...")
        success = scale_proxysql_mig(target_size=1)
        if not success:
            logger.error("❌ [Startup Error] Failed to scale ProxySQL to 1.")
            raise RuntimeError("ProxySQL startup failed.")
    else:
        logger.info(
            "⏳ [Startup: Worker] Waiting for Coordinator to bring up ProxySQL MIG..."
        )

    logger.info("⏳ [Startup] Verifying ProxySQL port health (startup check)...")
    healthy = wait_for_proxysql_health(timeout_sec=240)
    if not healthy:
        logger.error("❌ [Startup Error] ProxySQL port health check timed out.")
        raise RuntimeError("ProxySQL health check timed out during startup.")
    logger.info("✔ [Startup] ProxySQL MIG is healthy and operational!")


def _execute_safety_teardown(is_coordinator: bool, scripts_dir: str) -> None:
    global _teardown_done
    if is_coordinator and os.environ.get("IS_CLOUD"):
        try:
            logger.info(
                "🧹 [Cleanup] Running safety teardown to ensure GCP resources (ProxySQL MIG) are stopped..."
            )
            # 1. Inline fast scale-down first to guarantee immediate scale-down within tight timeouts
            _inline_stop_proxysql()
            _teardown_done = True
            # 2. Comprehensive check and notification via ensure_resources_stopped
            run_command(
                [
                    sys.executable,
                    os.path.join(scripts_dir, "ensure_resources_stopped.py"),
                ],
                "Teardown: Ensure On-Demand Resources Stopped",
                timeout=60,
            )
        except Exception as cleanup_err:  # noqa: BLE001
            logger.warning(
                f"⚠️ [Cleanup Warning] Failed to stop resources in teardown: {cleanup_err}"
            )


def aggregate_task_array_reports(task_records: list, total_jobs: int = 89) -> dict:
    """
    Aggregates results_json from all CrawlerTaskExecution records.
    Handles both model instances and plain dictionaries.
    """
    all_results = []
    task_stats = []
    for rec in task_records:
        if hasattr(rec, "results_json"):
            results = rec.results_json or []
            task_idx = getattr(rec, "task_index", None)
            status = getattr(rec, "status", "UNKNOWN")
        elif isinstance(rec, dict):
            results = rec.get("results_json", [])
            task_idx = rec.get("task_index")
            status = rec.get("status", "UNKNOWN")
        else:
            continue
        all_results.extend(results)
        task_stats.append(
            {
                "task_index": task_idx,
                "status": status,
                "job_count": len(results),
            }
        )

    success_jobs = sum(1 for r in all_results if r.get("status") == "success")
    failed_list = [
        r for r in all_results if r.get("status") in ["failed", "timeout", "error"]
    ]
    failed_jobs = len(failed_list)
    executed_jobs = len(all_results)
    missing_jobs = max(0, total_jobs - executed_jobs)

    msg_lines = ["📢 【クローリング全タスク集約レポート】"]
    msg_lines.append(f"実行タスク数: {len(task_records)} タスク")
    msg_lines.append(
        f"総ジョブ数: {total_jobs} (実行完了: {executed_jobs}, 成功: {success_jobs}, 失敗: {failed_jobs}{f', 未実行: {missing_jobs}' if missing_jobs > 0 else ''})"
    )

    if failed_list:
        msg_lines.append("\n⚠️ 異常・失敗が発生したクローラー:")
        for f in failed_list:
            company = f.get("company", "unknown")
            ptype = f.get("property_type", "unknown")
            status = f.get("status", "failed")
            code = f.get("exit_code", "?")
            dur = f.get("duration", "")
            dur_str = f", 所要: {dur}" if dur else ""
            msg_lines.append(f"• {company} - {ptype}: {status} (Code: {code}{dur_str})")
    else:
        msg_lines.append(f"\n✅ 全 {executed_jobs} ジョブが正常に実行・完了しました。")

    slack_message = "\n".join(msg_lines)

    return {
        "total_jobs": total_jobs,
        "executed_jobs": executed_jobs,
        "success_jobs": success_jobs,
        "failed_jobs": failed_jobs,
        "missing_jobs": missing_jobs,
        "all_results": all_results,
        "failed_list": failed_list,
        "task_stats": task_stats,
        "slack_message": slack_message,
    }


def _run_crawler_step(
    is_task_array: bool,
    is_coordinator: bool,
    task_index: int | None,
    task_count: int,
    ops_dir: str,
    skip_portals: bool,
) -> tuple[bool, bool]:
    crawl_cmd = [sys.executable, os.path.join(ops_dir, "run_all_crawlers.py")]
    if skip_portals:
        crawl_cmd.append("--skip-portals")
    step1_title = f"Step 1/6: Parallel Crawling{' [Task ' + str(task_index) + '/' + str(task_count) + ']' if is_task_array else ''}{' [Skip Portals]' if skip_portals else ''}"
    crawler_ok = True
    try:
        run_command(crawl_cmd, step1_title)
    except TimeoutError:
        logger.error("❌ [Step 1/6 Deadline/Timeout] Crawling timed out or reached deadline. Re-raising to trigger safe teardown.")
        raise
    except Exception as crawl_err:
        crawler_ok = False
        logger.error(
            f"❌ [Step 1/6 Failure] Parallel Crawling encountered an error: {crawl_err}. "
            "Proceeding with post-crawl pipeline (validation, evaluation, and recommendation)..."
        )

    if is_task_array and not is_coordinator:
        logger.info(
            f"✔ [Worker] Task {task_index}/{task_count} のクローリングが完了しました。コンテナを終了します。"
        )
        return False, crawler_ok

    if is_task_array and is_coordinator:
        logger.info(
            f"⏳ [Coordinator] 他全タスクのクローリング完了を待機します (全 {task_count} タスク)..."
        )
        remaining = get_remaining_pipeline_time()
        # Bound task waiting by remaining time minus safe shutdown buffer and polling interval
        wait_interval = 15
        wait_timeout = max(
            0,
            int(
                min(
                    10800 - wait_interval,
                    remaining - SAFE_SHUTDOWN_BUFFER_SEC - wait_interval,
                )
            ),
        )
        logger.info(
            f"⏳ [Coordinator] wait_for_all_tasks timeout bounded to {wait_timeout}s (remaining pipeline time: {int(remaining)}s)..."
        )
        all_ok, failed_tasks = wait_for_all_tasks(
            model=CrawlerTaskExecution,
            execution_date=datetime.datetime.now(datetime.timezone.utc).date(),
            task_count=task_count,
            timeout_sec=wait_timeout,
            interval_sec=wait_interval,
        )
        if not all_ok:
            crawler_ok = False
            logger.warning(
                f"⚠️ 一部タスクが未完了または失敗しています (失敗タスク番号: {failed_tasks})。完了分で後続パイプラインを続行します。"
            )

        # 全タスク集約レポートの生成 & Slack通知 (Issue #445)
        try:
            today = datetime.datetime.now(datetime.timezone.utc).date()
            records = list(
                CrawlerTaskExecution.objects.filter(execution_date=today).order_by(
                    "task_index"
                )
            )
            aggregated = aggregate_task_array_reports(records, total_jobs=89)
            logger.info(
                f"📊 [Coordinator Aggregation] Tasks: {len(records)}, Total: {aggregated['total_jobs']}, "
                f"Executed: {aggregated['executed_jobs']}, Success: {aggregated['success_jobs']}, Failed: {aggregated['failed_jobs']}"
            )
            if aggregated.get("slack_message"):
                asyncio.run(send_crawling_summary_alert(aggregated["slack_message"]))
        except Exception as agg_err:
            logger.warning(
                f"⚠️ [Aggregation Warning] Failed to aggregate task array reports: {agg_err}"
            )
    return True, crawler_ok


def _run_post_crawl_pipeline(
    crawler_dir: str,
    ops_dir: str,
    maintenance_dir: str,
    debug_tools_dir: str,
    skip_portals: bool,
) -> list[str]:
    failed_steps = []

    # Step 1.5 (2/6): 不正データ自動検証 & クレンジング & HTMLエラー監視
    try:
        run_command(
            [
                sys.executable,
                os.path.join(maintenance_dir, "validate_data.py"),
            ],
            "Step 2/6: Scraping Data Validation & Automated Cleansing",
        )
    except Exception as e:
        failed_steps.append("Step 2/6: Scraping Data Validation & Automated Cleansing")
        logger.error(f"❌ [Step 2/6 Error] Data validation step failed: {e}")

    # AI自己修復用のバグ指示書生成
    try:
        run_command(
            [
                sys.executable,
                os.path.join(debug_tools_dir, "auto_heal_parsers.py"),
            ],
            "Step 2.5/6: Auto-Heal Instruction Generation for AI Agent",
        )
    except Exception as e:
        failed_steps.append("Step 2.5/6: Auto-Heal Instruction Generation for AI Agent")
        logger.error(f"❌ [Step 2.5/6 Error] Auto-heal instruction generation failed: {e}")

    # Step 2 (3/6): 最新データによるMLモデル再学習 (失敗時も価格推定を継続)
    try:
        run_command(
            [
                sys.executable,
                os.path.join(crawler_dir, "package", "ml", "train.py"),
            ],
            "Step 3/6: ML Model Re-Training (LightGBM, XGBoost, CatBoost, RandomForest)",
        )
    except Exception as e:
        failed_steps.append("Step 3/6: ML Model Re-Training")
        logger.error(
            f"❌ [Step 3/6 Error] ML Re-training failed: {e}. "
            "Continuing with existing models for evaluation and recommendations."
        )

    # Step 3 (4/6): 一括価格予測・投資シミュレーション評価のDB更新 (バルクML推論)
    try:
        eval_cmd = [sys.executable, os.path.join(ops_dir, "run_bulk_ml_evaluation.py")]
        if skip_portals:
            eval_cmd.append("--skip-portals")
        run_command(
            eval_cmd,
            f"Step 4/6: Batch Estimation & Investment Evaluation{' [Skip Portals]' if skip_portals else ''}",
        )
    except Exception as e:
        failed_steps.append("Step 4/6: Batch Estimation & Investment Evaluation")
        logger.error(f"❌ [Step 4/6 Error] Batch Estimation & Investment Evaluation failed: {e}")

    # Step 4 (5/6): お宝物件のスクリーニング & Slack通知
    try:
        run_command(
            [
                sys.executable,
                os.path.join(ops_dir, "send_recommendations.py"),
            ],
            "Step 5/6: Slack Notification (Hot Property Recommendation)",
        )
    except Exception as e:
        failed_steps.append("Step 5/6: Slack Notification")
        logger.error(f"❌ [Step 5/6 Error] Slack recommendation sending failed: {e}")

    # Step 5 (6/6): 日次予測精度診断 & AIインサイト分析
    try:
        run_command(
            [
                sys.executable,
                os.path.join(ops_dir, "run_daily_prediction_diagnostics.py"),
                "--notify",
            ],
            "Step 6/6: Daily ML Prediction Diagnostics & AI Insights",
        )
    except Exception as e:
        failed_steps.append("Step 6/6: Daily ML Prediction Diagnostics")
        logger.error(f"❌ [Step 6/6 Error] Daily ML Prediction Diagnostics failed: {e}")

    return failed_steps


def main():
    parser = argparse.ArgumentParser(description="Real Estate Pipeline")
    parser.add_argument(
        "--skip-portals",
        action="store_true",
        help="Skip large portal sites (homes, athome)",
    )
    args = parser.parse_args()

    global _is_coordinator
    task_index, task_count = get_task_config()
    is_task_array = task_count > 1 and task_index is not None
    is_coordinator = not is_task_array or task_index == 0
    _is_coordinator = is_coordinator

    logger.info(BORDER_LINE)
    logger.info(
        f"Starting REALESTATE CRAWLER & ML ESTIMATION PIPELINE (skip_portals={args.skip_portals})"
    )
    if is_task_array:
        logger.info(
            f"🎯 [Task Array Mode] Task {task_index}/{task_count} (Role: {'Coordinator' if is_coordinator else 'Worker'})"
        )
    logger.info(BORDER_LINE)

    current_dir = os.path.dirname(os.path.abspath(__file__))  # .../scripts/ops
    scripts_dir = os.path.dirname(current_dir)  # .../scripts
    crawler_dir = os.path.dirname(scripts_dir)  # .../crawler

    debug_tools_dir = os.path.join(scripts_dir, "debug_tools")
    maintenance_dir = os.path.join(scripts_dir, "maintenance")
    ops_dir = current_dir

    failed_slack_file = os.path.join(crawler_dir, "failed_slack_notifications.json")
    if os.path.exists(failed_slack_file):
        try:
            os.remove(failed_slack_file)
        except OSError:
            pass

    try:
        # Step 0: Slack Connection Pre-flight Check
        run_command(
            [
                sys.executable,
                os.path.join(debug_tools_dir, "check_slack_connection.py"),
            ],
            "Step 0/6: Slack Connection Pre-flight Check",
        )

        # Step 0.2: Start On-Demand Resources & Health Check (Coordinator in Cloud)
        _execute_startup_resources(is_coordinator)

        # Step 0.4: Database Readiness Pre-flight Check
        run_command(
            [
                sys.executable,
                os.path.join(debug_tools_dir, "wait_for_db.py"),
            ],
            "Step 0.4/6: Database Readiness Pre-flight Check",
        )

        # Step 0.5: Database Schema Migration
        if is_coordinator:
            run_command(
                [
                    sys.executable,
                    os.path.join(crawler_dir, "manage.py"),
                    "migrate",
                    "--noinput",
                ],
                "Step 0.5/6: Database Schema Migration (Coordinator)",
            )
        else:
            logger.info(
                "⏳ [Worker] Coordinator による DB マイグレーション完了を待機中 (10秒)..."
            )
            time.sleep(10)

        should_continue, crawler_ok = _run_crawler_step(
            is_task_array,
            is_coordinator,
            task_index,
            task_count,
            ops_dir,
            args.skip_portals,
        )
        if not should_continue:
            return

        failed_steps = _run_post_crawl_pipeline(
            crawler_dir, ops_dir, maintenance_dir, debug_tools_dir, args.skip_portals
        )
        _check_failed_slack_notifications(failed_slack_file)

        if not crawler_ok:
            failed_steps.insert(0, "Step 1/6: Parallel Crawling")

        if failed_steps:
            logger.error(
                f"❌ Pipeline finished with partial failures in steps: {', '.join(failed_steps)}"
            )
            sys.exit(1)

        logger.info(BORDER_LINE)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY! All steps finished.")
        logger.info(BORDER_LINE)
    except Exception:
        logger.exception("Pipeline crashed due to unhandled exception")
        sys.exit(1)
    finally:
        _execute_safety_teardown(is_coordinator, scripts_dir)


if __name__ == "__main__":
    main()

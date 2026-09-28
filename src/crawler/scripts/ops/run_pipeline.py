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

from django.db import close_old_connections, connection
from package.utils.db_timeouts import bound_mysql_timeouts
from package.utils.logging_config import configure_logging
from package.utils.task_distribution import (
    get_execution_date,
    get_execution_id,
    get_task_config,
    pin_execution_date,
)
from package.models.crawler_task_execution import CrawlerTaskExecution
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
_task_index: int | None = None
_task_count: int = 1
_teardown_done: bool = False
_pipeline_start_time: float = time.time()
DEFAULT_TIMEOUT_SEC: float = 3600.0
SAFE_SHUTDOWN_BUFFER_SEC: float = 300.0
TASK_RECONCILE_MAX_ATTEMPTS: int = 4
TASK_RECONCILE_INTERVAL_SEC: float = 15.0


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


def _inline_stop_proxysql() -> bool:
    """Directly scales down ProxySQL MIG/Instance and Autoscaler to 0 inline without subprocess overhead."""
    try:
        logger.info(
            "🛑 [Emergency/Inline Teardown] Scaling down ProxySQL MIG/Instance & Autoscaler to 0..."
        )
        autoscaler_ok = True
        if not os.environ.get("PROXYSQL_INSTANCE_NAME"):
            autoscaler_ok = bool(patch_proxysql_autoscaler(min_replicas=0, max_replicas=0))
        mig_ok = bool(scale_proxysql_mig(target_size=0))
        if not (autoscaler_ok and mig_ok):
            logger.error(
                f"❌ [Emergency/Inline Teardown Error] ProxySQL scale-down incomplete "
                f"(autoscaler_ok={autoscaler_ok}, mig_ok={mig_ok})"
            )
            return False
        logger.info(
            "✔ [Emergency/Inline Teardown] Successfully scaled down ProxySQL MIG/Instance & Autoscaler to 0."
        )
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"❌ [Emergency/Inline Teardown Error] Failed to scale down ProxySQL: {e}"
        )
        return False


def _current_execution_filters() -> dict:
    """main() 起動時に pin_execution_date() で固定した実行日 (子プロセスへ CRAWLER_EXECUTION_DATE で継承) と実行 ID で今回の実行のタスク行を特定する"""
    return {"execution_date": get_execution_date(), "execution_id": get_execution_id()}


def _bind_parent_db_timeouts() -> None:
    """親プロセスの ORM 接続に有限タイムアウトを適用する (確立済みの接続は閉じ、次回クエリで設定付きで再接続させる)"""
    bound_mysql_timeouts(getattr(connection, "settings_dict", None))
    if getattr(connection, "connection", None) is not None:
        connection.close()


def _can_stop_shared_proxysql() -> bool:
    """タスクアレイでは他タスクが全て終端状態の場合のみ共有 ProxySQL を停止できる (未確定時は Safety-Net に委譲)"""
    if _task_count <= 1:
        return True
    if _task_index is None:
        logger.warning(
            "⚠️ [Teardown Guard] タスク番号 (CLOUD_RUN_TASK_INDEX) が無く自タスクを特定できないため ProxySQL 停止をスキップし Safety-Net に委譲します"
        )
        return False
    execution_filters = _current_execution_filters()
    if not execution_filters["execution_id"]:
        logger.warning(
            "⚠️ [Teardown Guard] 実行 ID (CLOUD_RUN_EXECUTION) が無く今回の実行のタスク行を特定できないため ProxySQL 停止をスキップし Safety-Net に委譲します"
        )
        return False
    try:
        _bind_parent_db_timeouts()
        records = list(CrawlerTaskExecution.objects.filter(**execution_filters))
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"⚠️ [Teardown Guard] タスク状態を取得できないため ProxySQL 停止をスキップし Safety-Net に委譲します: {e}"
        )
        return False
    status_map = {r.task_index: r.status for r in records}
    pending = [
        idx
        for idx in range(_task_count)
        if idx != _task_index and status_map.get(idx) not in ("COMPLETED", "FAILED")
    ]
    if pending:
        logger.warning(
            f"⚠️ [Teardown Guard] 未完了タスク {pending} が存在するため ProxySQL 停止をスキップし Safety-Net に委譲します"
        )
        return False
    return True


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
        if _can_stop_shared_proxysql() and _inline_stop_proxysql():
            _teardown_done = True

    sys.exit(128 + signum)


def _atexit_teardown() -> None:
    """Atexit handler as the ultimate safety net for unhandled exits."""
    global _teardown_done
    if _is_coordinator and os.environ.get("IS_CLOUD") and not _teardown_done:
        logger.info("🧹 [Atexit Guard] Executing safety teardown via atexit...")
        if _can_stop_shared_proxysql() and _inline_stop_proxysql():
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
            if not _can_stop_shared_proxysql():
                logger.warning(
                    "⚠️ [Cleanup] 他タスクが稼働中のため共有 ProxySQL の停止をスキップしました。"
                    "停止は Safety-Net (realestate-safety-net, 17-21 UTC 毎時) が実行終了後に行います。"
                )
                return
            # 1. Inline fast scale-down first to guarantee immediate scale-down within tight timeouts
            if _inline_stop_proxysql():
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


def reconcile_aborted_task_execution(task_index: int | None) -> bool:
    """失敗終了したクローラーの RUNNING 行を DB 復旧後に FAILED へ更新し、バリアが終端状態と判定できるようにする"""
    # 子プロセスの bound_db_connect_timeout() は親プロセスの接続に及ばないため、update() の無期限ブロックを防ぐ
    bound_mysql_timeouts(getattr(connection, "settings_dict", None))
    for attempt in range(1, TASK_RECONCILE_MAX_ATTEMPTS + 1):
        # 再同期の待機は run_command() のタイムアウト対象外のため、安全停止の猶予を消費しないよう打ち切る
        if is_deadline_approaching():
            break
        # DB 不通で切断された接続を再利用すると復旧後も失敗し続けるため、試行ごとに破棄する
        close_old_connections()
        try:
            # run_all_crawlers.py と同じ execution_date (ローカル日付) / task_index で自タスクの行のみを対象とする
            updated = CrawlerTaskExecution.objects.filter(
                **_current_execution_filters(),
                task_index=task_index or 0,
                status="RUNNING",
            ).update(status="FAILED")
        except Exception as e:
            logger.warning(
                f"⚠️ CrawlerTaskExecution (task {task_index or 0}) の FAILED 再同期に失敗 "
                f"({attempt}/{TASK_RECONCILE_MAX_ATTEMPTS}): {e}"
            )
            if attempt < TASK_RECONCILE_MAX_ATTEMPTS:
                if is_deadline_approaching(SAFE_SHUTDOWN_BUFFER_SEC + TASK_RECONCILE_INTERVAL_SEC):
                    break
                time.sleep(TASK_RECONCILE_INTERVAL_SEC)
            continue
        if updated:
            logger.info(f"✔ RUNNING のまま残った CrawlerTaskExecution (task {task_index or 0}) を FAILED に再同期しました")
        return True
    return False


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
        reconcile_aborted_task_execution(task_index)

    if is_task_array:
        logger.info(
            f"✔ [{'Coordinator' if is_coordinator else 'Worker'}] Task {task_index}/{task_count} のクローリングが完了しました。"
            "集約レポート・学習・価格推定は ML Pipeline Job が実行します。コンテナを終了します。"
        )
        return False, crawler_ok

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
    pin_execution_date()

    global _is_coordinator, _task_index, _task_count
    task_index, task_count = get_task_config()
    is_task_array = task_count > 1 and task_index is not None
    is_coordinator = not is_task_array or task_index == 0
    _is_coordinator = is_coordinator
    _task_index = task_index
    _task_count = task_count

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

# ruff: noqa: E402, F401
# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import time
import logging
import threading
import json
import argparse

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

import datetime
from package.utils.logging_config import configure_logging
from package.utils.task_distribution import get_task_config
from package.utils.pipeline_coordinator import wait_for_all_tasks
from package.models.crawler_task_execution import CrawlerTaskExecution
configure_logging()
logger = logging.getLogger(__name__)

def run_command(cmd, desc, timeout: float | None = None):
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
        bufsize=1
    )
    
    def _reader():
        if proc.stdout is not None:
            for line in iter(proc.stdout.readline, ''):
                print(line, end='', flush=True)
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
        logger.error(f"=== [TIMEOUT] {desc} timed out after {timeout}s (elapsed: {int(elapsed)}s) ===")
        raise TimeoutError(f"Step '{desc}' timed out after {timeout}s")

    elapsed = time.time() - start_time
    
    if proc.returncode != 0:
        logger.error(f"=== [FAILED] {desc} (Exit Code: {proc.returncode}, Time: {int(elapsed)}s) ===")
        raise RuntimeError(f"Step '{desc}' failed with exit code {proc.returncode}")
        
    logger.info(f"=== [SUCCESS] {desc} (Time: {int(elapsed)}s) ===")


def _check_failed_slack_notifications(failed_slack_file: str) -> None:
    if not os.path.exists(failed_slack_file):
        return
    with open(failed_slack_file, "r", encoding="utf-8") as f:
        failed_msgs = json.load(f)
    if failed_msgs:
        logger.critical(f"❌ 【深刻なエラー】 パイプライン中に送信されるべき Slack メッセージが不達となっています（計 {len(failed_msgs)} 件）。")
        for m in failed_msgs:
            logger.critical(f"  - [{m['timestamp']}] Channel: {m['channel']} | Error: {m['error']} | Preview: {m['message_preview']}")
        raise RuntimeError("Pipeline finished but some Slack notifications were not delivered successfully.")


def _execute_safety_teardown(is_coordinator: bool, scripts_dir: str) -> None:
    if is_coordinator and os.environ.get("IS_CLOUD"):
        try:
            logger.info("🧹 [Cleanup] Running safety teardown to ensure GCP resources (ProxySQL MIG) are stopped...")
            run_command([
                sys.executable,
                os.path.join(scripts_dir, "ensure_resources_stopped.py"),
            ], "Teardown: Ensure On-Demand Resources Stopped", timeout=60)
        except Exception as cleanup_err:  # noqa: BLE001
            logger.warning(f"⚠️ [Cleanup Warning] Failed to stop resources in teardown: {cleanup_err}")


def _run_crawler_step(
    is_task_array: bool,
    is_coordinator: bool,
    task_index: int | None,
    task_count: int,
    ops_dir: str,
    skip_portals: bool,
) -> bool:
    crawl_cmd = [sys.executable, os.path.join(ops_dir, "run_all_crawlers.py")]
    if skip_portals:
        crawl_cmd.append("--skip-portals")
    step1_title = f"Step 1/6: Parallel Crawling{' [Task ' + str(task_index) + '/' + str(task_count) + ']' if is_task_array else ''}{' [Skip Portals]' if skip_portals else ''}"
    run_command(crawl_cmd, step1_title)

    if is_task_array and not is_coordinator:
        logger.info(f"✔ [Worker] Task {task_index}/{task_count} のクローリングが完了しました。コンテナを終了します。")
        return False

    if is_task_array and is_coordinator:
        logger.info(f"⏳ [Coordinator] 他全タスクのクローリング完了を待機します (全 {task_count} タスク)...")
        all_ok, failed_tasks = wait_for_all_tasks(
            model=CrawlerTaskExecution,
            execution_date=datetime.datetime.now(datetime.timezone.utc).date(),
            task_count=task_count,
            timeout_sec=10800,
            interval_sec=15,
        )
        if not all_ok:
            logger.warning(f"⚠️ 一部タスクが未完了または失敗しています (失敗タスク番号: {failed_tasks})。完了分で後続パイプラインを続行します。")
    return True


def _run_post_crawl_pipeline(
    crawler_dir: str,
    ops_dir: str,
    maintenance_dir: str,
    debug_tools_dir: str,
    skip_portals: bool,
) -> None:
    # Step 1.5 (2/6): 不正データ自動検証 & クレンジング & HTMLエラー監視
    run_command([
        sys.executable,
        os.path.join(maintenance_dir, "validate_data.py"),
    ], "Step 2/6: Scraping Data Validation & Automated Cleansing")

    # AI自己修復用のバグ指示書生成
    run_command([
        sys.executable,
        os.path.join(debug_tools_dir, "auto_heal_parsers.py"),
    ], "Step 2.5/6: Auto-Heal Instruction Generation for AI Agent")

    # Step 2 (3/6): 最新データによるMLモデル再学習
    run_command([
        sys.executable,
        os.path.join(crawler_dir, "package", "ml", "train.py"),
    ], "Step 3/6: ML Model Re-Training (LightGBM, XGBoost, CatBoost, RandomForest)")

    # Step 3 (4/6): 一括価格予測・投資シミュレーション評価のDB更新 (バルクML推論)
    eval_cmd = [sys.executable, os.path.join(ops_dir, "run_bulk_ml_evaluation.py")]
    if skip_portals:
        eval_cmd.append("--skip-portals")
    run_command(eval_cmd, f"Step 4/6: Batch Estimation & Investment Evaluation{' [Skip Portals]' if skip_portals else ''}")

    # Step 4 (5/6): お宝物件のスクリーニング & Slack通知
    run_command([
        sys.executable,
        os.path.join(ops_dir, "send_recommendations.py"),
    ], "Step 5/6: Slack Notification (Hot Property Recommendation)")

    # Step 5 (6/6): 日次予測精度診断 & AIインサイト分析
    run_command([
        sys.executable,
        os.path.join(ops_dir, "run_daily_prediction_diagnostics.py"),
        "--notify",
    ], "Step 6/6: Daily ML Prediction Diagnostics & AI Insights")


def main():
    parser = argparse.ArgumentParser(description="Real Estate Pipeline")
    parser.add_argument("--skip-portals", action="store_true", help="Skip large portal sites (homes, athome)")
    args = parser.parse_args()

    task_index, task_count = get_task_config()
    is_task_array = task_count > 1 and task_index is not None
    is_coordinator = not is_task_array or task_index == 0

    logger.info("=============================================================")
    logger.info(f"Starting REALESTATE CRAWLER & ML ESTIMATION PIPELINE (skip_portals={args.skip_portals})")
    if is_task_array:
        logger.info(f"🎯 [Task Array Mode] Task {task_index}/{task_count} (Role: {'Coordinator' if is_coordinator else 'Worker'})")
    logger.info("=============================================================")

    current_dir = os.path.dirname(os.path.abspath(__file__))  # .../scripts/ops
    scripts_dir = os.path.dirname(current_dir)               # .../scripts
    crawler_dir = os.path.dirname(scripts_dir)               # .../crawler

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
        run_command([
            sys.executable,
            os.path.join(debug_tools_dir, "check_slack_connection.py"),
        ], "Step 0/6: Slack Connection Pre-flight Check")

        # Step 0.4: Database Readiness Pre-flight Check
        run_command([
            sys.executable,
            os.path.join(debug_tools_dir, "wait_for_db.py"),
        ], "Step 0.4/6: Database Readiness Pre-flight Check")

        # Step 0.5: Database Schema Migration
        if is_coordinator:
            run_command([
                sys.executable,
                os.path.join(crawler_dir, "manage.py"),
                "migrate",
                "--noinput",
            ], "Step 0.5/6: Database Schema Migration (Coordinator)")
        else:
            logger.info("⏳ [Worker] Coordinator による DB マイグレーション完了を待機中 (10秒)...")
            time.sleep(10)

        should_continue = _run_crawler_step(
            is_task_array, is_coordinator, task_index, task_count, ops_dir, args.skip_portals
        )
        if not should_continue:
            return

        _run_post_crawl_pipeline(
            crawler_dir, ops_dir, maintenance_dir, debug_tools_dir, args.skip_portals
        )
        _check_failed_slack_notifications(failed_slack_file)

        logger.info("=============================================================")
        logger.info("PIPELINE COMPLETED SUCCESSFULLY! All steps finished.")
        logger.info("=============================================================")
    except Exception as e:
        logger.error(f"Pipeline crashed due to unhandled exception: {e}")
        sys.exit(1)
    finally:
        _execute_safety_teardown(is_coordinator, scripts_dir)


if __name__ == "__main__":
    main()

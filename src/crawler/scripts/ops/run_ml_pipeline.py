# ruff: noqa: E402, F401
"""
Cloud Run ML Pipeline Job (クローラージョブ終了後に Cloud Scheduler から日次 1 回起動):
0. Cloud SQL 稼働確認・ProxySQL 起動・疎通確認・DB 待機
1. クローラータスク完了確認 (Barrier Check) & 全タスク集約レポート Slack 送信
2. 不正データ検証 & クレンジング (validate_data.py)
3. MLモデル再学習 (package/ml/train.py)
4. バルクML価格推定・投資評価 (run_bulk_ml_evaluation.py)
5. お宝物件レコメンド Slack 通知 (send_recommendations.py)
6. 日次予測精度診断 (run_daily_prediction_diagnostics.py)
7. finally ブロックで ProxySQL MIG を確実に停止 (size: 1 -> 0)
"""
import os
import sys
import time
import asyncio
import logging
import argparse
import datetime
import subprocess

_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env  # noqa: F401
        break
    _cur = _parent

from package.utils.logging_config import configure_logging
from package.models.crawler_task_execution import CrawlerTaskExecution
from package.utils.task_distribution import STANDALONE_EXECUTION_PREFIX
from package.utils.pipeline_coordinator import aggregate_task_array_reports
from package.utils.slack import send_crawling_summary_alert
from package.utils.gcp_resources import (
    check_cloud_sql_status,
    patch_proxysql_autoscaler,
    wait_for_proxysql_health,
    scale_proxysql_mig as _gcp_scale_proxysql_mig,
    get_gcp_access_token as _get_gcp_access_token,
)

try:
    from google.cloud import compute_v1
except ImportError:
    compute_v1 = None

configure_logging()
logger = logging.getLogger(__name__)


SEPARATOR = "============================================================="
SLACK_REPORT_TIMEOUT_SEC = 10  # NFR-021: 外部 API 呼び出しの有限タイムアウト上限


def scale_proxysql_mig(target_size: int = 0, project_id: str | None = None, region: str | None = None, mig_name: str | None = None, dry_run: bool = False) -> bool:
    """ProxySQL MIG のサイズを変更 (バッチ終了時の停止 size: 1 -> 0)"""
    token_fn = getattr(sys.modules[__name__], "_get_gcp_access_token", _get_gcp_access_token)
    comp_mod = getattr(sys.modules[__name__], "compute_v1", compute_v1)
    return _gcp_scale_proxysql_mig(
        target_size=target_size,
        project_id=project_id,
        region=region,
        mig_name=mig_name,
        dry_run=dry_run,
        compute_module=comp_mod,
        get_token_callback=token_fn,
    )


def start_on_demand_resources(dry_run: bool = False) -> None:
    """クローラージョブ終了時に停止された Cloud SQL 経路 (ProxySQL) を起動し、疎通を確認する"""
    if not os.environ.get("IS_CLOUD"):
        return
    ok, status = check_cloud_sql_status()
    if not ok:
        raise RuntimeError(f"Cloud SQL pre-flight check failed: {status}")
    if not os.environ.get("PROXYSQL_INSTANCE_NAME") and not dry_run:
        logger.info("🚀 [Startup] Restoring ProxySQL Autoscaler (min=1, max=2)...")
        if not patch_proxysql_autoscaler(min_replicas=1, max_replicas=2):
            raise RuntimeError("ProxySQL Autoscaler restore failed.")
    logger.info("🚀 [Startup] Scaling ProxySQL (0 -> 1)...")
    if not scale_proxysql_mig(target_size=1, dry_run=dry_run):
        raise RuntimeError("ProxySQL startup failed.")
    if dry_run:
        return
    if not wait_for_proxysql_health(timeout_sec=240):
        raise RuntimeError("ProxySQL health check timed out during startup.")
    logger.info("✔ [Startup] ProxySQL is healthy and operational!")


def _latest_execution_tasks(target_date: datetime.date) -> list | None:
    """対象日で開始 (最初のタスク行登録) が最も新しいクローラー実行のタスク行を返す。

    空の実行 ID の行 (別実行同士で上書きされ得る) と単独実行 cloud-tasks-* の行 (日次クロール全体を表さない) は
    評価対象外とし、行が存在するのに識別可能な実行が無い場合は None を返す。
    """
    rows = list(CrawlerTaskExecution.objects.filter(execution_date=target_date))
    by_execution: dict[str, list] = {}
    for row in rows:
        if row.execution_id and not row.execution_id.startswith(STANDALONE_EXECUTION_PREFIX):
            by_execution.setdefault(row.execution_id, []).append(row)
    if not by_execution:
        return None if rows else []
    latest_id = max(by_execution, key=lambda k: min(r.created_at for r in by_execution[k]))
    return by_execution[latest_id]


def verify_barrier_completion(execution_date: datetime.date | None = None, min_success_ratio: float = 0.85) -> tuple[bool, list[str]]:
    """DB のタスク状況を点検し、ML 実行基準を満たしているか検証"""
    target_date = execution_date or datetime.datetime.now(datetime.timezone.utc).date()
    try:
        tasks = _latest_execution_tasks(target_date)
        if tasks is None:
            logger.warning(f"Task records for {target_date} have no identifiable execution_id. Cannot verify barrier.")
            return False, []
        if not tasks:
            logger.warning(f"No task records found for {target_date}. Proceeding with existing DB data.")
            return True, []

        total = max(t.task_count for t in tasks)
        if total <= 0:
            logger.warning(f"Invalid task_count={total} for the latest execution on {target_date}.")
            return False, []
        missing = set(range(total)) - {t.task_index for t in tasks}
        failed_indexes = {t.task_index for t in tasks if t.status in ("FAILED", "PENDING")} | missing
        failed = [str(i) for i in sorted(failed_indexes)]
        if missing:
            logger.warning(f"Task registrations missing for indexes {sorted(missing)} (task_count={total}).")
            return False, failed

        completed = [t for t in tasks if t.status == "COMPLETED"]
        success_ratio = len(completed) / total
        logger.info(f"Barrier verification: {len(completed)}/{total} tasks completed (ratio: {success_ratio:.2%}).")

        if success_ratio >= min_success_ratio:
            return True, failed
        else:
            logger.warning(f"Completion ratio {success_ratio:.2%} is below threshold {min_success_ratio:.2%}.")
            return False, failed
    except Exception as e:
        logger.warning(f"Could not verify task status in DB: {e}. Proceeding.")
        return True, []


def send_aggregated_crawl_report(execution_date: datetime.date | None = None) -> bool:
    """最新クローラー実行の全タスク結果を集約し、全タスク集約レポートを Slack に 1 回送信する"""
    target_date = execution_date or datetime.datetime.now(datetime.timezone.utc).date()
    try:
        tasks = _latest_execution_tasks(target_date)
        if not tasks:
            logger.warning(f"⚠️ [Aggregation] No identifiable crawler execution for {target_date}. Skipping aggregated report.")
            return False
        records = sorted(tasks, key=lambda t: t.task_index)
        aggregated = aggregate_task_array_reports(records, total_jobs=89)
        logger.info(
            f"📊 [Aggregation] Tasks: {len(records)}, Total: {aggregated['total_jobs']}, "
            f"Executed: {aggregated['executed_jobs']}, Success: {aggregated['success_jobs']}, Failed: {aggregated['failed_jobs']}"
        )
        return bool(asyncio.run(asyncio.wait_for(
            send_crawling_summary_alert(aggregated["slack_message"]),
            timeout=SLACK_REPORT_TIMEOUT_SEC,
        )))
    except Exception as e:
        logger.warning(f"⚠️ [Aggregation Warning] Failed to send aggregated crawl report: {e}")
        return False


def run_command(cmd: list[str], desc: str):
    """リアルタイムログ付きで外部コマンドを実行"""
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

    if proc.stdout is not None:
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            print(line, end='', flush=True)

    proc.wait()
    elapsed = time.time() - start_time

    if proc.returncode != 0:
        logger.error(f"=== [FAILED] {desc} (Exit Code: {proc.returncode}, Time: {int(elapsed)}s) ===")
        raise RuntimeError(f"Step '{desc}' failed with exit code {proc.returncode}")

    logger.info(f"=== [SUCCESS] {desc} (Time: {int(elapsed)}s) ===")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cloud Run ML Pipeline Job")
    parser.add_argument("--skip-portals", action="store_true", help="Skip large portal sites (homes, athome)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without modifying GCP resources")
    parser.add_argument("--force", action="store_true", help="Force ML execution even if barrier ratio is low")
    args = parser.parse_args(argv)

    current_dir = os.path.dirname(os.path.abspath(__file__)) # .../scripts/ops
    scripts_dir = os.path.dirname(current_dir)              # .../scripts
    crawler_dir = os.path.dirname(scripts_dir)              # .../crawler

    debug_tools_dir = os.path.join(scripts_dir, "debug_tools")
    maintenance_dir = os.path.join(scripts_dir, "maintenance")
    ops_dir = current_dir

    logger.info(SEPARATOR)
    logger.info(f"Starting ML ESTIMATION & RECOMMENDATION PIPELINE (skip_portals={args.skip_portals})")
    logger.info(SEPARATOR)

    try:
        # Step 0: Cloud SQL 確認・ProxySQL 起動・疎通確認・DB 待機
        start_on_demand_resources(dry_run=args.dry_run)
        run_command([
            sys.executable,
            os.path.join(debug_tools_dir, "wait_for_db.py")
        ], "Step 0/5: Database Readiness Pre-flight Check")

        # Step 1: バリア完了検証
        ok, failed = verify_barrier_completion()
        send_aggregated_crawl_report()
        if not ok and not args.force:
            logger.warning(f"⚠️ 一部タスク未完了/失敗のため ML パイプラインを中断します (失敗: {failed})。--force で強制実行可能。")
            return 1
        if not ok:
            logger.warning(f"⚠️ 一部タスク未完了/失敗 (失敗: {failed})。--force 指定のため完了分のデータで続行します。")

        # Step 2: データ検証 & クレンジング
        run_command([
            sys.executable,
            os.path.join(maintenance_dir, "validate_data.py")
        ], "Step 1/5: Scraping Data Validation & Automated Cleansing")

        # AI自己修復用のバグ指示書生成
        run_command([
            sys.executable,
            os.path.join(debug_tools_dir, "auto_heal_parsers.py")
        ], "Step 1.5/5: Auto-Heal Instruction Generation for AI Agent")

        # Step 3: 最新データによるMLモデル再学習
        run_command([
            sys.executable,
            os.path.join(crawler_dir, "package", "ml", "train.py")
        ], "Step 2/5: ML Model Re-Training (LightGBM, XGBoost, CatBoost, RandomForest)")

        # Step 4: 一括価格予測・投資シミュレーション評価のDB更新 (バルクML推論)
        eval_cmd = [sys.executable, os.path.join(ops_dir, "run_bulk_ml_evaluation.py")]
        if args.skip_portals:
            eval_cmd.append("--skip-portals")
        run_command(eval_cmd, f"Step 3/5: Batch Estimation & Investment Evaluation{' [Skip Portals]' if args.skip_portals else ''}")

        # Step 5: お宝物件のスクリーニング & Slack通知
        run_command([
            sys.executable,
            os.path.join(ops_dir, "send_recommendations.py")
        ], "Step 4/5: Slack Notification (Hot Property Recommendation)")

        # Step 6: 日次予測精度診断 & AIインサイト分析
        run_command([
            sys.executable,
            os.path.join(ops_dir, "run_daily_prediction_diagnostics.py"),
            "--notify"
        ], "Step 5/5: Daily ML Prediction Diagnostics & AI Insights")

        logger.info(SEPARATOR)
        logger.info("ML PIPELINE COMPLETED SUCCESSFULLY! All steps finished.")
        logger.info(SEPARATOR)
        return 0

    finally:
        # Step 7: 終了フック (ProxySQL MIG を size=0 に停止してゾンビ課金を防止)
        try:
            logger.info("Executing teardown hook: stopping ProxySQL MIG (size: 1 -> 0)...")
            scale_proxysql_mig(target_size=0, dry_run=args.dry_run)
        except Exception:
            logger.exception("Failed to scale in ProxySQL MIG in finally block")


if __name__ == "__main__":
    sys.exit(main())

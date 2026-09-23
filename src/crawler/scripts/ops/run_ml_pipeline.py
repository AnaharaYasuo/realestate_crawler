# ruff: noqa: E402, F401
"""
Cloud Run ML Pipeline Job:
1. クローラータスク完了確認 (Barrier Check)
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

try:
    from google.cloud import compute_v1
except ImportError:
    compute_v1 = None

configure_logging()
logger = logging.getLogger(__name__)


def scale_proxysql_mig(target_size: int = 0, project_id: str | None = None, region: str | None = None, mig_name: str | None = None, dry_run: bool = False) -> bool:
    """ProxySQL MIG のサイズを変更 (バッチ終了時の停止 size: 1 -> 0)"""
    project = project_id or os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT", "sumifu")
    reg = region or os.getenv("GCP_REGION", "asia-northeast1")
    mig = mig_name or os.getenv("PROXYSQL_MIG_NAME", f"proxysql-mig-{os.getenv('ENVIRONMENT', 'prod')}")

    logger.info(f"Scaling ProxySQL MIG '{mig}' to size {target_size} (project: {project}, region: {reg}, dry_run: {dry_run})")
    if dry_run or not bool(os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")):
        logger.info(f"[Dry-run/Local] ProxySQL MIG scaled to {target_size} (mocked).")
        return True

    if compute_v1 is not None:
        try:
            client = compute_v1.RegionInstanceGroupManagersClient()
            op = client.resize(
                project=project,
                region=reg,
                region_instance_group_manager=mig,
                size=target_size,
            )
            logger.info(f"Resize operation submitted: {op.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to resize ProxySQL MIG via compute_v1: {e}")
            return False
    else:
        cmd = [
            "gcloud", "compute", "instance-groups", "managed", "resize",
            mig, f"--size={target_size}", f"--region={reg}", f"--project={project}", "--quiet"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            logger.error(f"gcloud resize failed: {res.stderr}")
            return False
        return True


def verify_barrier_completion(execution_date: datetime.date | None = None, min_success_ratio: float = 0.85) -> tuple[bool, list[str]]:
    """DB のタスク状況を点検し、ML 実行基準を満たしているか検証"""
    target_date = execution_date or datetime.datetime.now(datetime.timezone.utc).date()
    try:
        tasks = list(CrawlerTaskExecution.objects.filter(execution_date=target_date))
        if not tasks:
            logger.warning(f"No task records found for {target_date}. Proceeding with existing DB data.")
            return True, []

        total = len(tasks)
        completed = [t for t in tasks if t.status == "COMPLETED"]
        failed = [t.task_id for t in tasks if t.status in ("FAILED", "PENDING")]

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

    logger.info("=============================================================")
    logger.info(f"Starting ML ESTIMATION & RECOMMENDATION PIPELINE (skip_portals={args.skip_portals})")
    logger.info("=============================================================")

    try:
        # Step 1: バリア完了検証
        ok, failed = verify_barrier_completion()
        if not ok and not args.force:
            logger.warning(f"⚠️ 一部タスク未完了/失敗のため ML パイプラインを中断します (失敗: {failed})。--force で強制実行可能。")
            return 1

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

        logger.info("=============================================================")
        logger.info("ML PIPELINE COMPLETED SUCCESSFULLY! All steps finished.")
        logger.info("=============================================================")
        return 0

    finally:
        # Step 7: 終了フック (ProxySQL MIG を size=0 に停止してゾンビ課金を防止)
        try:
            logger.info("Executing teardown hook: stopping ProxySQL MIG (size: 1 -> 0)...")
            scale_proxysql_mig(target_size=0, dry_run=args.dry_run)
        except Exception as te:
            logger.error(f"Failed to scale in ProxySQL MIG in finally block: {te}")


if __name__ == "__main__":
    sys.exit(main())

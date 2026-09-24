# ruff: noqa: E402, F401
"""
Cloud Run Dispatcher Job:
1. ProxySQL MIG をオンデマンド起動 (size: 0 -> 1)
2. ProxySQL のヘルスチェック疎通確認 (port 6033)
3. DB スキーママイグレーション実行
4. Cloud Tasks (crawler-tasks) へ全45タスクを一括登録
5. 5秒〜数十秒で即座に exit 0 (課金停止)
"""
import argparse
import datetime
import json
import logging
import os
import socket
import subprocess
import sys
import time

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
from package.utils.crawl_jobs import CRAWL_JOBS
from package.models.crawler_task_execution import CrawlerTaskExecution
from package.utils.gcp_resources import (
    scale_proxysql_mig as _gcp_scale_proxysql_mig,
    get_gcp_access_token as _get_gcp_access_token,
)

try:
    from google.cloud import compute_v1
    from google.cloud import tasks_v2
except ImportError:
    compute_v1 = None
    tasks_v2 = None

configure_logging()
logger = logging.getLogger(__name__)


def scale_proxysql_mig(target_size: int = 1, project_id: str | None = None, region: str | None = None, mig_name: str | None = None, dry_run: bool = False) -> bool:
    """ProxySQL MIG のサイズを変更 (0 -> 1 または 1 -> 0)"""
    token_fn = getattr(sys.modules[__name__], "_get_gcp_access_token", _get_gcp_access_token)
    comp_mod = getattr(sys.modules[__name__], "compute_v1", compute_v1)
    res = _gcp_scale_proxysql_mig(
        target_size=target_size,
        project_id=project_id,
        region=region,
        mig_name=mig_name,
        dry_run=dry_run,
        compute_module=comp_mod,
        get_token_callback=token_fn,
    )
    if not res and bool(os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")) and not dry_run:
        raise RuntimeError(f"ProxySQL MIG resize failed to scale to {target_size}")
    return res


def wait_for_proxysql_health(host: str | None = None, port: int | None = None, timeout_sec: int = 60) -> bool:
    """ProxySQL のポート (6033) 疎通を確認"""
    target_host = host or os.getenv("DB_HOST", "127.0.0.1")
    target_port = int(port or os.getenv("DB_PORT", "6033"))

    # ローカルやコンテナで db:3306 の場合はそのままチェック
    if not bool(os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")):
        logger.info(f"[Local/Test] Skipping remote ProxySQL wait, checking {target_host}:{target_port}...")
        return True

    logger.info(f"Waiting for ProxySQL health at {target_host}:{target_port} (timeout: {timeout_sec}s)...")
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            with socket.create_connection((target_host, target_port), timeout=2.0):
                logger.info(f"ProxySQL is healthy and reachable at {target_host}:{target_port}!")
                return True
        except OSError:
            time.sleep(2)

    logger.warning(f"ProxySQL connection wait timed out ({timeout_sec}s). Proceeding with caution.")
    return False


def run_db_migration() -> bool:
    """DB スキーママイグレーションを実行"""
    logger.info("Executing database migration (manage.py migrate)...")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    crawler_dir = os.path.dirname(os.path.dirname(current_dir))
    manage_py = os.path.join(crawler_dir, "manage.py")

    cmd = [sys.executable, manage_py, "migrate", "--noinput"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        logger.error(f"Migration failed: {res.stderr}")
        raise RuntimeError(f"Database migration failed: {res.stderr}")
    logger.info("Database migration finished successfully.")
    return True


def _record_pending_task(today: datetime.date, company: str, prop_type: str) -> None:
    """DB に初期ステータス PENDING を登録"""
    try:
        CrawlerTaskExecution.objects.update_or_create(
            execution_date=today,
            task_id=f"{company}_{prop_type}",
            defaults={
                "status": "PENDING",
                "company": company,
                "property_type": prop_type,
                "scraped_count": 0,
                "error_message": "",
            },
        )
    except Exception as e:
        logger.debug(f"Could not record PENDING status for {company}-{prop_type}: {e}")


def _dispatch_task_to_cloud(tasks_client, parent: str, url: str, sa_email: str, payload: dict) -> None:
    """Cloud Tasks API 経由でタスクを送信"""
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("ESTIMATION_API_KEY")
    if api_key:
        headers["X-API-KEY"] = api_key
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,
            "headers": headers,
            "body": json.dumps(payload).encode(),
            "oidc_token": {"service_account_email": sa_email},
        }
    }
    tasks_client.create_task(request={"parent": parent, "task": task})


def enqueue_crawl_tasks(project_id: str | None = None, region: str | None = None, queue_name: str | None = None, worker_url: str | None = None, skip_portals: bool = False, dry_run: bool = False) -> int:
    """全クロールジョブを Cloud Tasks へ登録"""
    project = project_id or os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT", "sumifu")
    reg = region or os.getenv("GCP_REGION", "asia-northeast1")
    env = os.getenv("ENVIRONMENT", "prod")
    queue = queue_name or os.getenv("CLOUD_TASKS_QUEUE", f"realestate-crawler-queue-{env}")
    url = worker_url or os.getenv("CRAWLER_WORKER_URL", f"https://realestate-crawler-worker-{env}.run.app/api/crawl/task")
    sa_email = os.getenv("CRAWLER_RUNNER_SA", f"realestate-crawler-runner@{project}.iam.gserviceaccount.com")

    portal_companies = {"homes", "athome"}
    enqueued_count = 0
    today = datetime.datetime.now(datetime.timezone.utc).date()
    today_str = today.isoformat()

    logger.info(f"Enqueueing crawl tasks to queue '{queue}' targeting {url} (skip_portals={skip_portals})...")

    is_cloud = bool(os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"))
    tasks_client = tasks_v2.CloudTasksClient() if (is_cloud and tasks_v2 is not None and not dry_run) else None
    parent = tasks_client.queue_path(project, reg, queue) if tasks_client is not None else ""

    for company, prop_type in CRAWL_JOBS:
        if skip_portals and company.lower() in portal_companies:
            continue

        _record_pending_task(today, company, prop_type)

        if tasks_client is not None:
            payload = {"company": company, "property_type": prop_type, "execution_date": today_str}
            _dispatch_task_to_cloud(tasks_client, parent, url, sa_email, payload)

        enqueued_count += 1

    logger.info(f"Successfully enqueued {enqueued_count} crawl tasks.")
    return enqueued_count


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cloud Run Dispatcher Job")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without modifying GCP resources")
    parser.add_argument("--skip-portals", action="store_true", help="Skip large portal sites (homes, athome)")
    args = parser.parse_args(argv)

    logger.info("=== [DISPATCHER START] Starting Real Estate Pipeline Dispatcher ===")
    
    # 1. ProxySQL MIG 起動 (size: 0 -> 1)
    scale_proxysql_mig(target_size=1, dry_run=args.dry_run)

    # 2. ProxySQL 疎通待機
    wait_for_proxysql_health(timeout_sec=60)

    # 3. DB マイグレーション
    if not args.dry_run:
        run_db_migration()

    # 4. Cloud Tasks へ全タスク投入
    enqueue_crawl_tasks(skip_portals=args.skip_portals, dry_run=args.dry_run)

    logger.info("=== [DISPATCHER SUCCESS] All tasks dispatched. Exiting immediately (CPU cost ¥0). ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

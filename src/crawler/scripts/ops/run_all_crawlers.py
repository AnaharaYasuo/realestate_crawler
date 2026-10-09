# ruff: noqa: E402, F401
# -*- coding: utf-8 -*-
import os
import sys
import time
import subprocess
import logging
import datetime
import argparse
import json
import signal
import atexit
import asyncio
import socket
import threading
import tempfile

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

from package.utils.newrelic_helper import init_new_relic, record_crawler_metrics, record_container_sample, start_container_sample_thread, shutdown_new_relic
init_new_relic()
record_container_sample()
start_container_sample_thread(interval_sec=60)

from django.apps import apps
from django.db import connection
from django.db.models import Q
from django.utils import timezone
from package.utils.slack import send_crawling_summary_alert, send_dev_report, send_slack_message
from package.utils.task_distribution import get_task_config, distribute_jobs, get_execution_date, get_execution_id
from package.utils.crawler_scheduler import select_next_job
from package.models.crawler_task_execution import CrawlerTaskExecution
from package.utils.failure_reporter import FailureReporter, generate_auto_heal_trigger_message
from package.utils.db_timeouts import bound_mysql_timeouts
from package.utils.crawler_watchdog import check_job_hung, kill_hung_job_process, HANG_THRESHOLD_SEC
from package.api.adaptive_concurrency import AdaptiveConcurrencyController

from package.utils.crawl_jobs import CRAWL_JOBS, filter_crawl_jobs  # noqa: E402  — SSOT for production + tests

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_args():
    """Parse CLI arguments for run_all_crawlers."""
    default_parallel = 9
    default_playwright_parallel = 3
    parser = argparse.ArgumentParser(description="Run all crawler jobs in parallel or sequentially.")
    parser.add_argument("--dry-run", action="store_true", help="Print jobs without execution.")
    parser.add_argument("--parallel", "--standard-parallel", type=int, default=default_parallel, help="Number of parallel standard crawler processes (aiohttp/http).")
    parser.add_argument("--playwright-parallel", type=int, default=default_playwright_parallel, help="Number of parallel Playwright crawler processes (high memory usage).")
    parser.add_argument("--skip-portals", action="store_true", help="Skip large portal sites (athome, homes) for fast execution.")
    parser.add_argument("--company", type=str, default=None, help="Target company name(s), comma-separated (e.g. sumifu,mitsui).")
    parser.add_argument("--property-type", "--type", dest="property_type", type=str, default=None, help="Target property type(s), comma-separated (e.g. mansion,kodate).")
    parser.add_argument("--sites", type=str, default=None, help="Target site tokens, comma-separated (e.g. sumifu:mansion,tokyu).")
    return parser.parse_args()

# ポータルサイトおよび Playwright を使用する高メモリ負荷サイトのリスト
PORTAL_COMPANIES = ["athome", "homes"]
PLAYWRIGHT_COMPANIES = ["athome"]


# ロギング設定
_current_dir = os.path.dirname(os.path.abspath(__file__)) # .../scripts/ops
_scripts_dir = os.path.dirname(_current_dir)              # .../scripts
_crawler_dir = os.path.dirname(_scripts_dir)              # .../crawler
_project_root = os.path.dirname(os.path.dirname(_crawler_dir)) # root
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)
main_py_path = os.path.join(_crawler_dir, "main.py")

from package.utils.logging_config import configure_logging
configure_logging()

log_dir = os.path.join(_crawler_dir, "logs")
os.makedirs(log_dir, exist_ok=True)


# 定義済みの全クロールジョブリスト
from package.utils.crawl_jobs import CRAWL_JOBS  # noqa: E402  — SSOT for production + tests

logger = logging.getLogger(__name__)




cooldown_sec = int(os.getenv("CRAWL_COOLDOWN_SEC", 180))
timeout_sec = int(os.getenv("CRAWL_TIMEOUT_SEC", "32400"))

DB_HEALTH_CHECK_INTERVAL_SEC = max(1.0, float(os.getenv("DB_HEALTH_CHECK_INTERVAL_SEC", "15")))
DB_HEALTH_MAX_CONSECUTIVE_FAILURES = max(1, int(os.getenv("DB_HEALTH_MAX_CONSECUTIVE_FAILURES", "3")))
DB_HEALTH_SOCKET_TIMEOUT_SEC = 3.0
DB_LIVENESS_ABORT_SAVE_TIMEOUT_SEC = 10.0

active_processes = {}


class DbLivenessMonitor:
    """ProxySQL / DB への TCP 疎通を定期監視し、連続失敗回数で応答喪失を判定する"""

    def __init__(
        self,
        host,
        port,
        interval_sec=DB_HEALTH_CHECK_INTERVAL_SEC,
        max_failures=DB_HEALTH_MAX_CONSECUTIVE_FAILURES,
        timeout_sec=DB_HEALTH_SOCKET_TIMEOUT_SEC,
        connector=socket.create_connection,
        clock=time.monotonic,
    ):
        self.host = host
        self.port = int(port)
        self.interval_sec = interval_sec
        self.max_failures = max(1, int(max_failures))
        self.timeout_sec = timeout_sec
        self._connector = connector
        self._clock = clock
        self._last_checked_at = None
        self.consecutive_failures = 0
        self.last_error = ""

    def is_lost(self) -> bool:
        now = self._clock()
        if self._last_checked_at is None or now - self._last_checked_at >= self.interval_sec:
            self._last_checked_at = now
            self._probe()
        return self.consecutive_failures >= self.max_failures

    def _probe(self) -> None:
        # 認証付きクエリで判定すると、ProxySQL がバックエンド接続上限で要求をキュー待ちさせた際の
        # 正常な混雑を応答喪失と誤判定して全クロールを停止し得るため、TCP 疎通で判定する
        try:
            with self._connector((self.host, self.port), timeout=self.timeout_sec):
                pass
        except OSError as e:
            self.consecutive_failures += 1
            self.last_error = str(e)
            logger.warning(
                f"DB/ProxySQL 疎通失敗 {self.host}:{self.port} "
                f"({self.consecutive_failures}/{self.max_failures}): {e}"
            )
            return
        self.consecutive_failures = 0


def resolve_db_endpoint():
    """Django 設定 (未設定時は環境変数) から DB 接続先 (ProxySQL 経由時は 10.0.0.10:6033) を取得する"""
    settings_dict = getattr(connection, "settings_dict", None) or {}
    host = settings_dict.get("HOST") or os.getenv("DB_HOST", "127.0.0.1")
    port = int(settings_dict.get("PORT") or os.getenv("DB_PORT", "3306"))
    # MySQL クライアントは localhost / ソケットパス指定時に TCP を使わないため、TCP 監視では DB 正常時も誤検知する
    if host == "localhost" or host.startswith("/"):
        logger.warning(f"DB 接続先 {host} は UNIX ソケット接続のため TCP 疎通監視を無効化します")
        return None
    return host, port


def bound_db_connect_timeout():
    """ループ内の DB 処理が DB 不通時に OS 既定の TCP 待ちで長時間ブロックしないよう接続・読み書きタイムアウトを設ける"""
    bound_mysql_timeouts(getattr(connection, "settings_dict", None))

def cleanup_active_process():
    """現在アクティブなすべての子プロセスグループを安全かつ完全にキルする"""
    global active_processes
    for idx, (proc, company, ptype, *_) in list(active_processes.items()):
        if proc.poll() is None:
            try:
                pgid = os.getpgid(proc.pid)
                logging.info(f"親プロセスの終了を検知したため、子プロセスグループ {pgid} ({company} - {ptype}) を強制終了します...")
                os.killpg(pgid, signal.SIGKILL)
                proc.communicate()  # プロセスゾンビ化を防ぐための回収
            except Exception as e:
                logging.exception(f"子プロセスのクリーンアップ中にエラー: {e}")
    active_processes.clear()


def record_task_start(task_index, task_count, jobs_assigned):
    """自タスクの CrawlerTaskExecution を RUNNING で登録する (同日の別実行と区別するため実行 ID を記録)"""
    try:
        record, _ = CrawlerTaskExecution.objects.update_or_create(
            execution_date=get_execution_date(),
            task_index=task_index or 0,
            execution_id=get_execution_id(),
            defaults={
                "task_count": task_count,
                "status": "RUNNING",
                "jobs_assigned": jobs_assigned,
            },
        )
    except Exception as dbe:
        logger.warning(f"Failed to record CrawlerTaskExecution start: {dbe}")
        return None
    return record


def _mark_task_failed(task_exec_record):
    try:
        task_exec_record.status = "FAILED"
        task_exec_record.save()
    except Exception as dbe:
        logger.warning(f"Failed to mark CrawlerTaskExecution FAILED after DB liveness loss: {dbe}")


def abort_on_db_liveness_loss(monitor, task_exec_record=None):
    """DB 応答喪失時にクローラー子プロセス群を即時停止し、Slack 通知後に exit 1 で終了する (Fast-Fail)"""
    aborted_jobs = [f"{company} - {ptype}" for _, company, ptype, *_ in active_processes.values()]
    endpoint = f"{monitor.host}:{monitor.port}"
    logger.error(
        f"DB/ProxySQL ({endpoint}) の応答喪失を検知 (連続 {monitor.consecutive_failures} 回失敗)。"
        f"実行中クローラー {len(aborted_jobs)} 件を即時停止します。"
    )
    cleanup_active_process()

    msg = (
        f"🚨 【緊急停止: DB/ProxySQL 応答喪失】 クローリングを Fast-Fail 停止しました。\n"
        f"・接続先: {endpoint}\n"
        f"・判定: 連続 {monitor.consecutive_failures} 回の疎通失敗 (最終エラー: {monitor.last_error})\n"
        f"・停止ジョブ: {', '.join(aborted_jobs) if aborted_jobs else 'なし'}"
    )
    try:
        asyncio.run(send_crawling_summary_alert(msg))
    except Exception:
        logger.exception("Failed to post DB liveness loss alert")

    if task_exec_record is not None:
        # DB 不通時は save() が TCP 接続待ちでブロックし得るため、有限時間で見切って終了する
        saver = threading.Thread(target=_mark_task_failed, args=(task_exec_record,), daemon=True)
        saver.start()
        saver.join(DB_LIVENESS_ABORT_SAVE_TIMEOUT_SEC)
        if saver.is_alive():
            logger.warning(
                f"CrawlerTaskExecution の FAILED 更新が {DB_LIVENESS_ABORT_SAVE_TIMEOUT_SEC}s 以内に完了しないため待機を打ち切ります。"
            )

    raise SystemExit(1)


def signal_handler(signum, frame):
    logging.info(f"シグナル {signum} を受信しました。アクティブなクローラーを強制終了します。")
    cleanup_active_process()
    sys.exit(128 + signum)

# シグナルハンドラおよび atexit の登録
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(cleanup_active_process)

def clean_zombies():
    """自分自身以外の残留クローラープロセスを一掃する"""
    my_pid = os.getpid()
    cleaned = 0
    proc_dir = '/proc'
    if not os.path.exists(proc_dir):
        return
    for name in os.listdir(proc_dir):
        if not name.isdigit():
            continue
        pid = int(name)
        if pid == my_pid:
            continue
        try:
            with open(os.path.join(proc_dir, name, 'cmdline'), 'r') as f:
                cmdline = f.read().replace('\x00', ' ')
            if 'main.py' in cmdline and '--company=' in cmdline:
                logging.info(f"残留プロセスを検知: PID {pid} ({cmdline.strip()})")
                os.kill(pid, signal.SIGKILL)
                cleaned += 1
        except Exception:
            pass
    if cleaned > 0:
        logging.info(f"過去のゾンビプロセス {cleaned} 件を一掃しました。")

def format_duration(seconds: int) -> str:
    """Format duration seconds to readable string."""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}時間{m}分{s}秒"
    elif m > 0:
        return f"{m}分{s}秒"
    else:
        return f"{s}秒"


def get_count_for_job(company: str, ptype: str, start_dt: datetime.datetime | None) -> tuple[int, int, int]:
    """
    指定会社・種別における指定日時以降の処理件数内訳を取得する。
    Returns:
        (detail_count, skipped_count, total_count)
    """
    if apps is None or start_dt is None:
        return 0, 0, 0
    try:
        target = ptype.lower().replace("_", "")
        valid_targets = {target, target.replace("invest", "investment")}
        if "investkodate" in target or "investmentkodate" in target:
            valid_targets.update({"investapartment", "investmentapartment"})

        total_detail_cnt = 0
        total_skip_cnt = 0
        matched_any = False

        for model in apps.get_models():
            m_name = model.__name__.lower()
            if m_name.startswith(company.lower()):
                rest = m_name[len(company):]
                if rest in valid_targets:
                    has_update = hasattr(model, "updateDateTime")
                    has_input = hasattr(model, "inputDateTime")

                    if not has_input and not has_update:
                        continue

                    matched_any = True
                    if has_input and has_update:
                        q_detail = Q(inputDateTime__gte=start_dt)
                        q_skip = Q(updateDateTime__gte=start_dt) & (Q(inputDateTime__lt=start_dt) | Q(inputDateTime__isnull=True))
                        detail_cnt = model.objects.filter(q_detail).count()
                        skip_cnt = model.objects.filter(q_skip).count()
                        total_detail_cnt += detail_cnt
                        total_skip_cnt += skip_cnt
                    elif has_input:
                        cnt = model.objects.filter(inputDateTime__gte=start_dt).count()
                        total_detail_cnt += cnt
                    else:
                        cnt = model.objects.filter(updateDateTime__gte=start_dt).count()
                        total_detail_cnt += cnt

        if matched_any:
            return total_detail_cnt, total_skip_cnt, total_detail_cnt + total_skip_cnt
    except Exception:
        logger.exception("Failed to get db count for %s - %s", company, ptype)
        return None, None, None
    return 0, 0, 0


def format_job_success_message(
    company: str,
    ptype: str,
    idx: int,
    total_jobs: int,
    detail_cnt: int,
    skipped_cnt: int,
    total_cnt: int,
    duration_job_str: str
) -> str:
    """ジョブ正常終了時のSlack通知文面をフォーマット"""
    return (
        f"✅ 【成功】 {company} - {ptype} (Job {idx}/{total_jobs}) | "
        f"詳細処理: {detail_cnt} 件 / 未変更スキップ: {skipped_cnt} 件 (計: {total_cnt} 件) | "
        f"処理時間: {duration_job_str}"
    )


def format_summary_item_message(
    company: str,
    ptype: str,
    detail_cnt: int,
    skipped_cnt: int,
    total_cnt: int,
    timing_str: str = ""
) -> str:
    """24時間サマリーレポート内の各行をフォーマット"""
    return f"• {company} - {ptype}: 詳細処理 {detail_cnt} 件 / 未変更スキップ {skipped_cnt} 件 (計: {total_cnt} 件){timing_str}"


def main():
    """Run or list crawler jobs and report execution results.

    Executed runs post Slack and database status and write a dated JSON report.
    """
    args = parse_args()
    if args.dry_run:
        target_jobs = [j for j in CRAWL_JOBS if not (args.skip_portals and j[0].lower() in PORTAL_COMPANIES)]
        logging.info(f"--- Dry Run Mode: List of Crawling Jobs ({len(target_jobs)} jobs) ---")
        for i, (company, ptype) in enumerate(target_jobs, 1):
            logging.info(f"{i:02d}. Company: {company}, Type: {ptype}")
        logging.info("Dry run finished.")
        return

    # 起動時にゾンビプロセスを自動一掃
    clean_zombies()
    bound_db_connect_timeout()

    # 実行単位で独立した動的並行度状態ファイルを設定（子プロセスへ継承）
    if "CRAWLER_CONCURRENCY_STATE_FILE" not in os.environ:
        os.environ["CRAWLER_CONCURRENCY_STATE_FILE"] = os.path.join(
            tempfile.gettempdir(),
            f"crawler_concurrency_state_{os.getpid()}_{int(time.time())}.json"
        )

    def post_slack(msg):
        try:
            asyncio.run(send_crawling_summary_alert(msg))
        except Exception as se:
            logging.exception(f"Failed to post Slack status: {se}")

    today_str = datetime.date.today().strftime("%Y%m%d")
    report_path = os.path.join(log_dir, f"crawl_report_{today_str}.json")
    
    task_index, task_count = get_task_config()
    target_jobs = list(CRAWL_JOBS)
    if args.skip_portals:
        target_jobs = [j for j in target_jobs if j[0].lower() not in PORTAL_COMPANIES]
        logging.info(f"Skipping portal sites ({', '.join(PORTAL_COMPANIES)}). Active jobs: {len(target_jobs)}/{len(CRAWL_JOBS)}")

    company_arg = getattr(args, "company", None)
    prop_type_arg = getattr(args, "property_type", None)
    sites_arg = getattr(args, "sites", None)
    if company_arg or prop_type_arg or sites_arg:
        target_jobs = filter_crawl_jobs(
            target_jobs,
            sites=sites_arg,
            company=company_arg,
            property_type=prop_type_arg,
        )
        logger.info(f"🎯 [Target Filter] Filtered jobs to {len(target_jobs)} jobs based on company={company_arg}, property_type={prop_type_arg}, sites={sites_arg}")

    if task_count > 1 and task_index is not None:
        target_jobs = distribute_jobs(target_jobs, task_index, task_count)
        logging.info(f"🎯 [Task Array] Task {task_index}/{task_count} に {len(target_jobs)} 件のジョブを割り当てました")

    if not target_jobs:
        logger.info(f"✔ [Fast Exit] Task {task_index if task_index is not None else 0}/{task_count}: 担当ジョブが0件のため即座に正常終了します。")
        if task_count > 1 and task_index is not None:
            try:
                CrawlerTaskExecution.objects.update_or_create(
                    execution_date=get_execution_date(),
                    task_index=task_index,
                    execution_id=get_execution_id(),
                    defaults={
                        "task_count": task_count,
                        "status": "COMPLETED",
                        "jobs_assigned": 0,
                        "jobs_success": 0,
                        "jobs_failed": 0,
                    },
                )
            except Exception as dbe:
                logger.warning(f"Failed to record fast exit CrawlerTaskExecution: {dbe}")
        return

    # DB にタスク実行状態を登録
    task_exec_record = record_task_start(task_index, task_count, len(target_jobs))

    if task_count > 1 and task_index is not None:
        post_slack(f"🚀 【分散クローリング開始】 Task {task_index}/{task_count} を開始します。(担当 {len(target_jobs)} ジョブ)")
    else:
        post_slack(f"🚀 【クローリング開始】 一括巡回処理を開始します。(全 {len(target_jobs)} ジョブ{' [ポータル割愛]' if args.skip_portals else ''})")
    
    results = []
    job_queue = list(target_jobs)
    next_job_index = 1
    
    global active_processes

    batch_start_dt = datetime.datetime.now(datetime.timezone.utc)
    db_endpoint = resolve_db_endpoint()
    db_monitor = DbLivenessMonitor(*db_endpoint) if db_endpoint else None

    while job_queue or active_processes:
        if db_monitor is not None and db_monitor.is_lost():
            abort_on_db_liveness_loss(db_monitor, task_exec_record)

        now = time.time()
        
        # 1. 終了プロセスの回収およびタイムアウトのキル
        active_indices = tuple(active_processes.keys())
        for idx in active_indices:
            proc, company, ptype, start_t, start_dt, *extra = active_processes[idx]
            last_act = extra[0] if extra else start_t
            poll_status = proc.poll()
            if poll_status is not None:
                # 正常・異常終了の回収
                exit_code = proc.returncode
                status = "success" if exit_code == 0 else "failed"
                error_msg = "" if exit_code == 0 else f"Job exited with code {exit_code}"
                elapsed = now - start_t
                end_dt = timezone.now() if timezone is not None else datetime.datetime.now()
                duration_job_str = format_duration(int(elapsed))
                
                scraped_cnt = 0
                detail_cnt = 0
                skipped_cnt = 0
                if exit_code == 0:
                    counts = get_count_for_job(company, ptype, start_dt)
                    if counts[0] is None:
                        status = "failed"
                        error_type = "CountQueryFailure"
                        error_msg = "Database count query failed"
                        post_slack(f"❌ 【失敗: DB件数取得エラー】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | 処理時間: {duration_job_str}")
                    else:
                        detail_cnt, skipped_cnt, scraped_cnt = counts
                        if scraped_cnt > 0:
                            error_type = ""
                            post_slack(
                                format_job_success_message(
                                    company=company,
                                    ptype=ptype,
                                    idx=idx,
                                    total_jobs=len(CRAWL_JOBS),
                                    detail_cnt=detail_cnt,
                                    skipped_cnt=skipped_cnt,
                                    total_cnt=scraped_cnt,
                                    duration_job_str=duration_job_str,
                                )
                            )
                        else:
                            status = "failed"
                            error_type = "ZeroCountFailure"
                            error_msg = "0 items scraped (Zero count failure)"
                            post_slack(f"❌ 【失敗: 0件取得】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | 新規取得: 0 件 | 処理時間: {duration_job_str} (データが1件も取得できていません)")
                else:
                    error_type = "ProcessCrashFailure"
                    post_slack(f"❌ 【失敗】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | Exit Code: {exit_code} | 処理時間: {duration_job_str}")

                if status != "success":
                    logging.error(f"[{idx}] Crawl job FAILED for {company} - {ptype}. Exit Code: {exit_code}, Scraped: {scraped_cnt} items, Error: {error_msg}")
                    try:
                        FailureReporter.record_job_failure(
                            company=company,
                            property_type=ptype,
                            error_type=error_type,
                            error_message=error_msg,
                            exit_code=exit_code,
                            duration_seconds=int(elapsed),
                            task_index=task_index,
                            task_count=task_count,
                            date_str=today_str
                        )
                    except Exception as fe:
                        logging.warning(f"Failed to record failure telemetry for {company} - {ptype}: {fe}")
                else:
                    logging.info(f"[{idx}] Crawl job finished for {company} - {ptype}. Status: {status}, Code: {exit_code}, Time: {duration_job_str}")
                results.append({
                    "index": idx,
                    "company": company,
                    "property_type": ptype,
                    "status": status,
                    "exit_code": exit_code,
                    "start_time": start_dt.strftime(DATETIME_FORMAT) if start_dt else "",
                    "end_time": end_dt.strftime(DATETIME_FORMAT) if end_dt else "",
                    "duration": duration_job_str,
                    "elapsed_seconds": int(elapsed),
                    "items_count": scraped_cnt,
                    "detail_count": detail_cnt,
                    "skipped_count": skipped_cnt,
                    "error_message": error_msg
                })

                try:
                    record_crawler_metrics(
                        site_name=company,
                        property_type=ptype,
                        count=scraped_cnt,
                        duration_sec=float(elapsed),
                        zero_count=(exit_code == 0 and scraped_cnt == 0),
                        status=status,
                        metadata={"exit_code": exit_code, "error_msg": error_msg or ""}
                    )
                except Exception as nre:
                    logger.warning(f"Failed to record New Relic metrics for {company} - {ptype}: {nre}")

                del active_processes[idx]
                AdaptiveConcurrencyController.set_active_jobs_count(len(active_processes))
                continue

        # 子プロセスの進捗監視（1ループあたり最大1ジョブのみDB件数増分を確認し、DB負荷を最小化）
        # HANG_THRESHOLD_SEC <= 0 の場合はハング検知が無効化されているため進捗カウント取得をスキップ
        # extra: (last_act, current_db_cnt, last_check_t)
        if HANG_THRESHOLD_SEC > 0:
            for idx in tuple(active_processes.keys()):
                if idx not in active_processes:
                    continue
                proc, company, ptype, start_t, start_dt, *extra = active_processes[idx]
                last_act = extra[0] if extra else start_t
                prev_db_cnt = extra[1] if len(extra) > 1 else 0
                last_check_t = extra[2] if len(extra) > 2 else 0.0
                if (now - last_check_t) >= 15.0:
                    counts = get_count_for_job(company, ptype, start_dt)
                    current_db_cnt = counts[2] if counts[0] is not None else None
                    if current_db_cnt is not None:
                        if current_db_cnt > prev_db_cnt:
                            last_act = now
                        active_processes[idx] = (proc, company, ptype, start_t, start_dt, last_act, max(current_db_cnt, prev_db_cnt), now)
                    else:
                        # クエリ失敗時は last_act を更新せず（ハング判定の即時誤検知を防ぐため以前の値を保持）、チェック時刻のみ更新
                        active_processes[idx] = (proc, company, ptype, start_t, start_dt, last_act, prev_db_cnt, now)
                    break  # 1回のループで1ジョブのみ検査して終了

        for idx in tuple(active_processes.keys()):
            if idx not in active_processes:
                continue
            proc, company, ptype, start_t, start_dt, *extra = active_processes[idx]
            last_act = extra[0] if extra else start_t
            if check_job_hung(last_act, now, threshold_sec=HANG_THRESHOLD_SEC):
                # 沈黙監視 (ハング検知)
                logger.error(
                    f"[{idx}] Crawl job silent/hung for {company} - {ptype} "
                    f"(no progress > {HANG_THRESHOLD_SEC}s). Killing process group..."
                )
                kill_hung_job_process(proc)
                elapsed = now - start_t
                end_dt = timezone.now() if timezone is not None else datetime.datetime.now(datetime.timezone.utc)
                duration_job_str = format_duration(int(elapsed))
                try:
                    FailureReporter.record_job_failure(
                        company=company,
                        property_type=ptype,
                        error_type="HangSilentFailure",
                        error_message=f"Process hung with no progress for {int(HANG_THRESHOLD_SEC)}s",
                        exit_code=-1,
                        duration_seconds=int(elapsed),
                        task_index=task_index,
                        task_count=task_count,
                        date_str=today_str
                    )
                except Exception as hfe:
                    logger.warning(f"Failed to record hang telemetry for {company} - {ptype}: {hfe}")

                results.append({
                    "index": idx,
                    "company": company,
                    "property_type": ptype,
                    "status": "hung_timeout",
                    "exit_code": -1,
                    "start_time": start_dt.strftime(DATETIME_FORMAT) if start_dt else "",
                    "end_time": end_dt.strftime(DATETIME_FORMAT) if end_dt else "",
                    "duration": duration_job_str,
                    "elapsed_seconds": int(elapsed),
                    "items_count": 0,
                    "error_message": f"Process hung with no progress for {int(HANG_THRESHOLD_SEC)}s"
                })
                try:
                    record_crawler_metrics(
                        site_name=company,
                        property_type=ptype,
                        count=0,
                        duration_sec=float(elapsed),
                        zero_count=True,
                        status="hung_timeout",
                        metadata={"exit_code": -1, "error_msg": f"Process hung with no progress for {int(HANG_THRESHOLD_SEC)}s"}
                    )
                except Exception as nre:
                    logger.warning(f"Failed to record New Relic metrics for {company} - {ptype}: {nre}")

                post_slack(f"❌ 【ハング検知・強制終了】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | {int(HANG_THRESHOLD_SEC)}秒間無進捗のため打ち切り")
                del active_processes[idx]

            elif timeout_sec > 0 and now - start_t > timeout_sec:
                # タイムアウト
                logger.error(f"[{idx}] Crawl job timed out for {company} - {ptype} after {timeout_sec} seconds. Killing process group...")
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGKILL)
                    proc.communicate()
                except Exception:
                    logger.exception("Failed to kill")
                
                elapsed = now - start_t
                end_dt = timezone.now() if timezone is not None else datetime.datetime.now(datetime.timezone.utc)
                duration_job_str = format_duration(int(elapsed))
                try:
                    FailureReporter.record_job_failure(
                        company=company,
                        property_type=ptype,
                        error_type="TimeoutFailure",
                        error_message=f"Timeout expired ({timeout_sec}s)",
                        exit_code=-1,
                        duration_seconds=int(elapsed),
                        task_index=task_index,
                        task_count=task_count,
                        date_str=today_str
                    )
                except Exception as tfe:
                    logging.warning(f"Failed to record timeout failure for {company} - {ptype}: {tfe}")

                results.append({
                    "index": idx,
                    "company": company,
                    "property_type": ptype,
                    "status": "timeout",
                    "exit_code": -1,
                    "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S") if start_dt else "",
                    "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt else "",
                    "duration": duration_job_str,
                    "elapsed_seconds": int(elapsed),
                    "items_count": 0,
                    "error_message": f"Timeout expired ({timeout_sec}s)"
                })

                try:
                    record_crawler_metrics(
                        site_name=company,
                        property_type=ptype,
                        count=0,
                        duration_sec=float(elapsed),
                        zero_count=True,
                        status="timeout",
                        metadata={"exit_code": -1, "error_msg": f"Timeout expired ({timeout_sec}s)"}
                    )
                except Exception as nre:
                    logger.warning(f"Failed to record New Relic timeout metrics for {company} - {ptype}: {nre}")

                post_slack(f"❌ 【タイムアウト】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | 制限時間 {timeout_sec}秒超過")
                del active_processes[idx]
        
        # 2. 新規ジョブの投入 (取扱物件数に応じた階層的並行度 & Playwright/Standard 上限で制御)
        if job_queue and len(active_processes) < args.parallel:
            active_playwright_cnt = sum(1 for proc_tuple in active_processes.values() if proc_tuple[1].lower() in PLAYWRIGHT_COMPANIES)

            # 現在実行中の会社別アクティブプロセス数を集計
            active_company_counts = {}
            for proc_tuple in active_processes.values():
                c_low = proc_tuple[1].lower()
                active_company_counts[c_low] = active_company_counts.get(c_low, 0) + 1

            job_select_res = select_next_job(
                job_queue=job_queue,
                active_company_counts=active_company_counts,
                max_playwright_parallel=args.playwright_parallel,
                current_playwright_count=active_playwright_cnt,
                playwright_companies=PLAYWRIGHT_COMPANIES,
            )

            if job_select_res is not None:
                target_idx_in_queue, _ = job_select_res
                company, ptype = job_queue.pop(target_idx_in_queue)
                idx = next_job_index
                next_job_index += 1
                
                is_pw = company.lower() in PLAYWRIGHT_COMPANIES
                logger.info(f"[{idx}/{len(CRAWL_JOBS)}] Starting crawl for {company} - {ptype} (Playwright={is_pw})...")
                cmd = [
                    sys.executable,
                    main_py_path,
                    f"--company={company}",
                    f"--type={ptype}"
                ]

                
                try:
                    # クロール開始前のタイムスタンプを保存
                    start_dt = timezone.now() if timezone is not None else None
                    # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
                    proc = subprocess.Popen(
                        cmd,
                        start_new_session=True  # replaces preexec_fn=os.setsid; safe with threads (CPython docs)
                    )
                    now_ts = time.time()
                    active_processes[idx] = (proc, company, ptype, now_ts, start_dt, now_ts)
                    AdaptiveConcurrencyController.set_active_jobs_count(len(active_processes))
                    post_slack(f"🚀 【開始】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)})")
                except Exception as e:
                    logger.exception(f"Failed to start crawl job for {company} - {ptype}")
                    results.append({
                        "index": idx,
                        "company": company,
                        "property_type": ptype,
                        "status": "error",
                        "exit_code": -1,
                        "start_time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                        "end_time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                        "duration": "0秒",
                        "elapsed_seconds": 0,
                        "items_count": 0,
                        "error_message": str(e)
                    })

                    try:
                        record_crawler_metrics(
                            site_name=company,
                            property_type=ptype,
                            count=0,
                            duration_sec=0.0,
                            zero_count=True,
                            status="error",
                            metadata={"exit_code": -1, "error_msg": str(e)}
                        )
                    except Exception as nre:
                        logger.warning(f"Failed to record New Relic error metrics for {company} - {ptype}: {nre}")
                
                # 並行起動時にPCへ一度に負荷を集中させないよう、わずかなスリープ
                time.sleep(2)
                continue

            
        time.sleep(1)
            
    # レポート保存
    batch_end_dt = datetime.datetime.now(datetime.timezone.utc)
    elapsed_delta = batch_end_dt - batch_start_dt
    duration_str = format_duration(int(elapsed_delta.total_seconds()))

    summary = {
        "timestamp": batch_end_dt.strftime(DATETIME_FORMAT),
        "start_time": batch_start_dt.strftime(DATETIME_FORMAT),
        "end_time": batch_end_dt.strftime(DATETIME_FORMAT),
        "duration": duration_str,
        "elapsed_seconds": int(elapsed_delta.total_seconds()),
        "total_jobs": len(CRAWL_JOBS),
        "success_jobs": sum(1 for r in results if r["status"] == "success"),
        "failed_jobs": sum(1 for r in results if r["status"] in ["failed", "timeout", "error", "hung_timeout"]),
        "results": results
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        
    logger.info(f"All crawl jobs finished. Report written to {report_path}")
    
    # DB にタスク完了状態を記録
    if task_exec_record is not None:
        try:
            task_exec_record.status = "COMPLETED" if summary["failed_jobs"] == 0 else "FAILED"
            task_exec_record.jobs_success = summary["success_jobs"]
            task_exec_record.jobs_failed = summary["failed_jobs"]
            task_exec_record.results_json = results
            task_exec_record.save()
            logger.info(f"✔ CrawlerTaskExecution updated: status={task_exec_record.status}, success={task_exec_record.jobs_success}, failed={task_exec_record.jobs_failed}")
        except Exception as dbe:
            logger.warning(f"Failed to update CrawlerTaskExecution finish: {dbe}")
    
    # Slack notifications for crawl statuses
    try:
        threshold_24h = timezone.now() - datetime.timedelta(hours=24)
        db_summary = []
        for model in apps.get_models():
            model_name = model.__name__
            if model_name in ["PropertyEvaluation", "Migration"] or "Potential" in model_name or model_name == "PropertyImage":
                continue
                
            company = "unknown"
            for c in ["mitsui", "sumifu", "tokyu", "nomura", "misawa", "athome", "homes", "smtrc", "sumai1", "mizuho", "sekisui", "afr", "daiwa", "totate", "odakyu", "sumirin", "keio", "seibu", "keikyu", "sotetsu", "keisei", "daikyo", "rearie", "heim"]:
                if model_name.lower().startswith(c):
                    company = c
                    break
            if company == "unknown":
                continue
                
            prop_type = model_name[len(company):].lower()
            if prop_type == "mansion":
                prop_type = "mansion"
            elif prop_type == "kodate":
                prop_type = "kodate"
            elif prop_type == "tochi":
                prop_type = "tochi"
            elif prop_type in ["investmentkodate", "investkodate"]:
                prop_type = "invest_kodate"
            elif prop_type in ["investmentapartment", "investapartment"]:
                prop_type = "invest_apartment"
            elif prop_type == "investment":
                prop_type = "investment"
                
            try:
                if hasattr(model, "updateDateTime"):
                    detail_24h = model.objects.filter(inputDateTime__gte=threshold_24h).count()
                    skip_24h = model.objects.filter(
                        Q(updateDateTime__gte=threshold_24h) & (Q(inputDateTime__lt=threshold_24h) | Q(inputDateTime__isnull=True))
                    ).count()
                    total_24h = detail_24h + skip_24h
                else:
                    detail_24h = model.objects.filter(inputDateTime__gte=threshold_24h).count()
                    skip_24h = 0
                    total_24h = detail_24h
                db_summary.append((company, prop_type, detail_24h, skip_24h, total_24h))
            except Exception:
                pass
                
        # Format Slack Message
        header_title = "📢 【クローリング実行状況レポート】"
        if task_count > 1 and task_index is not None:
            header_title = f"📢 【クローリング実行状況レポート (Task {task_index}/{task_count})】"
        msg_lines = [header_title]
        msg_lines.append(f"開始時間: {batch_start_dt.strftime(DATETIME_FORMAT)}")
        msg_lines.append(f"終了時間: {batch_end_dt.strftime(DATETIME_FORMAT)}")
        msg_lines.append(f"所要時間: {duration_str}")
        if task_count > 1 and task_index is not None:
            msg_lines.append(f"総ジョブ数: {len(CRAWL_JOBS)} (Task {task_index}/{task_count} 担当: {len(target_jobs)}, 成功: {summary['success_jobs']}, 失敗: {summary['failed_jobs']})")
        else:
            msg_lines.append(f"総ジョブ数: {len(CRAWL_JOBS)} (成功: {summary['success_jobs']}, 失敗: {summary['failed_jobs']})")
        
        # Build lookup from results for job timings
        job_timings = {}
        for r in results:
            key = (r["company"].lower(), r["property_type"].lower())
            job_timings[key] = r

        msg_lines.append("\n▼ 過去24時間の新規取得件数内訳:")
        has_new_items = False
        for comp, ptype, detail_cnt, skip_cnt, total_cnt in sorted(db_summary):
            if total_cnt > 0:
                timing = job_timings.get((comp.lower(), ptype.lower()))
                timing_str = ""
                if timing and timing.get("start_time") and timing.get("end_time"):
                    st = timing["start_time"].split(" ")[-1]
                    et = timing["end_time"].split(" ")[-1]
                    dur = timing.get("duration", format_duration(timing.get("elapsed_seconds", 0)))
                    timing_str = f" (開始: {st}, 終了: {et}, 所要: {dur})"
                item_line = format_summary_item_message(comp, ptype, detail_cnt, skip_cnt, total_cnt, timing_str)
                msg_lines.append(item_line)
                has_new_items = True
        if not has_new_items:
            msg_lines.append("• 新規取得物件なし")
            
        failed_list = [r for r in results if r["status"] in ["failed", "timeout", "error", "hung_timeout"]]
        if failed_list:
            msg_lines.append("\n⚠️ 異常が発生したクローラー:")
            for f in failed_list:
                st = f.get("start_time", "").split(" ")[-1]
                et = f.get("end_time", "").split(" ")[-1]
                dur = f.get("duration", format_duration(f.get("elapsed_seconds", 0)))
                timing_str = f" (開始: {st}, 終了: {et}, 所要: {dur})" if st and et else ""
                err_info = f" | {f['error_message']}" if f.get("error_message") else ""
                msg_lines.append(f"• {f['company']} - {f['property_type']}: {f['status']} (Code: {f['exit_code']}){timing_str}{err_info}")
            msg_lines.append(f"\n🛠️ Antigravity 一括修復コマンド:\npython src/crawler/scripts/debug_tools/fetch_run_failures.py --date {today_str}")
        else:
            msg_lines.append("\n✅ すべてのクローラーが正常終了しました。")
            
        summary_msg = "\n".join(msg_lines)
        if failed_list:
            # 異常ジョブが存在する場合はアラートとして #property_alert に警告発報
            asyncio.run(send_crawling_summary_alert(summary_msg))
        else:
            # 全件正常終了時は #dev-agent に運用レポートとして送信
            asyncio.run(send_dev_report(summary_msg))

        # 異常ジョブが存在する場合、#dev-agent 宛に @DevAgent ゼロタッチ自動修復トリガーを発信
        if failed_list:
            try:
                failed_job_tuples = [(f["company"], f["property_type"]) for f in failed_list]
                auto_heal_msg = generate_auto_heal_trigger_message(
                    date_str=today_str,
                    failed_count=len(failed_list),
                    failed_jobs=failed_job_tuples
                )
                asyncio.run(send_dev_report(auto_heal_msg))
                logger.info(f"Triggered Slack DevAgent auto-heal for {len(failed_list)} failed jobs.")
            except Exception as dte:  # noqa: BLE001
                logger.warning(f"Failed to send Slack DevAgent auto-heal trigger: {dte}")
    except Exception as ex:
        logging.exception(f"Failed to generate/send Slack crawl summary: {ex}")
        
    # monitor_error_pages.py のキック
    monitor_script = os.path.join(_project_root, "src", "crawler", "scripts", "ops", "monitor_error_pages.py")
    if os.path.exists(monitor_script):
        logging.info("Triggering monitor_error_pages.py...")
        subprocess.run([sys.executable, monitor_script])

if __name__ == "__main__":
    try:
        main()
    finally:
        shutdown_new_relic()


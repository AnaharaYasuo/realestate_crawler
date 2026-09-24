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

from django.apps import apps
from django.db.models import Q
from django.utils import timezone
from package.utils.slack import send_crawling_summary_alert
from package.utils.task_distribution import get_task_config, distribute_jobs
from package.utils.crawler_scheduler import select_next_job
from package.models.crawler_task_execution import CrawlerTaskExecution

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_args():
    """Parse CLI arguments for run_all_crawlers."""
    default_parallel = 35
    default_playwright_parallel = 3
    parser = argparse.ArgumentParser(description="Run all crawler jobs in parallel or sequentially.")
    parser.add_argument("--dry-run", action="store_true", help="Print jobs without execution.")
    parser.add_argument("--parallel", "--standard-parallel", type=int, default=default_parallel, help="Number of parallel standard crawler processes (aiohttp/http).")
    parser.add_argument("--playwright-parallel", type=int, default=default_playwright_parallel, help="Number of parallel Playwright crawler processes (high memory usage).")
    parser.add_argument("--skip-portals", action="store_true", help="Skip large portal sites (athome, homes) for fast execution.")
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




cooldown_sec = int(os.getenv("CRAWL_COOLDOWN_SEC", 180))
timeout_sec = int(os.getenv("CRAWL_TIMEOUT_SEC", 10800))

active_processes = {}

def cleanup_active_process():
    """現在アクティブなすべての子プロセスグループを安全かつ完全にキルする"""
    global active_processes
    for idx, (proc, company, ptype, start_t) in active_processes.items():
        if proc.poll() is None:
            try:
                pgid = os.getpgid(proc.pid)
                logging.info(f"親プロセスの終了を検知したため、子プロセスグループ {pgid} ({company} - {ptype}) を強制終了します...")
                os.killpg(pgid, signal.SIGKILL)
                proc.communicate()  # プロセスゾンビ化を防ぐための回収
            except Exception as e:
                logging.exception(f"子プロセスのクリーンアップ中にエラー: {e}")
    active_processes.clear()

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

    def post_slack(msg):
        try:
            asyncio.run(send_crawling_summary_alert(msg))
        except Exception as se:
            logging.exception(f"Failed to post Slack status: {se}")

    def get_count_for_job(company, ptype, start_dt):
        if apps is None or start_dt is None:
            return 0
        try:
            target = ptype.lower().replace("_", "")
            for model in apps.get_models():
                m_name = model.__name__.lower()
                if m_name.startswith(company.lower()):
                    rest = m_name[len(company):]
                    if rest == target or rest == target.replace("invest", "investment"):
                        q = Q(updateDateTime__gte=start_dt) | Q(inputDateTime__gte=start_dt) if hasattr(model, "updateDateTime") else Q(inputDateTime__gte=start_dt)
                        return model.objects.filter(q).count()
        except Exception as ce:
            logging.exception(f"Failed to get db count for {company} - {ptype}: {ce}")
        return 0

    today_str = datetime.date.today().strftime("%Y%m%d")
    report_path = os.path.join(log_dir, f"crawl_report_{today_str}.json")
    
    task_index, task_count = get_task_config()
    target_jobs = list(CRAWL_JOBS)
    if args.skip_portals:
        target_jobs = [j for j in target_jobs if j[0].lower() not in PORTAL_COMPANIES]
        logging.info(f"Skipping portal sites ({', '.join(PORTAL_COMPANIES)}). Active jobs: {len(target_jobs)}/{len(CRAWL_JOBS)}")

    if task_count > 1 and task_index is not None:
        target_jobs = distribute_jobs(target_jobs, task_index, task_count)
        logging.info(f"🎯 [Task Array] Task {task_index}/{task_count} に {len(target_jobs)} 件のジョブを割り当てました")

    # DB にタスク実行状態を登録
    task_exec_record = None
    try:
        task_exec_record, _ = CrawlerTaskExecution.objects.update_or_create(
            execution_date=datetime.date.today(),
            task_index=task_index or 0,
            defaults={
                "task_count": task_count,
                "status": "RUNNING",
                "jobs_assigned": len(target_jobs),
            }
        )
    except Exception as dbe:
        logging.warning(f"Failed to record CrawlerTaskExecution start: {dbe}")

    if task_count > 1 and task_index is not None:
        post_slack(f"🚀 【分散クローリング開始】 Task {task_index}/{task_count} を開始します。(担当 {len(target_jobs)} ジョブ)")
    else:
        post_slack(f"🚀 【クローリング開始】 一括巡回処理を開始します。(全 {len(target_jobs)} ジョブ{' [ポータル割愛]' if args.skip_portals else ''})")
    
    results = []
    job_queue = list(target_jobs)
    next_job_index = 1
    
    global active_processes

    batch_start_dt = datetime.datetime.now()

    while job_queue or active_processes:
        now = time.time()
        
        # 1. 終了プロセスの回収およびタイムアウトのキル
        active_indices = tuple(active_processes.keys())
        for idx in active_indices:
            proc, company, ptype, start_t, start_dt = active_processes[idx]
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
                if exit_code == 0:
                    scraped_cnt = get_count_for_job(company, ptype, start_dt)
                    if scraped_cnt > 0:
                        post_slack(f"✅ 【成功】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | 新規取得: {scraped_cnt} 件 | 処理時間: {duration_job_str}")
                    else:
                        status = "failed"
                        error_msg = "0 items scraped (Zero count failure)"
                        post_slack(f"❌ 【失敗: 0件取得】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | 新規取得: 0 件 | 処理時間: {duration_job_str} (データが1件も取得できていません)")
                else:
                    post_slack(f"❌ 【失敗】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | Exit Code: {exit_code} | 処理時間: {duration_job_str}")

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
                    "error_message": error_msg
                })

                del active_processes[idx]
                
            elif timeout_sec > 0 and now - start_t > timeout_sec:
                # タイムアウト
                logging.error(f"[{idx}] Crawl job timed out for {company} - {ptype} after {timeout_sec} seconds. Killing process group...")
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGKILL)
                    proc.communicate()
                except Exception as ke:
                    logging.exception(f"Failed to kill: {ke}")
                
                elapsed = now - start_t
                end_dt = timezone.now() if timezone is not None else datetime.datetime.now()
                duration_job_str = format_duration(int(elapsed))
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
                post_slack(f"❌ 【タイムアウト】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | 制限時間 {timeout_sec}秒超過")
                del active_processes[idx]
        
        # 2. 新規ジョブの投入 (取扱物件数に応じた階層的並行度 & Playwright/Standard 上限で制御)
        if job_queue and len(active_processes) < args.parallel:
            active_playwright_cnt = sum(1 for _, c, _, _, _ in active_processes.values() if c.lower() in PLAYWRIGHT_COMPANIES)

            # 現在実行中の会社別アクティブプロセス数を集計
            active_company_counts = {}
            for _, c, _, _, _ in active_processes.values():
                c_low = c.lower()
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
                logging.info(f"[{idx}/{len(CRAWL_JOBS)}] Starting crawl for {company} - {ptype} (Playwright={is_pw})...")
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
                        preexec_fn=os.setsid
                    )
                    active_processes[idx] = (proc, company, ptype, time.time(), start_dt)
                    post_slack(f"🚀 【開始】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)})")
                except Exception as e:
                    logging.exception(f"Failed to start crawl job for {company} - {ptype}: {e}")
                    results.append({
                        "index": idx,
                        "company": company,
                        "property_type": ptype,
                        "status": "error",
                        "exit_code": -1,
                        "start_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "end_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "duration": "0秒",
                        "elapsed_seconds": 0,
                        "items_count": 0,
                        "error_message": str(e)
                    })
                
                # 並行起動時にPCへ一度に負荷を集中させないよう、わずかなスリープ
                time.sleep(2)
                continue

            
        time.sleep(1)
            
    # レポート保存
    batch_end_dt = datetime.datetime.now()
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
        "failed_jobs": sum(1 for r in results if r["status"] in ["failed", "timeout", "error"]),
        "results": results
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        
    logging.info(f"All crawl jobs finished. Report written to {report_path}")
    
    # DB にタスク完了状態を記録
    if task_exec_record is not None:
        try:
            task_exec_record.status = "COMPLETED" if summary["failed_jobs"] == 0 else "FAILED"
            task_exec_record.jobs_success = summary["success_jobs"]
            task_exec_record.jobs_failed = summary["failed_jobs"]
            task_exec_record.save()
            logging.info(f"✔ CrawlerTaskExecution updated: status={task_exec_record.status}, success={task_exec_record.jobs_success}, failed={task_exec_record.jobs_failed}")
        except Exception as dbe:
            logging.warning(f"Failed to update CrawlerTaskExecution finish: {dbe}")
    
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
                q = Q(updateDateTime__gte=threshold_24h) | Q(inputDateTime__gte=threshold_24h) if hasattr(model, "updateDateTime") else Q(inputDateTime__gte=threshold_24h)
                count_24h = model.objects.filter(q).count()
                db_summary.append((company, prop_type, count_24h))
            except Exception:
                pass
                
        # Format Slack Message
        msg_lines = ["📢 【クローリング実行状況レポート】"]
        msg_lines.append(f"開始時間: {batch_start_dt.strftime(DATETIME_FORMAT)}")
        msg_lines.append(f"終了時間: {batch_end_dt.strftime(DATETIME_FORMAT)}")
        msg_lines.append(f"所要時間: {duration_str}")
        msg_lines.append(f"総ジョブ数: {len(CRAWL_JOBS)} (成功: {summary['success_jobs']}, 失敗: {summary['failed_jobs']})")
        
        # Build lookup from results for job timings
        job_timings = {}
        for r in results:
            key = (r["company"].lower(), r["property_type"].lower())
            job_timings[key] = r

        msg_lines.append("\n▼ 過去24時間の新規取得件数内訳:")
        has_new_items = False
        for comp, ptype, cnt in sorted(db_summary):
            if cnt > 0:
                timing = job_timings.get((comp.lower(), ptype.lower()))
                timing_str = ""
                if timing and timing.get("start_time") and timing.get("end_time"):
                    st = timing["start_time"].split(" ")[-1]
                    et = timing["end_time"].split(" ")[-1]
                    dur = timing.get("duration", format_duration(timing.get("elapsed_seconds", 0)))
                    timing_str = f" (開始: {st}, 終了: {et}, 所要: {dur})"
                msg_lines.append(f"• {comp} - {ptype}: {cnt} 件{timing_str}")
                has_new_items = True
        if not has_new_items:
            msg_lines.append("• 新規取得物件なし")
            
        failed_list = [r for r in results if r["status"] in ["failed", "timeout", "error"]]
        if failed_list:
            msg_lines.append("\n⚠️ 異常が発生したクローラー:")
            for f in failed_list:
                st = f.get("start_time", "").split(" ")[-1]
                et = f.get("end_time", "").split(" ")[-1]
                dur = f.get("duration", format_duration(f.get("elapsed_seconds", 0)))
                timing_str = f" (開始: {st}, 終了: {et}, 所要: {dur})" if st and et else ""
                msg_lines.append(f"• {f['company']} - {f['property_type']}: {f['status']} (Code: {f['exit_code']}){timing_str}")
        else:
            msg_lines.append("\n✅ すべてのクローラーが正常終了しました。")
            
        asyncio.run(send_crawling_summary_alert("\n".join(msg_lines)))
    except Exception as ex:
        logging.exception(f"Failed to generate/send Slack crawl summary: {ex}")
        
    # monitor_error_pages.py のキック
    monitor_script = os.path.join(_project_root, "src", "crawler", "scripts", "monitor_error_pages.py")
    if os.path.exists(monitor_script):
        logging.info("Triggering monitor_error_pages.py...")
        subprocess.run([sys.executable, monitor_script])

if __name__ == "__main__":
    main()


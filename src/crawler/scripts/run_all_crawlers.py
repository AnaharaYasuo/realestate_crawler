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

# # CLI 引数のパース
cpu_count = os.cpu_count() or 2
default_parallel = max(1, min(12, cpu_count))
parser = argparse.ArgumentParser(description="Run all crawler jobs in parallel or sequentially.")
parser.add_argument("--dry-run", action="store_true", help="Print jobs without execution.")
parser.add_argument("--parallel", type=int, default=default_parallel, help="Number of parallel crawler processes.")
args = parser.parse_args()

# ロギング設定
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
log_dir = os.path.join(_project_root, "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(log_dir, "scheduler.log"), encoding="utf-8")
    ]
)

# 定義済みの全クロールジョブリスト
CRAWL_JOBS = [
    # 主要5社 (居住用)
    ("mitsui", "mansion"), ("mitsui", "kodate"), ("mitsui", "tochi"),
    ("sumifu", "mansion"), ("sumifu", "kodate"), ("sumifu", "tochi"),
    ("tokyu", "mansion"), ("tokyu", "kodate"), ("tokyu", "tochi"),
    ("nomura", "mansion"), ("nomura", "kodate"), ("nomura", "tochi"),
    ("misawa", "mansion"), ("misawa", "kodate"), ("misawa", "tochi"),
    
    # 信託・銀行系列3社 (居住用)
    ("smtrc", "mansion"), ("smtrc", "kodate"), ("smtrc", "tochi"),
    ("sumai1", "mansion"), ("sumai1", "kodate"), ("sumai1", "tochi"),
    ("mizuho", "mansion"), ("mizuho", "kodate"), ("mizuho", "tochi"),

    # 電鉄・ハウスメーカー・その他系列 (居住用)
    ("sekisui", "mansion"), ("sekisui", "kodate"), ("sekisui", "tochi"),
    ("afr", "mansion"), ("afr", "kodate"), ("afr", "tochi"),
    ("daiwa", "mansion"), ("daiwa", "kodate"), ("daiwa", "tochi"),
    ("totate", "mansion"), ("totate", "kodate"), ("totate", "tochi"),
    ("odakyu", "mansion"), ("odakyu", "kodate"), ("odakyu", "tochi"),
    ("sumirin", "mansion"), ("sumirin", "kodate"), ("sumirin", "tochi"),
    ("heim", "mansion"), ("heim", "kodate"), ("heim", "tochi"),
    ("rearie", "mansion"), ("rearie", "kodate"), ("rearie", "tochi"),
    ("keio", "mansion"), ("keio", "kodate"), ("keio", "tochi"),
    ("seibu", "mansion"), ("seibu", "kodate"), ("seibu", "tochi"),
    ("keikyu", "mansion"), ("keikyu", "kodate"), ("keikyu", "tochi"),
    ("sotetsu", "mansion"), ("sotetsu", "kodate"), ("sotetsu", "tochi"),
    ("keisei", "mansion"), ("keisei", "kodate"), ("keisei", "tochi"),
    ("daikyo", "mansion"), ("daikyo", "kodate"), ("daikyo", "tochi"),

    # ポータルサイト (居住用)
    ("athome", "mansion"), ("athome", "kodate"), ("athome", "tochi"),
    ("homes", "mansion"), ("homes", "kodate"), ("homes", "tochi"),

    # 投資用・事業用物件
    ("mitsui", "invest_kodate"), ("mitsui", "invest_apartment"),
    ("sumifu", "invest_kodate"), ("sumifu", "invest_apartment"),
    ("tokyu", "invest_kodate"), ("tokyu", "invest_apartment"),
    ("nomura", "invest_kodate"), ("nomura", "invest_apartment"),
    ("misawa", "invest_kodate"), ("misawa", "invest_apartment"),
    ("athome", "invest_apartment"),
    ("homes", "invest_apartment"),
    ("smtrc", "investment"),
    ("sumai1", "investment"),
    ("mizuho", "investment"),
    ("odakyu", "investment"),
    ("sumirin", "investment"),
]




cooldown_sec = int(os.getenv("CRAWL_COOLDOWN_SEC", 180))
timeout_sec = int(os.getenv("CRAWL_TIMEOUT_SEC", 1800))

active_processes = {}

def cleanup_active_process():
    """現在アクティブなすべての子プロセスグループを安全かつ完全にキルする"""
    global active_processes
    for idx, (proc, company, ptype, start_t) in list(active_processes.items()):
        if proc.poll() is None:
            try:
                pgid = os.getpgid(proc.pid)
                logging.info(f"親プロセスの終了を検知したため、子プロセスグループ {pgid} ({company} - {ptype}) を強制終了します...")
                os.killpg(pgid, signal.SIGKILL)
                proc.communicate()  # プロセスゾンビ化を防ぐための回収
            except Exception as e:
                logging.error(f"子プロセスのクリーンアップ中にエラー: {e}")
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
    if not os.path.exists('/proc'):
        return
    for name in os.listdir('/proc'):
        if not name.isdigit():
            continue
        pid = int(name)
        if pid == my_pid:
            continue
        try:
            with open(os.path.join('/proc', name, 'cmdline'), 'r') as f:
                cmdline = f.read().replace('\x00', ' ')
            if ('run_all_crawlers.py' in cmdline or 'main.py' in cmdline) and ('--company=' in cmdline or 'run_all_crawlers.py' in cmdline):
                logging.info(f"残留プロセスを検知: PID {pid} ({cmdline.strip()})")
                os.kill(pid, signal.SIGKILL)
                cleaned += 1
        except Exception:
            pass
    if cleaned > 0:
        logging.info(f"過去のゾンビプロセス {cleaned} 件を一掃しました。")

def main():
    if args.dry_run:
        logging.info("--- Dry Run Mode: List of Crawling Jobs ---")
        for i, (company, ptype) in enumerate(CRAWL_JOBS, 1):
            logging.info(f"{i:02d}. Company: {company}, Type: {ptype}")
        logging.info("Dry run finished.")
        return

    # 起動時にゾンビプロセスを自動一掃
    clean_zombies()

    # Django Settings Initialization for DB queries & Slack status alerts
    apps = None
    timezone = None
    try:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import realestateSettings
        realestateSettings.configure()
        from django.apps import apps
        from django.utils import timezone
        from package.utils.slack import send_crawling_summary_alert
        import asyncio
    except Exception as e:
        logging.error(f"Failed to initialize Django for Slack status reporting: {e}")


    def post_slack(msg):
        if apps is not None:
            try:
                asyncio.run(send_crawling_summary_alert(msg))
            except Exception as se:
                logging.error(f"Failed to post Slack status: {se}")

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
                        return model.objects.filter(inputDateTime__gte=start_dt).count()
        except Exception as ce:
            logging.error(f"Failed to get db count for {company} - {ptype}: {ce}")
        return 0

    today_str = datetime.date.today().strftime("%Y%m%d")
    report_path = os.path.join(log_dir, f"crawl_report_{today_str}.json")
    
    logging.info(f"Starting run_all_crawlers.py script in parallel mode (Max parallel={args.parallel})...")
    
    results = []
    job_queue = list(CRAWL_JOBS)
    next_job_index = 1
    
    global active_processes

    while job_queue or active_processes:
        now = time.time()
        
        # 1. 終了プロセスの回収およびタイムアウトのキル
        for idx, (proc, company, ptype, start_t, start_dt) in list(active_processes.items()):
            poll_status = proc.poll()
            if poll_status is not None:
                # 正常・異常終了の回収
                exit_code = proc.returncode
                status = "success" if exit_code == 0 else "failed"
                error_msg = "" if exit_code == 0 else f"Job exited with code {exit_code}"
                elapsed = now - start_t
                
                logging.info(f"[{idx}] Crawl job finished for {company} - {ptype}. Status: {status}, Code: {exit_code}, Time: {int(elapsed)}s")
                results.append({
                    "index": idx,
                    "company": company,
                    "property_type": ptype,
                    "status": status,
                    "exit_code": exit_code,
                    "elapsed_seconds": int(elapsed),
                    "error_message": error_msg
                })
                
                if exit_code == 0:
                    scraped_cnt = get_count_for_job(company, ptype, start_dt)
                    post_slack(f"✅ 【成功】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | 新規取得: {scraped_cnt} 件 | 処理時間: {int(elapsed)}秒")
                else:
                    post_slack(f"❌ 【失敗】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | Exit Code: {exit_code} | 処理時間: {int(elapsed)}秒")
                    
                del active_processes[idx]
                
            elif timeout_sec > 0 and now - start_t > timeout_sec:
                # タイムアウト
                logging.error(f"[{idx}] Crawl job timed out for {company} - {ptype} after {timeout_sec} seconds. Killing process group...")
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGKILL)
                    proc.communicate()
                except Exception as ke:
                    logging.error(f"Failed to kill: {ke}")
                
                elapsed = now - start_t
                results.append({
                    "index": idx,
                    "company": company,
                    "property_type": ptype,
                    "status": "timeout",
                    "exit_code": -1,
                    "elapsed_seconds": int(elapsed),
                    "error_message": f"Timeout expired ({timeout_sec}s)"
                })
                post_slack(f"❌ 【タイムアウト】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)}) | 制限時間 {timeout_sec}秒超過")
                del active_processes[idx]
        
        # 2. 新規ジョブの投入
        if job_queue and len(active_processes) < args.parallel:
            company, ptype = job_queue.pop(0)
            idx = next_job_index
            next_job_index += 1
            
            logging.info(f"[{idx}/{len(CRAWL_JOBS)}] Starting crawl for {company} - {ptype}...")
            cmd = [
                sys.executable,
                os.path.join(_project_root, "src", "crawler", "main.py"),
                f"--company={company}",
                f"--type={ptype}"
            ]
            
            try:
                # クロール開始前のタイムスタンプを保存
                start_dt = timezone.now() if timezone is not None else None
                proc = subprocess.Popen(
                    cmd,
                    preexec_fn=os.setsid
                )
                active_processes[idx] = (proc, company, ptype, time.time(), start_dt)
                post_slack(f"🚀 【開始】 {company} - {ptype} (Job {idx}/{len(CRAWL_JOBS)})")
            except Exception as e:
                logging.error(f"Failed to start crawl job for {company} - {ptype}: {e}")
                results.append({
                    "index": idx,
                    "company": company,
                    "property_type": ptype,
                    "status": "error",
                    "exit_code": -1,
                    "elapsed_seconds": 0,
                    "error_message": str(e)
                })
            
            # 並行起動時にPCへ一度に負荷を集中させないよう、わずかなスリープ
            time.sleep(2)
            continue
            
        time.sleep(1)
            
    # レポート保存
    summary = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_jobs": len(CRAWL_JOBS),
        "success_jobs": sum(1 for r in results if r["status"] == "success"),
        "failed_jobs": sum(1 for r in results if r["status"] in ["failed", "timeout", "error"]),
        "results": results
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        
    logging.info(f"All crawl jobs finished. Report written to {report_path}")
    
    # Slack notifications for crawl statuses
    try:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import realestateSettings
        realestateSettings.configure()
        from django.apps import apps
        from django.utils import timezone
        from package.utils.slack import send_crawling_summary_alert
        import asyncio
        
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
                count_24h = model.objects.filter(inputDateTime__gte=threshold_24h).count()
                db_summary.append((company, prop_type, count_24h))
            except Exception:
                pass
                
        # Format Slack Message
        msg_lines = ["📢 【クローリング実行状況レポート】"]
        msg_lines.append(f"日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        msg_lines.append(f"総ジョブ数: {len(CRAWL_JOBS)} (成功: {summary['success_jobs']}, 失敗: {summary['failed_jobs']})")
        
        msg_lines.append("\n▼ 過去24時間の新規取得件数内訳:")
        has_new_items = False
        for comp, ptype, cnt in sorted(db_summary):
            if cnt > 0:
                msg_lines.append(f"• {comp} - {ptype}: {cnt} 件")
                has_new_items = True
        if not has_new_items:
            msg_lines.append("• 新規取得物件なし")
            
        failed_list = [r for r in results if r["status"] in ["failed", "timeout", "error"]]
        if failed_list:
            msg_lines.append("\n⚠️ 異常が発生したクローラー:")
            for f in failed_list:
                msg_lines.append(f"• {f['company']} - {f['property_type']}: {f['status']} (Code: {f['exit_code']})")
        else:
            msg_lines.append("\n✅ すべてのクローラーが正常終了しました。")
            
        asyncio.run(send_crawling_summary_alert("\n".join(msg_lines)))
    except Exception as ex:
        logging.error(f"Failed to generate/send Slack crawl summary: {ex}")
        
    # monitor_error_pages.py のキック
    monitor_script = os.path.join(_project_root, "src", "crawler", "scripts", "monitor_error_pages.py")
    if os.path.exists(monitor_script):
        logging.info("Triggering monitor_error_pages.py...")
        subprocess.run([sys.executable, monitor_script])

if __name__ == "__main__":
    main()


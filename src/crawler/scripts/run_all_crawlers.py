# -*- coding: utf-8 -*-
import os
import sys
import time
import subprocess
import logging
import datetime
import argparse
import json

# # CLI 引数のパース
parser = argparse.ArgumentParser(description="Run all crawler jobs in parallel or sequentially.")
parser.add_argument("--dry-run", action="store_true", help="Print jobs without execution.")
parser.add_argument("--parallel", type=int, default=1, help="Number of parallel crawler processes.")
args = parser.parse_args()

# ロギング設定
log_dir = "/app/logs"
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

    # 投資用・事業用物件
    ("mitsui", "invest_kodate"), ("mitsui", "invest_apartment"),
    ("sumifu", "invest_kodate"), ("sumifu", "invest_apartment"),
    ("tokyu", "invest_kodate"), ("tokyu", "invest_apartment"),
    ("nomura", "invest_kodate"), ("nomura", "invest_apartment"),
    ("misawa", "invest_kodate"), ("misawa", "invest_apartment"),
    ("smtrc", "investment"),
    ("sumai1", "investment"),
    ("mizuho", "investment"),
    ("odakyu", "investment"),
    ("sumirin", "investment"),
]

import signal
import atexit

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
        for idx, (proc, company, ptype, start_t) in list(active_processes.items()):
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
                del active_processes[idx]
                
            elif now - start_t > timeout_sec:
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
                del active_processes[idx]
        
        # 2. 新規ジョブの投入
        if job_queue and len(active_processes) < args.parallel:
            company, ptype = job_queue.pop(0)
            idx = next_job_index
            next_job_index += 1
            
            logging.info(f"[{idx}/{len(CRAWL_JOBS)}] Starting crawl for {company} - {ptype}...")
            cmd = [
                sys.executable,
                "/app/src/crawler/main.py",
                f"--company={company}",
                f"--type={ptype}"
            ]
            
            try:
                proc = subprocess.Popen(
                    cmd,
                    preexec_fn=os.setsid
                )
                active_processes[idx] = (proc, company, ptype, time.time())
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
    
    # monitor_error_pages.py のキック
    monitor_script = "/app/src/crawler/scripts/monitor_error_pages.py"
    if os.path.exists(monitor_script):
        logging.info("Triggering monitor_error_pages.py...")
        subprocess.run([sys.executable, monitor_script])

if __name__ == "__main__":
    main()

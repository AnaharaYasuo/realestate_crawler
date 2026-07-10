# -*- coding: utf-8 -*-
import os
import sys
import time
import subprocess
import logging
import datetime
import argparse
import json

# CLI 引数のパース
parser = argparse.ArgumentParser(description="Run all crawler jobs sequentially.")
parser.add_argument("--dry-run", action="store_true", help="Print jobs without execution.")
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

# 定義済みの全クロールジョブリスト (5社 × 最大6種別)
CRAWL_JOBS = [
    ("mitsui", "mansion"), ("mitsui", "kodate"), ("mitsui", "tochi"),
    ("sumifu", "mansion"), ("sumifu", "kodate"), ("sumifu", "tochi"),
    ("tokyu", "mansion"), ("tokyu", "kodate"), ("tokyu", "tochi"),
    ("nomura", "mansion"), ("nomura", "kodate"), ("nomura", "tochi"),
    ("misawa", "mansion"), ("misawa", "kodate"), ("misawa", "tochi"),
    
    ("mitsui", "invest_kodate"), ("mitsui", "invest_apartment"),
    ("sumifu", "invest_kodate"), ("sumifu", "invest_apartment"),
    ("tokyu", "invest_kodate"), ("tokyu", "invest_apartment"),
    ("nomura", "invest_kodate"), ("nomura", "invest_apartment"),
    ("misawa", "invest_kodate"), ("misawa", "invest_apartment"),
]

cooldown_sec = int(os.getenv("CRAWL_COOLDOWN_SEC", 180))
timeout_sec = int(os.getenv("CRAWL_TIMEOUT_SEC", 1800))

def main():
    if args.dry_run:
        logging.info("--- Dry Run Mode: List of Crawling Jobs ---")
        for i, (company, ptype) in enumerate(CRAWL_JOBS, 1):
            logging.info(f"{i:02d}. Company: {company}, Type: {ptype}")
        logging.info("Dry run finished.")
        return

    today_str = datetime.date.today().strftime("%Y%m%d")
    report_path = os.path.join(log_dir, f"crawl_report_{today_str}.json")
    
    logging.info("Starting run_all_crawlers.py script...")
    
    results = []
    
    for i, (company, ptype) in enumerate(CRAWL_JOBS, 1):
        logging.info(f"[{i}/{len(CRAWL_JOBS)}] Starting crawl for {company} - {ptype}...")
        start_time = time.time()
        
        # main.py の CLI 実行
        cmd = [
            sys.executable,
            "/app/src/crawler/main.py",
            f"--company={company}",
            f"--type={ptype}"
        ]
        
        status = "success"
        exit_code = 0
        error_msg = ""
        
        try:
            res = subprocess.run(cmd, timeout=timeout_sec, capture_output=True, text=True, encoding="utf-8")
            exit_code = res.returncode
            if exit_code != 0:
                status = "failed"
                error_msg = res.stderr
                logging.error(f"Crawl job failed with code {exit_code}: {res.stderr}")
            else:
                logging.info(f"Crawl job succeeded for {company} - {ptype}")
        except subprocess.TimeoutExpired as e:
            status = "timeout"
            logging.error(f"Crawl job timed out after {timeout_sec} seconds")
            error_msg = str(e)
        except Exception as e:
            status = "error"
            logging.error(f"Crawl job error: {e}")
            error_msg = str(e)
            
        elapsed = time.time() - start_time
        
        job_result = {
            "index": i,
            "company": company,
            "property_type": ptype,
            "status": status,
            "exit_code": exit_code,
            "elapsed_seconds": int(elapsed),
            "error_message": error_msg[:1000] # Truncate long logs
        }
        results.append(job_result)
        
        # クールダウン
        if i < len(CRAWL_JOBS):
            logging.info(f"Cooling down for {cooldown_sec} seconds before next job...")
            time.sleep(cooldown_sec)
            
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

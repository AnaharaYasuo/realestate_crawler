# -*- coding: utf-8 -*-
import os
import re
import datetime
import json
import logging
import sys

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

ERROR_DIRS = [
    "/app/src/crawler/tests/error_pages",
    "/app/docs/error_pages"
]

def parse_meta_file(meta_path):
    info = {"url": "unknown", "reason": "unknown", "timestamp": "unknown"}
    if not os.path.exists(meta_path):
        return info
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("URL:"):
                    info["url"] = line.split("URL:", 1)[1].strip()
                elif line.startswith("Reason:"):
                    info["reason"] = line.split("Reason:", 1)[1].strip()
                elif line.startswith("Timestamp:"):
                    info["timestamp"] = line.split("Timestamp:", 1)[1].strip()
    except Exception as e:
        logging.error(f"Failed to parse meta file {meta_path}: {e}")
    return info

def main():
    logging.info("Starting monitor_error_pages.py...")
    
    # 過去24時間に発生したエラーを集計
    now = datetime.datetime.now()
    one_day_ago = now - datetime.timedelta(days=1)
    
    error_summary = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_errors": 0,
        "recent_errors_24h": 0,
        "by_company_type": {},
        "recent_details": []
    }
    
    for base_dir in ERROR_DIRS:
        if not os.path.exists(base_dir):
            continue
            
        for company_type in os.listdir(base_dir):
            comp_path = os.path.join(base_dir, company_type)
            if not os.path.isdir(comp_path):
                continue
                
            if company_type not in error_summary["by_company_type"]:
                error_summary["by_company_type"][company_type] = {
                    "total": 0,
                    "recent_24h": 0
                }
                
            for filename in os.listdir(comp_path):
                if not filename.endswith(".html"):
                    continue
                    
                file_path = os.path.join(comp_path, filename)
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                
                is_recent = mtime >= one_day_ago
                
                # メタ情報の取得
                meta_filename = filename.replace(".html", "_meta.txt")
                meta_path = os.path.join(comp_path, meta_filename)
                
                meta_info = parse_meta_file(meta_path)
                if meta_info["timestamp"] == "unknown":
                    meta_info["timestamp"] = mtime.strftime("%Y-%m-%d %H:%M:%S")
                
                error_summary["total_errors"] += 1
                error_summary["by_company_type"][company_type]["total"] += 1
                
                if is_recent:
                    error_summary["recent_errors_24h"] += 1
                    error_summary["by_company_type"][company_type]["recent_24h"] += 1
                    
                    error_summary["recent_details"].append({
                        "company_type": company_type,
                        "file": filename,
                        "url": meta_info["url"],
                        "reason": meta_info["reason"],
                        "timestamp": meta_info["timestamp"]
                    })
                    
    today_str = datetime.date.today().strftime("%Y%m%d")
    report_path = os.path.join(log_dir, f"error_report_{today_str}.json")
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(error_summary, f, ensure_ascii=False, indent=2)
        
    logging.info(f"Error monitoring finished. Report written to {report_path}")
    logging.info(f"Total Errors: {error_summary['total_errors']}, Recent (24h): {error_summary['recent_errors_24h']}")
    
    # 警告閾値の判定 (直近24時間で5件以上あれば警告)
    alert_threshold = int(os.getenv("ERROR_ALERT_THRESHOLD", 5))
    if error_summary["recent_errors_24h"] >= alert_threshold:
        logging.warning(f"⚠️ ALERT: {error_summary['recent_errors_24h']} parse errors detected in the last 24 hours!")
        for detail in error_summary["recent_details"]:
            logging.warning(f"  - [{detail['company_type']}] Reason: {detail['reason']} | URL: {detail['url']}")

if __name__ == "__main__":
    main()

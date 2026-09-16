# -*- coding: utf-8 -*-
import os
import datetime
import json
import logging
import sys
import subprocess

# ロギング設定
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
log_dir = os.path.join(_project_root, "logs")
os.makedirs(log_dir, exist_ok=True)

ERROR_DIRS = [
    os.path.join(_project_root, "docs", "error_pages")
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
    logging.info("Starting monitor_error_pages.py (optimized with linux find)...")
    
    now = datetime.datetime.now()
    
    error_summary = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_errors": 0,
        "recent_errors_24h": 0,
        "by_company_type": {},
        "recent_details": []
    }
    
    recent_files = []
    
    # 1. find コマンドで直近24時間(1440分)以内に更新された HTML ファイル一覧を瞬時に取得 (I/O遅延対策)
    for base_dir in ERROR_DIRS:
        if not os.path.exists(base_dir):
            continue
            
        try:
            res = subprocess.run(
                ["find", base_dir, "-mmin", "-1440", "-name", "*.html"],
                capture_output=True, text=True, check=True
            )
            for path in res.stdout.splitlines():
                if path.strip():
                    recent_files.append(path.strip())
        except Exception as e:
            logging.error(f"Failed to run find command in {base_dir}: {e}")
            
    # 2. 直近エラーの詳細をパース
    for file_path in recent_files:
        comp_path = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        company_type = os.path.basename(comp_path)
        
        if company_type not in error_summary["by_company_type"]:
            error_summary["by_company_type"][company_type] = {
                "total": 0,
                "recent_24h": 0
            }
            
        meta_filename = filename.replace(".html", "_meta.txt")
        meta_path = os.path.join(comp_path, meta_filename)
        
        meta_info = parse_meta_file(meta_path)
        if meta_info["timestamp"] == "unknown":
            try:
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                meta_info["timestamp"] = mtime.strftime("%Y-%m-%d %H:%M:%S")
            except:
                meta_info["timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
                
        error_summary["recent_errors_24h"] += 1
        error_summary["by_company_type"][company_type]["recent_24h"] += 1
        
        error_summary["recent_details"].append({
            "company_type": company_type,
            "file": filename,
            "url": meta_info["url"],
            "reason": meta_info["reason"],
            "timestamp": meta_info["timestamp"]
        })
        
    # 3. 全体の累積エラー数も find で一瞬で集計する
    for base_dir in ERROR_DIRS:
        if not os.path.exists(base_dir):
            continue
        try:
            res_total = subprocess.run(
                ["find", base_dir, "-name", "*.html"],
                capture_output=True, text=True, check=True
            )
            all_files = [p for p in res_total.stdout.splitlines() if p.strip()]
            error_summary["total_errors"] += len(all_files)
            for path in all_files:
                comp = os.path.basename(os.path.dirname(path))
                if comp not in error_summary["by_company_type"]:
                    error_summary["by_company_type"][comp] = {"total": 0, "recent_24h": 0}
                error_summary["by_company_type"][comp]["total"] += 1
        except Exception as e:
            logging.error(f"Failed to count total error files: {e}")
            
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
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(log_dir, "error_monitor.log"), encoding="utf-8")
        ]
    )
    # monitor_error_pagesのインポートパス解決のため、カレントディレクトリをscriptsに合わせる
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)
    main()


import json
import os
import datetime
import logging
from pathlib import Path

class CrawlerReporter:
    REPORT_DIR = Path("logs/reports")

    @classmethod
    def _get_report_path(cls):
        cls.REPORT_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.date.today().strftime("%Y%m%d")
        return cls.REPORT_DIR / f"crawl_report_{date_str}.json"

    @classmethod
    def log_result(cls, url, status, model, error=None):
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "url": url,
            "status": status,
            "model": model,
            "error": str(error) if error else None
        }
        
        # Append mode to JSON (JSON Lines format for appendability)
        try:
            with open(cls._get_report_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logging.error(f"Failed to write to report: {e}")

    @classmethod
    def success(cls, url, model):
        cls.log_result(url, "SUCCESS", model)

    @classmethod
    def failure(cls, url, model, error):
        cls.log_result(url, "FAILURE", model, error)
        logging.error(f"CRAWLER FAILURE [{model}] {url}: {error}")


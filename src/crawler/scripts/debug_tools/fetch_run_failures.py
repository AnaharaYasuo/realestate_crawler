"""CLI script for bulk retrieving crawling failure telemetry."""
import argparse
import datetime
import json
import os
import sys

_current_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.dirname(_current_dir)
_crawler_dir = os.path.dirname(_scripts_dir)
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

import setup_env  # noqa: F401
from package.utils.failure_reporter import FailureReporter


def main():
    parser = argparse.ArgumentParser(description="Fetch all crawling failure telemetry from GCS/storage for a given date.")
    default_date = datetime.datetime.now(datetime.timezone.utc).date().strftime("%Y%m%d")
    parser.add_argument("--date", type=str, default=default_date, help="Target date YYYYMMDD")
    parser.add_argument("--summary", action="store_true", help="Print readable summary instead of raw JSON")
    args = parser.parse_args()

    manifest = FailureReporter.fetch_daily_failures(date_str=args.date)

    if manifest.get("total_failures", 0) == 0 and manifest.get("storage_error"):
        print(
            f"ERROR: Failed to retrieve telemetry from storage ({manifest.get('storage_error')}) "
            "and no local fallback records exist.",
            file=sys.stderr
        )
        sys.exit(1)

    if args.summary:
        print(f"=== Crawling Failures Summary for {manifest['date']} ===")
        print(f"Total Telemetry Failures: {manifest['total_failures']}")
        print(f"Total Log Errors (ERROR/CRITICAL): {manifest.get('total_log_errors', 0)}")
        for idx, f in enumerate(manifest['failures'], 1):
            print(f"\n[{idx}] {f.get('company')} - {f.get('property_type')}")
            print(f"    Error: {f.get('error_type')} - {f.get('error_message')}")
            print(f"    URL: {f.get('target_url') or 'N/A'}")
            print(f"    Parser: {f.get('parser_file')}")
            print(f"    Raw HTML: {f.get('gcs_html_path') or 'N/A'}")
        if manifest.get("log_errors"):
            print("\n=== Parsed Log File Errors ===")
            for idx, le in enumerate(manifest["log_errors"], 1):
                print(f"[{idx}] ({le['level']}) {le['file_path']}:{le['line_number']} - {le['log_entry']}")
    else:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

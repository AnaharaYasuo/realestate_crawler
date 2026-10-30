#!/usr/bin/env python3
"""Verify 10-point site wiring across crawler, dispatcher, tasks, and ML pipeline."""
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[4]
    crawler_dir = repo_root / "src" / "crawler"
    if str(crawler_dir) not in sys.path:
        sys.path.insert(0, str(crawler_dir))

    from package.site_registry import verify_all_registered_sites

    report = verify_all_registered_sites()
    if report["missing"]:
        print("WIRING ERRORS DETECTED:")
        for err in report["missing"]:
            print(f"  - {err}")
        return 1
    print(f"ALL SITES WIRED CLEANLY: {report['total_sites']} companies / {report['total_jobs']} jobs verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

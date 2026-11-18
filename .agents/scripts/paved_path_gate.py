#!/usr/bin/env python3
"""Paved Path & Deterministic Anchor Pipeline (Chapter 23 & 24).

Runs preflight checks (PYTHONPATH / worktree check) and deterministic anchors
(pytest, architecture harness) sequentially, failing fast on the first error.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable


def _default_runner(cmd: list[str]) -> int:
    env = os.environ.copy()
    crawler_dir = str(Path.cwd() / "src" / "crawler")
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in [crawler_dir, env.get("PYTHONPATH", "")] if p
    )
    return subprocess.run(cmd, env=env, check=False).returncode


def run_gate(
    repo_root: Path,
    runner: Callable[[list[str]], int] = _default_runner,
    skip_preflight: bool = False,
) -> int:
    if not skip_preflight:
        crawler_dir = repo_root / "src" / "crawler"
        if not crawler_dir.exists():
            print(f"[PREFLIGHT FAIL] Missing {crawler_dir}", file=sys.stderr)
            return 2

    anchors: list[list[str]] = [
        [sys.executable, "-m", "pytest", str(repo_root / "src" / "crawler" / "tests"), "-q"],
    ]
    harness_test = repo_root / "src" / "crawler" / "tests" / "test_architecture_harness.py"
    if harness_test.exists():
        anchors.append([sys.executable, "-m", "pytest", str(harness_test), "-q"])

    for cmd in anchors:
        rc = runner(cmd)
        if rc != 0:
            return rc
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Paved Path deterministic anchor gate.")
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    sys.exit(run_gate(repo_root=repo_root, skip_preflight=args.skip_preflight))


if __name__ == "__main__":
    main()

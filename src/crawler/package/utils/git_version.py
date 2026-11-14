"""Git SHA resolution utility for self-healing version tracking (Issue #1410)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

_CACHED_LOCAL_GIT_SHA: str | None = None


def _resolve_local_git_sha() -> str:
    global _CACHED_LOCAL_GIT_SHA
    if _CACHED_LOCAL_GIT_SHA is not None:
        return _CACHED_LOCAL_GIT_SHA
    try:
        repo_dir = Path(__file__).resolve().parent
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        sha = (res.stdout or "").strip()[:40] if res.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        sha = ""
    _CACHED_LOCAL_GIT_SHA = sha
    return sha


def get_current_git_sha() -> str:
    """Return the active parser/application Git commit SHA (up to 40 chars, or '')."""
    for env_key in ("APP_GIT_SHA", "GITHUB_SHA", "COMMIT_SHA"):
        val = (os.getenv(env_key) or "").strip()
        if val:
            return val[:40]
    return _resolve_local_git_sha()

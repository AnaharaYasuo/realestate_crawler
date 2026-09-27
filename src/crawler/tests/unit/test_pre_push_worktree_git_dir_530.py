# -*- coding: utf-8 -*-
"""Issue #530: pre-push must pass container-side GIT_DIR/GIT_WORK_TREE for in-repo worktrees."""
import os
import re
import shutil
import subprocess

import pytest

HOOK_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".githooks", "pre-push")
)

pytestmark = pytest.mark.skipif(
    shutil.which("sh") is None or shutil.which("git") is None, reason="requires POSIX sh and git"
)


def _run_pre_pr_check_function() -> str:
    with open(HOOK_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"^run_pre_pr_check\(\) \{\n[\s\S]*?^\}\n", content, re.MULTILINE)
    assert match is not None, "run_pre_pr_check() not found in pre-push"
    return match.group(0)


def _isolated_env(**extra):
    # Inherited GIT_DIR/GIT_WORK_TREE would redirect these git calls to the caller's repository.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra)
    return env


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, env=_isolated_env(), check=True, capture_output=True,
    )


def test_in_repo_worktree_invokes_docker_with_container_git_dir(tmp_path):
    main_root = tmp_path / "repo"
    main_root.mkdir()
    _git(main_root, "init", "-q", "-b", "master")
    _git(main_root, "commit", "-q", "--allow-empty", "-m", "init")
    _git(main_root, "worktree", "add", "-q", ".worktrees/fix-1-demo", "-b", "fix/1-demo")
    worktree = main_root / ".worktrees" / "fix-1-demo"

    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    args_log = tmp_path / "docker_args.log"
    docker_stub = stub_dir / "docker"
    docker_stub.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" > "$DOCKER_ARGS_LOG"\n', encoding="utf-8")
    docker_stub.chmod(0o755)

    script = tmp_path / "run.sh"
    script.write_text(
        "set -e\n" + _run_pre_pr_check_function() + 'run_pre_pr_check "fix/1-demo" "deadbeef"\n',
        encoding="utf-8",
        newline="\n",
    )
    env = _isolated_env(
        PATH=f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        DOCKER_ARGS_LOG=str(args_log),
    )
    subprocess.run(["sh", str(script)], cwd=worktree, env=env, check=True, capture_output=True)

    args = args_log.read_text(encoding="utf-8").splitlines()

    def value_after(flag, prefix):
        return [
            args[i + 1] for i in range(len(args) - 1)
            if args[i] == flag and args[i + 1].startswith(prefix)
        ]

    assert args[:4] == ["compose", "--project-directory", str(main_root), "exec"]
    assert value_after("-e", "GIT_DIR=") == ["GIT_DIR=/app/.git/worktrees/fix-1-demo"]
    assert value_after("-e", "GIT_WORK_TREE=") == ["GIT_WORK_TREE=/app/.worktrees/fix-1-demo"]
    assert value_after("-w", "/app") == ["/app/.worktrees/fix-1-demo"]
    assert "--skip-coderabbit" in args
    assert args[args.index("--branch") + 1] == "fix/1-demo"

# -*- coding: utf-8 -*-
"""Issue #530: pre-push must pass container-side GIT_DIR/GIT_WORK_TREE for in-repo worktrees."""
import os
import re

HOOK_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".githooks", "pre-push")
)


def _in_repo_worktree_branch() -> str:
    with open(HOOK_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'if \[ -n "\$rel_path" \]; then\n([\s\S]*?)\n\s*elif ', content)
    assert match is not None, "in-repo worktree branch not found in pre-push"
    return match.group(1)


def test_in_repo_worktree_passes_git_dir_and_work_tree_to_container():
    block = _in_repo_worktree_branch()
    active_lines = [line for line in block.splitlines() if not line.lstrip().startswith("#")]
    exec_lines = [line for line in active_lines if "docker compose" in line and "exec" in line]
    assert len(exec_lines) == 1
    exec_line = exec_lines[0]
    assert '-e GIT_DIR="/app/$rel_git_dir"' in exec_line
    assert '-e GIT_WORK_TREE="/app/$rel_path"' in exec_line
    assert '-w "/app/$rel_path"' in exec_line
    assert "pre_pr_check.py --diff --skip-coderabbit" in exec_line


def test_in_repo_worktree_git_dir_is_derived_relative_to_main_root():
    block = "\n".join(
        line for line in _in_repo_worktree_branch().splitlines() if not line.lstrip().startswith("#")
    )
    assert "git rev-parse --absolute-git-dir" in block
    assert re.search(r'rel_git_dir="\$\{wt_git_dir_norm#"\$main_root_norm/"\}"', block)

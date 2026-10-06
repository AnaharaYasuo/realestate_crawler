"""Unit tests for CodeGraph operational integration and git hooks."""

import os
import yaml


def get_repo_root():
    """Return the absolute path of the repository root."""
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )


def test_githooks_post_merge_exists_and_configured():
    """Verify that .githooks/post-merge exists and includes codegraph sync."""
    repo_root = get_repo_root()
    post_merge_path = os.path.join(repo_root, ".githooks", "post-merge")

    assert os.path.exists(post_merge_path), ".githooks/post-merge must exist"
    with open(post_merge_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "codegraph" in content, "post-merge must reference codegraph"
    assert "sync" in content, "post-merge must perform codegraph sync"


def test_githooks_post_checkout_exists_and_configured():
    """Verify that .githooks/post-checkout exists and triggers on branch checkout."""
    repo_root = get_repo_root()
    post_checkout_path = os.path.join(repo_root, ".githooks", "post-checkout")

    assert os.path.exists(post_checkout_path), ".githooks/post-checkout must exist"
    with open(post_checkout_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "codegraph" in content, "post-checkout must reference codegraph"
    assert "sync" in content, "post-checkout must perform codegraph sync"


def test_taskfile_has_codegraph_tasks():
    """Verify Taskfile.yml contains codegraph tasks."""
    repo_root = get_repo_root()
    taskfile_path = os.path.join(repo_root, "Taskfile.yml")

    assert os.path.exists(taskfile_path), "Taskfile.yml must exist"
    with open(taskfile_path, "r", encoding="utf-8") as f:
        task_data = yaml.safe_load(f)

    tasks = task_data.get("tasks", {})
    assert "codegraph:sync" in tasks, "Taskfile.yml must define codegraph:sync task"
    assert "codegraph:status" in tasks, "Taskfile.yml must define codegraph:status task"


def test_agents_md_includes_codegraph_rules():
    """Verify .agents/AGENTS.md defines CodeGraph first and sync obligations."""
    repo_root = get_repo_root()
    agents_md_path = os.path.join(repo_root, ".agents", "AGENTS.md")

    assert os.path.exists(agents_md_path), ".agents/AGENTS.md must exist"
    with open(agents_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "codegraph" in content.lower(), "AGENTS.md must define codegraph rules"
    assert "codegraph_explore" in content, "AGENTS.md must mandate codegraph_explore"
    assert "codegraph sync" in content, "AGENTS.md must include codegraph sync in pre-flight sync"

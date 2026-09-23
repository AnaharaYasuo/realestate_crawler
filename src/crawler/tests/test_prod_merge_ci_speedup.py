"""
Test for Prod Merge Speedup and CI Optimization (#376).
Verifies:
1. .coderabbit.yaml base_branches excludes 'production'
2. test.yml pull_request triggers exclude 'production' while push includes it
3. review-gate.yml contains fast-pass logic for targetBranch === 'production'
4. dependabot.yml configures 'groups' for grouped updates
5. auto-release-pr.yml exists and triggers on master push with PR creation/auto-merge logic
"""

from pathlib import Path
import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_coderabbit_excludes_production_branch():
    """Verify that .coderabbit.yaml auto_review.base_branches only contains 'master' and not 'production'."""
    cr_path = REPO_ROOT / ".coderabbit.yaml"
    assert cr_path.exists(), f"{cr_path} does not exist"

    with open(cr_path, "r", encoding="utf-8") as f:
        cr_config = yaml.safe_load(f)

    reviews = cr_config.get("reviews", {})
    auto_review = reviews.get("auto_review", {})
    base_branches = auto_review.get("base_branches", [])

    assert "production" not in base_branches, (
        f".coderabbit.yaml should not have 'production' in base_branches, got {base_branches}"
    )
    assert "master" in base_branches, (
        f".coderabbit.yaml must have 'master' in base_branches, got {base_branches}"
    )


def test_test_workflow_excludes_production_pr():
    """Verify that test.yml pull_request trigger does not include 'production'."""
    test_yml_path = REPO_ROOT / ".github" / "workflows" / "test.yml"
    assert test_yml_path.exists(), f"{test_yml_path} does not exist"

    with open(test_yml_path, "r", encoding="utf-8") as f:
        content = f.read()
        workflow = yaml.safe_load(content)

    on_events = workflow.get("on") or workflow.get(True, {})
    pr_branches = on_events.get("pull_request", {}).get("branches", [])
    push_branches = on_events.get("push", {}).get("branches", [])

    assert "production" not in pr_branches, (
        f"test.yml pull_request.branches must exclude 'production' to prevent duplicate runs, got {pr_branches}"
    )
    assert pr_branches == ["main", "master"], (
        f"test.yml pull_request.branches must strictly be ['main', 'master'], got {pr_branches}"
    )
    assert "production" in push_branches, (
        f"test.yml push.branches should retain 'production' for deploy verification, got {push_branches}"
    )


def test_sonar_workflow_excludes_production_pr():
    """Verify that sonar.yml pull_request trigger excludes 'production' (only main, master)."""
    sonar_yml_path = REPO_ROOT / ".github" / "workflows" / "sonar.yml"
    assert sonar_yml_path.exists(), f"{sonar_yml_path} does not exist"

    with open(sonar_yml_path, "r", encoding="utf-8") as f:
        content = f.read()
        workflow = yaml.safe_load(content)

    on_events = workflow.get("on") or workflow.get(True, {})
    pr_branches = on_events.get("pull_request", {}).get("branches", [])

    assert "production" not in pr_branches, (
        f"sonar.yml pull_request.branches must exclude 'production', got {pr_branches}"
    )
    assert pr_branches == ["main", "master"], (
        f"sonar.yml pull_request.branches must strictly be ['main', 'master'], got {pr_branches}"
    )


def test_review_gate_bypasses_production_pr():
    """Verify that review-gate.yml contains early success fast-pass logic for production PRs."""
    rg_path = REPO_ROOT / ".github" / "workflows" / "review-gate.yml"
    assert rg_path.exists(), f"{rg_path} does not exist"

    content = rg_path.read_text(encoding="utf-8")
    assert "targetBranch === 'production'" in content or 'targetBranch === "production"' in content, (
        "review-gate.yml should check for targetBranch === 'production'"
    )
    assert "isSameRepo" in content and "isMasterHead" in content, (
        "review-gate.yml must verify that production PR originates from same repo and master ref"
    )
    assert "Production release PR: review gate bypassed" in content, (
        "review-gate.yml should set commit status description indicating bypass on production"
    )
    assert "staleChangesRequested" in content, (
        "review-gate.yml should handle stale changes requested from older commits as pending"
    )


def test_dependabot_groups_configured():
    """Verify that dependabot.yml has groups configured for grouped dependency updates."""
    dep_path = REPO_ROOT / ".github" / "dependabot.yml"
    assert dep_path.exists(), f"{dep_path} does not exist"

    with open(dep_path, "r", encoding="utf-8") as f:
        dep_config = yaml.safe_load(f)

    updates = dep_config.get("updates", [])
    ecosystems = {u.get("package-ecosystem"): u for u in updates}

    assert "pip" in ecosystems, "pip ecosystem must be configured in dependabot.yml"
    assert "groups" in ecosystems["pip"], "pip ecosystem must configure 'groups' for grouped PRs"

    assert "github-actions" in ecosystems, "github-actions ecosystem must be configured in dependabot.yml"
    assert "groups" in ecosystems["github-actions"], "github-actions ecosystem must configure 'groups'"


def test_auto_release_pr_workflow_exists_and_valid():
    """Verify that auto-release-pr.yml exists, triggers on master push, and manages production PR."""
    auto_rel_path = REPO_ROOT / ".github" / "workflows" / "auto-release-pr.yml"
    assert auto_rel_path.exists(), f"{auto_rel_path} must exist"

    content = auto_rel_path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(content)

    on_events = workflow.get("on") or workflow.get(True, {})
    push_branches = on_events.get("push", {}).get("branches", [])

    assert "master" in push_branches, "auto-release-pr.yml must trigger on push to master"
    assert "gh pr create" in content, "auto-release-pr.yml must include gh pr create"
    assert "--auto" in content and "--merge" in content, "auto-release-pr.yml must configure auto-merge"
    assert "production" in content, "auto-release-pr.yml must reference production"
    # Issue #383: CodeRabbit による本番PRのAIコメント抑止ディレクティブ
    assert "@coderabbitai ignore" in content, (
        "auto-release-pr.yml must include '@coderabbitai ignore' to prevent automated AI comments on production PR"
    )


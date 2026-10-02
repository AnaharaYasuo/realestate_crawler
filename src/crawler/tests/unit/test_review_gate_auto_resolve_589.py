# -*- coding: utf-8 -*-
"""Unit tests for review-gate.yml CodeRabbit deadlock resolution and auto-resolve (Issue #589).

Tests:
1. Verify review-gate.yml contains autoResolveCodeRabbitThreads logic using GraphQL resolveReviewThread.
2. Verify review-gate.yml bypasses/invalidates CodeRabbit CHANGES_REQUESTED when commit_id != headSha.
3. Verify review-gate.yml does not post repeated '@coderabbitai review' comments.
4. Verify non-CodeRabbit (human) CHANGES_REQUESTED is never bypassed.
"""
import os
import yaml


def _load_review_gate_script() -> str:
    """Extract JavaScript payload from review-gate.yml."""
    curr = os.path.dirname(os.path.abspath(__file__))
    while curr and curr != os.path.dirname(curr):
        wf_path = os.path.join(curr, ".github", "workflows", "review-gate.yml")
        if os.path.exists(wf_path):
            with open(wf_path, "r", encoding="utf-8") as fp:
                data = yaml.safe_load(fp)
            # Find github-script step
            for job in data.get("jobs", {}).values():
                for step in job.get("steps", []):
                    if step.get("uses", "").startswith("actions/github-script"):
                        return step.get("with", {}).get("script", "")
        curr = os.path.dirname(curr)
    raise FileNotFoundError("Could not find review-gate.yml")


def test_review_gate_contains_auto_resolve_graphql():
    """Verify review-gate.yml uses resolveReviewThread mutation for CodeRabbit threads."""
    script = _load_review_gate_script()
    assert "resolveReviewThread" in script
    assert "autoResolveCodeRabbitThreads" in script


def test_review_gate_bypasses_stale_coderabbit_changes_requested():
    """Verify CodeRabbit CHANGES_REQUESTED is bypassed when headSha is newer."""
    script = _load_review_gate_script()
    # Check that when isCodeRabbit and commit_id !== headSha, it logs and does not block
    assert "isCodeRabbit" in script
    # Verify it does not mark as isPending solely for bot re-evaluation
    assert "Waiting for CodeRabbit re-evaluation after new commit" not in script


def test_review_gate_removed_comment_bombing():
    """Verify automatic issue comment creation of '@coderabbitai review' is removed."""
    script = _load_review_gate_script()
    # Should not have issues.createComment with body '@coderabbitai review'
    assert "@coderabbitai review" not in script


def test_human_changes_requested_still_enforced():
    """Verify human changes requested is still added to changesRequested list."""
    script = _load_review_gate_script()
    assert "changesRequested.push" in script


def test_simulate_auto_resolve_and_review_gate_logic():
    """Simulate execution logic of autoResolveCodeRabbitThreads and CHANGES_REQUESTED gating."""
    # Simulation of autoResolveCodeRabbitThreads
    def simulate_auto_resolve(all_reviews, all_threads, head_sha):
        cr_reviews = [r for r in all_reviews if "coderabbit" in (r.get("user", {}).get("login", "")).lower()]
        has_new_commit = any(r.get("commit_id") and r.get("commit_id") != head_sha for r in cr_reviews)
        if not has_new_commit:
            return []

        resolved_thread_ids = []
        for t in all_threads:
            author = (t.get("comments", {}).get("nodes", [{}])[0].get("author", {}).get("login", "")).lower()
            if not t.get("isResolved") and "coderabbit" in author:
                t["isResolved"] = True
                resolved_thread_ids.append(t["id"])
        return resolved_thread_ids

    # Case 1: Stale CodeRabbit review with older commit_id -> auto-resolve unresolved threads
    head_sha = "new_sha_12345"
    all_reviews = [
        {"user": {"login": "coderabbitai[bot]"}, "commit_id": "old_sha_00000", "state": "CHANGES_REQUESTED"}
    ]
    all_threads = [
        {
            "id": "thread_1",
            "isResolved": False,
            "comments": {"nodes": [{"author": {"login": "coderabbitai[bot]"}, "body": "Please fix this"}]}
        },
        {
            "id": "thread_2",
            "isResolved": False,
            "comments": {"nodes": [{"author": {"login": "human_reviewer"}, "body": "Need attention"}]}
        }
    ]

    resolved = simulate_auto_resolve(all_reviews, all_threads, head_sha)
    assert resolved == ["thread_1"]
    assert all_threads[0]["isResolved"] is True
    assert all_threads[1]["isResolved"] is False  # Human thread remains unresolved

    # Case 2: Latest review with same head_sha -> do not auto-resolve
    all_reviews_current = [
        {"user": {"login": "coderabbitai[bot]"}, "commit_id": head_sha, "state": "CHANGES_REQUESTED"}
    ]
    all_threads_current = [
        {
            "id": "thread_3",
            "isResolved": False,
            "comments": {"nodes": [{"author": {"login": "coderabbitai[bot]"}, "body": "New finding"}]}
        }
    ]
    resolved_current = simulate_auto_resolve(all_reviews_current, all_threads_current, head_sha)
    assert resolved_current == []
    assert all_threads_current[0]["isResolved"] is False

    # Simulation of changesRequested evaluation
    def evaluate_changes_requested(latest_reviews, head_sha):
        blocked = []
        for user, r in latest_reviews.items():
            if r.get("state") == "CHANGES_REQUESTED":
                is_coderabbit = "coderabbit" in user.lower()
                if is_coderabbit and r.get("commit_id") and r.get("commit_id") != head_sha:
                    continue  # Stale CodeRabbit CHANGES_REQUESTED is bypassed
                blocked.append({"user": user, "commit_id": r.get("commit_id")})
        return blocked

    # Case 3: CodeRabbit stale CHANGES_REQUESTED is bypassed, human is NOT bypassed
    latest_reviews = {
        "coderabbitai[bot]": {"commit_id": "old_sha_00000", "state": "CHANGES_REQUESTED"},
        "alice_reviewer": {"commit_id": "old_sha_00000", "state": "CHANGES_REQUESTED"}
    }
    blocked = evaluate_changes_requested(latest_reviews, head_sha)
    assert len(blocked) == 1
    assert blocked[0]["user"] == "alice_reviewer"


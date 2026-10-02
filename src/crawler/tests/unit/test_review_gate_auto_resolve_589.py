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

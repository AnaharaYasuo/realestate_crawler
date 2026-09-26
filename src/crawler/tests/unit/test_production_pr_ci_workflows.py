"""Regression tests for the production pull-request CI exclusions in issue #304."""

import re
from pathlib import Path

import pytest
import yaml


WORKFLOWS_DIR = Path(__file__).resolve().parents[4] / ".github" / "workflows"
PRODUCTION_PR_CONDITION = (
    "github.event_name != 'pull_request' || github.base_ref != 'production'"
)


def _load_workflow(name: str) -> dict:
    with (WORKFLOWS_DIR / name).open(encoding="utf-8") as workflow_file:
        workflow = yaml.safe_load(workflow_file)

    assert isinstance(workflow, dict), f"{name} must contain a YAML mapping"
    return workflow


def _evaluate_job_condition(condition: str, event_name: str, base_ref: str) -> bool:
    """Evaluate the small GitHub expression subset used by the changed jobs."""
    values = {
        "github.event_name": event_name,
        "github.base_ref": base_ref,
    }

    results = []
    for clause in condition.split("||"):
        match = re.fullmatch(
            r"\s*(github\.(?:event_name|base_ref))\s*(!=|==)\s*'([^']*)'\s*",
            clause,
        )
        assert match, f"unsupported workflow condition clause: {clause!r}"
        actual = values[match.group(1)]
        expected = match.group(3)
        results.append(actual != expected if match.group(2) == "!=" else actual == expected)

    return any(results)


def _github_script(workflow: dict) -> str:
    steps = workflow["jobs"]["verify-conversations-resolved"]["steps"]
    github_script_steps = [
        step
        for step in steps
        if str(step.get("uses", "")).startswith("actions/github-script@")
    ]
    assert len(github_script_steps) == 1
    return github_script_steps[0]["with"]["script"]


def _extract_braced_block(source: str, marker: str, start: int = 0) -> tuple[str, int]:
    """Return a JavaScript block and the offset immediately after its closing brace."""
    marker_index = source.find(marker, start)
    assert marker_index >= 0, f"marker not found: {marker}"
    opening_brace = source.find("{", marker_index + len(marker))
    assert opening_brace >= 0, f"opening brace not found after: {marker}"

    depth = 0
    for index in range(opening_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening_brace + 1 : index], index + 1

    raise AssertionError(f"unclosed JavaScript block after: {marker}")


@pytest.mark.parametrize(
    ("workflow_name", "job_name"),
    (("snyk.yml", "trivy-iac"), ("sonar.yml", "changes")),
)
@pytest.mark.parametrize(
    ("event_name", "base_ref", "expected_to_run"),
    (
        ("pull_request", "production", False),
        ("pull_request", "master", True),
        ("pull_request", "production-preview", True),
        ("push", "", True),
        ("push", "production", True),
    ),
)
def test_scan_job_condition_only_skips_production_pull_requests(
    workflow_name: str,
    job_name: str,
    event_name: str,
    base_ref: str,
    expected_to_run: bool,
):
    """The exclusion must not suppress pushes or similarly named target branches."""
    condition = _load_workflow(workflow_name)["jobs"][job_name]["if"]

    assert condition == PRODUCTION_PR_CONDITION
    assert _evaluate_job_condition(condition, event_name, base_ref) is expected_to_run


def test_sonarcloud_is_transitively_skipped_with_change_detection():
    workflow = _load_workflow("sonar.yml")
    changes_job = workflow["jobs"]["changes"]
    sonarcloud_job = workflow["jobs"]["sonarcloud"]

    assert changes_job["if"] == PRODUCTION_PR_CONDITION
    assert sonarcloud_job["needs"] == "changes"
    assert sonarcloud_job["if"] == "${{ needs.changes.outputs.app == 'true' }}"


def test_review_gate_targets_only_master_and_excludes_production():
    workflow = _load_workflow("review-gate.yml")
    pull_request_trigger = (workflow.get("on") or workflow.get(True))["pull_request"]
    assert "master" in pull_request_trigger["branches"]
    assert "production" not in pull_request_trigger["branches"]

    script = _github_script(workflow)
    assert "const targetBranch = pr.base && pr.base.ref;" in script
    assert "if (targetBranch !== 'master')" in script


def test_review_gate_has_required_security_checks():
    script = _github_script(_load_workflow("review-gate.yml"))
    declaration_start = script.index("const requiredSecurityChecks")
    declaration_end = script.index("];", declaration_start) + len("];")
    declaration = script[declaration_start:declaration_end]

    assert set(re.findall(r"name: '([^']+)'", declaration)) == {
        "CodeQL Scan",
        "Trivy Security Scan",
        "Semgrep SAST Scan",
        "Checkov IaC Scan",
    }


def test_code_scanning_alerts_are_queried():
    script = _github_script(_load_workflow("review-gate.yml"))
    assert "listAlertsForRepo" in script
    assert "refs/pull/${prNumber}/merge" in script
    assert "refs/heads/${pr.head.ref}" in script


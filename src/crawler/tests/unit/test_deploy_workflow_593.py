"""Unit tests for deploy-production workflow image lifecycle and prune ordering (Issue #593)."""

from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "deploy-production.yml"


def _load_deploy_workflow() -> dict:
    assert WORKFLOW_PATH.exists(), f"Workflow file not found: {WORKFLOW_PATH}"
    with WORKFLOW_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "Workflow YAML must load as a dict"
    return data


def test_deploy_production_prune_step_is_after_all_updates():
    """Prune old images must be executed after all Cloud Run Jobs and Services are updated."""
    workflow = _load_deploy_workflow()
    job = workflow["jobs"]["build-and-deploy-container"]
    steps = job["steps"]

    step_names = [step.get("name") for step in steps if "name" in step]

    # Required update steps that must exist
    required_preceding_steps = [
        "Build and push Docker image",
        "Run Database Migrations on Cloud SQL",
        "Update Cloud Run Job Image",
        "Update Cloud Run Service Image",
        "Update Cloud Run API Service Image",
        "Update Crawler Worker Service Image",
        "Update Crawler Dispatcher Job Image",
        "Update ML Pipeline Job Image",
        "Update Safety Net Job Image",
    ]

    prune_step_name = "Prune old images (Keep latest 3 versions)"
    assert prune_step_name in step_names, f"Prune step '{prune_step_name}' not found"

    prune_index = step_names.index(prune_step_name)

    for step_name in required_preceding_steps:
        assert step_name in step_names, f"Expected step '{step_name}' was not found"
        step_index = step_names.index(step_name)
        assert (
            step_index < prune_index
        ), f"Step '{step_name}' (index {step_index}) must run BEFORE prune step (index {prune_index})"


def test_deploy_production_image_tags_consistency():
    """Verify that build and deploy steps reference consistent sha tags."""
    workflow = _load_deploy_workflow()
    job = workflow["jobs"]["build-and-deploy-container"]
    steps = job["steps"]

    build_step = next(
        s for s in steps if s.get("name") == "Build and push Docker image"
    )
    tags = build_step.get("with", {}).get("tags", "")
    assert "${{ github.sha }}" in tags
    assert "crawler:latest" in tags

    # Verify that Cloud Run update steps use the github.sha tag
    update_steps = [
        s for s in steps if s.get("name", "").startswith("Update Cloud Run") or s.get("name", "").startswith("Update Crawler") or s.get("name", "").startswith("Update ML") or s.get("name", "").startswith("Update Safety")
    ]
    assert len(update_steps) >= 7

    for s in update_steps:
        run_script = s.get("run", "")
        assert "crawler:${{ github.sha }}" in run_script, f"Step '{s.get('name')}' must use ${{ github.sha }} tag"

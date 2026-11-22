from pathlib import Path
import yaml


def test_auto_makemigrations_workflow_exists():
    wf_path = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "auto-makemigrations.yml"
    assert wf_path.exists()
    data = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    assert "pull_request" in data[True]
    assert "src/crawler/package/models/**" in data[True]["pull_request"]["paths"]

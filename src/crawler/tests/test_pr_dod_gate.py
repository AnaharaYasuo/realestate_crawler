import importlib.util
from pathlib import Path


def _load_pr_dod():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / ".agents" / "scripts" / "pr_dod_gate.py"
    spec = importlib.util.spec_from_file_location("pr_dod_gate", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_detects_oversized_pr():
    pd = _load_pr_dod()
    warnings = pd.evaluate_pr_dod(
        changed_files=["src/a.py"],
        total_changed_lines=1200,
        pr_body="- [x] テスト追加済み",
        max_lines=800,
    )
    assert any("oversized_pr" in w for w in warnings)


def test_detects_dod_drift_when_test_checked_without_test_files():
    pd = _load_pr_dod()
    warnings = pd.evaluate_pr_dod(
        changed_files=["src/crawler/package/parser/sample.py"],
        total_changed_lines=50,
        pr_body="- [x] テスト追加・合格",
    )
    assert any("dod_drift" in w for w in warnings)


def test_passes_valid_pr_with_tests():
    pd = _load_pr_dod()
    warnings = pd.evaluate_pr_dod(
        changed_files=[
            "src/crawler/package/parser/sample.py",
            "src/crawler/tests/test_sample.py",
        ],
        total_changed_lines=50,
        pr_body="- [x] テスト追加・合格",
    )
    assert warnings == []

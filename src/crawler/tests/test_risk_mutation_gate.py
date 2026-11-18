import importlib.util
from pathlib import Path


def _load_risk_mutation():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / ".agents" / "scripts" / "risk_mutation_gate.py"
    spec = importlib.util.spec_from_file_location("risk_mutation_gate", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_evaluates_mutation_score_against_threshold():
    rm = _load_risk_mutation()
    assert rm.evaluate_mutation_score(killed=8, total=10, min_score=0.8) is True
    assert rm.evaluate_mutation_score(killed=7, total=10, min_score=0.8) is False
    assert rm.evaluate_mutation_score(killed=0, total=0, min_score=0.8) is False

import importlib.util
from pathlib import Path


def _load_paved_path():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / ".agents" / "scripts" / "paved_path_gate.py"
    spec = importlib.util.spec_from_file_location("paved_path_gate", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_run_gate_stops_on_first_failure():
    pp = _load_paved_path()
    calls = []

    def fake_runner(cmd):
        calls.append(cmd)
        return 1 if "pytest" in " ".join(cmd) else 0

    exit_code = pp.run_gate(
        repo_root=Path("."),
        runner=fake_runner,
        skip_preflight=True,
    )
    assert exit_code == 1
    assert len(calls) == 1


def test_run_gate_succeeds_when_all_anchors_pass():
    pp = _load_paved_path()
    calls = []

    def fake_runner(cmd):
        calls.append(cmd)
        return 0

    exit_code = pp.run_gate(
        repo_root=Path("."),
        runner=fake_runner,
        skip_preflight=True,
    )
    assert exit_code == 0
    assert len(calls) >= 1

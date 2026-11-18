import importlib.util
from pathlib import Path


def _load_static_audit():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / ".agents" / "scripts" / "static_audit_gate.py"
    spec = importlib.util.spec_from_file_location("static_audit_gate", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_detects_swallowed_exception():
    sa = _load_static_audit()
    code = "def f():\n    try:\n        x = 1\n    except Exception:\n        pass\n"
    findings = sa.audit_python_source(code, "sample.py")
    assert any("swallowed_exception" in f for f in findings)


def test_allows_clean_code():
    sa = _load_static_audit()
    code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    assert sa.audit_python_source(code, "clean.py") == []

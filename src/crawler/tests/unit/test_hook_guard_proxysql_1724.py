import importlib.util
from pathlib import Path


def _load_hook_guard():
    guard_path = Path(__file__).resolve().parents[4] / ".agents" / "scripts" / "hook_guard.py"
    spec = importlib.util.spec_from_file_location("hook_guard", guard_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_hook_guard_denies_direct_proxysql_stop():
    hook_guard = _load_hook_guard()
    verdict = hook_guard._evaluate_run_command(
        '& "gcloud.cmd" compute instances stop proxysql-instance-prod --zone=asia-northeast1-a'
    )
    assert verdict is not None
    assert verdict["decision"] == "deny"
    assert "ProxySQL protection" in verdict["reason"]

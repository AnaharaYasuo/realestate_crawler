"""
Unit tests for pipeline architecture guardrails and regression prevention (Issue #422).
Prevents regressions where ProxySQL is idle (0 replicas) and the pipeline hangs on DB connection.
"""
import ast
import os

TERRAFORM_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../terraform"))
CRAWLER_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts"))


def test_scheduler_triggers_pipeline_with_startup_guardrail():
    """Verify scheduler targets crawler pipeline job and the script includes ProxySQL on-demand startup."""
    scheduler_tf = os.path.join(TERRAFORM_DIR, "scheduler.tf")
    with open(scheduler_tf, "r", encoding="utf-8") as f:
        content = f.read()

    assert "google_cloud_scheduler_job" in content
    assert "crawler_daily_trigger" in content
    assert "google_cloud_run_v2_job.crawler_pipeline_job.name" in content


def test_run_pipeline_contains_startup_and_health_check():
    """Verify run_pipeline.py explicitly imports and invokes scale_proxysql_mig and wait_for_proxysql_health."""
    pipeline_py = os.path.join(CRAWLER_SCRIPTS_DIR, "ops", "run_pipeline.py")
    with open(pipeline_py, "r", encoding="utf-8") as f:
        content = f.read()

    # Imports check
    assert "patch_proxysql_autoscaler" in content, "run_pipeline.py must import patch_proxysql_autoscaler"
    assert "scale_proxysql_mig" in content, "run_pipeline.py must import scale_proxysql_mig"
    assert "wait_for_proxysql_health" in content, "run_pipeline.py must import wait_for_proxysql_health"

    # Function definition check
    tree = ast.parse(content)
    startup_func = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_execute_startup_resources"),
        None,
    )
    assert startup_func is not None, "run_pipeline.py must define _execute_startup_resources"
    called_funcs = [
        item.func.id
        for item in ast.walk(startup_func)
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
    ]
    assert "patch_proxysql_autoscaler" in called_funcs, "_execute_startup_resources must invoke patch_proxysql_autoscaler"
    assert "scale_proxysql_mig" in called_funcs, "_execute_startup_resources must invoke scale_proxysql_mig"
    assert "wait_for_proxysql_health" in called_funcs, "_execute_startup_resources must invoke wait_for_proxysql_health"

    # Execution sequence check: _execute_startup_resources must appear BEFORE wait_for_db.py
    startup_pos = content.find("_execute_startup_resources(is_coordinator)")
    db_wait_pos = content.find("wait_for_db.py")
    assert startup_pos != -1, "_execute_startup_resources must be called in main()"
    assert db_wait_pos != -1, "wait_for_db.py must be called in main()"
    assert startup_pos < db_wait_pos, "_execute_startup_resources must be executed BEFORE wait_for_db.py!"


def test_run_pipeline_finally_teardown_enforced():
    """Verify run_pipeline.py enforces safety teardown in finally block."""
    pipeline_py = os.path.join(CRAWLER_SCRIPTS_DIR, "ops", "run_pipeline.py")
    with open(pipeline_py, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Find main function and check Try statement has finally executing _execute_safety_teardown
    found_finally_teardown = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            for item in ast.walk(node):
                if isinstance(item, ast.Try) and item.finalbody:
                    for fin in item.finalbody:
                        if isinstance(fin, ast.Expr) and isinstance(fin.value, ast.Call):
                            func = fin.value.func
                            if isinstance(func, ast.Name) and func.id == "_execute_safety_teardown":
                                found_finally_teardown = True
    assert found_finally_teardown, "main() must have a finally block executing _execute_safety_teardown!"


def test_wait_for_db_fail_fast_socket_guardrail():
    """Verify wait_for_db.py contains socket.create_connection to avoid 1-hour TCP SYN hangs."""
    wait_db_py = os.path.join(CRAWLER_SCRIPTS_DIR, "debug_tools", "wait_for_db.py")
    with open(wait_db_py, "r", encoding="utf-8") as f:
        content = f.read()

    assert "socket.create_connection" in content, "wait_for_db.py must use socket.create_connection for fail-fast check"
    assert "socket_timeout" in content, "wait_for_db.py must specify socket_timeout to bound connection wait"

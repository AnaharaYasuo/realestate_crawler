# -*- coding: utf-8 -*-
import os
import sys
import setup_env

def test_setup_env_initialization():
    # setup_env should return a valid crawler_dir containing realestateSettings.py
    crawler_dir = setup_env.CRAWLER_DIR
    assert crawler_dir is not None
    assert os.path.exists(os.path.join(crawler_dir, "realestateSettings.py"))
    assert crawler_dir in sys.path

def test_dynamic_root_discovery():
    # Verify that walking up from any nested path finds realestateSettings.py
    cur = os.path.abspath(__file__)
    found = False
    while True:
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        if os.path.exists(os.path.join(parent, "realestateSettings.py")):
            found = True
            break
        cur = parent
    assert found is True


def test_db_pool_options_has_pre_ping_and_recycle():
    """realestateSettings においてアプリ側プール(dj_db_conn_pool)が廃止され CONN_MAX_AGE=0 による ProxySQL 一元プーリングになっていること"""
    import realestateSettings
    import inspect

    src = inspect.getsource(realestateSettings.configure)
    assert "dj_db_conn_pool" not in src
    assert "'CONN_MAX_AGE': 0" in src
    assert "'django.db.backends.mysql'" in src


def test_validate_data_standalone_execution():
    """validate_data.py が PYTHONPATH 未設定の独立プロセス環境でも setup_env を自己解決して起動できること"""
    import subprocess

    crawler_dir = setup_env.CRAWLER_DIR
    validate_script = os.path.join(crawler_dir, "scripts", "maintenance", "validate_data.py")
    assert os.path.exists(validate_script)

    # PYTHONPATH を排除したクリーンな環境変数で別プロセス起動
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    # 任意の別ディレクトリ（例: root や tmp）を cwd として実行
    proc = subprocess.run(
        [sys.executable, validate_script, "--help"],
        cwd=os.path.dirname(crawler_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, f"Failed with stderr: {proc.stderr}"
    assert "usage:" in proc.stdout.lower() or "options:" in proc.stdout.lower()



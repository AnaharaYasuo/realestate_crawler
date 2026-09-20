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
    """realestateSettings の POOL_OPTIONS に PRE_PING: True と短縮リサイクルが設定されていること"""
    import realestateSettings
    import inspect

    src = inspect.getsource(realestateSettings.configure)
    assert "'PRE_PING': True" in src
    assert "300" in src


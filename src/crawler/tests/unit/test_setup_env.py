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
    """realestateSettings の POOL_OPTIONS において cloud/非cloud の両分岐で PRE_PING: True と短縮リサイクルが設定されていること"""
    import realestateSettings
    import inspect
    import ast

    src = inspect.getsource(realestateSettings.configure)
    assert src.count("'PRE_PING': True") >= 2
    assert src.count("int(os.getenv('DB_POOL_RECYCLE', 300))") >= 2

    # AST 解析で POOL_OPTIONS 辞書のキーと設定値を直接検証
    tree = ast.parse(src)
    pool_options_found = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            if 'PRE_PING' in keys and 'RECYCLE' in keys:
                pool_options_found += 1
                pre_ping_idx = keys.index('PRE_PING')
                val_node = node.values[pre_ping_idx]
                assert isinstance(val_node, ast.Constant) and val_node.value is True

    assert pool_options_found >= 2



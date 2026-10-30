# -*- coding: utf-8 -*-
"""Issue #932: クローラー/ディスパッチャーが manage.py migrate を実行しないことを検証する回帰テスト"""
import os

OPS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts", "ops")


def _read(name: str) -> str:
    with open(os.path.join(OPS_DIR, name), encoding="utf-8") as f:
        return f.read()


def test_run_pipeline_does_not_run_migrate():
    assert '"migrate"' not in _read("run_pipeline.py")


def test_run_dispatcher_does_not_run_migrate():
    src = _read("run_dispatcher.py")
    assert '"migrate"' not in src
    assert "run_db_migration" not in src

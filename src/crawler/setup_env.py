# -*- coding: utf-8 -*-
"""
プロジェクト統一環境・Django設定初期化モジュール (setup_env.py)

スクリプトの階層深さ（ops/, maintenance/, debug_tools/ 等）や実行カレントディレクトリに依存せず、
__file__ から親方向に遡って realestateSettings.py の存在するルートディレクトリ (src/crawler) を
動的に検出し、sys.path の最優先 (index 0) に適用します。
"""
import os
import sys

def _find_crawler_dir():
    cur = os.path.abspath(__file__)
    while True:
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        if os.path.exists(os.path.join(parent, "realestateSettings.py")):
            if parent not in sys.path:
                sys.path.insert(0, parent)
            return parent
        cur = parent


def _reconfigure_streams():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _init_settings():
    try:
        from package.utils.logging_config import configure_logging
        configure_logging()
    except Exception:
        pass
    import realestateSettings
    realestateSettings.configure()


def init_environment():
    crawler_dir = _find_crawler_dir()
    _reconfigure_streams()
    if crawler_dir:
        _init_settings()
    return crawler_dir

# モジュールインポート時に自動実行
CRAWLER_DIR = init_environment()

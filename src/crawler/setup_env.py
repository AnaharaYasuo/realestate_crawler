# -*- coding: utf-8 -*-
"""
プロジェクト統一環境・Django設定初期化モジュール (setup_env.py)

スクリプトの階層深さ（ops/, maintenance/, debug_tools/ 等）や実行カレントディレクトリに依存せず、
__file__ から親方向に遡って realestateSettings.py の存在するルートディレクトリ (src/crawler) を
動的に検出し、sys.path の最優先 (index 0) に適用します。
"""
import os
import sys

def init_environment():
    cur = os.path.abspath(__file__)
    crawler_dir = None
    while True:
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        if os.path.exists(os.path.join(parent, "realestateSettings.py")):
            crawler_dir = parent
            if parent not in sys.path:
                sys.path.insert(0, parent)
            break
        cur = parent

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if crawler_dir:
        try:
            from package.utils.logging_config import configure_logging
            configure_logging()
        except Exception:
            pass
        import realestateSettings
        realestateSettings.configure()
    return crawler_dir

# モジュールインポート時に自動実行
CRAWLER_DIR = init_environment()

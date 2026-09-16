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

    if crawler_dir:
        import realestateSettings
        realestateSettings.configure()
    return crawler_dir

# モジュールインポート時に自動実行
CRAWLER_DIR = init_environment()

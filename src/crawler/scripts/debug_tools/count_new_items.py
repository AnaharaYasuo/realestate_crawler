# -*- coding: utf-8 -*-
import sys
import os
_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env
        break
    _cur = _parent
from django.db import connection

threshold = "2026-08-22 13:50:00"

with connection.cursor() as cursor:
    cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'")
    tables = [r[0] for r in cursor.fetchall()]
    
    results = []
    total = 0
    for t in tables:
        if t in ['django_migrations', 'django_content_type', 'auth_permission', 'property_evaluations']:
            continue
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{t}` WHERE inputDateTime >= %s", [threshold])
            cnt = cursor.fetchone()[0]
            if cnt > 0:
                print(f"• {t}: {cnt:,} 件", flush=True)
                results.append((t, cnt))
                total += cnt
        except Exception:
            pass

print("──────────────────────────────────────────", flush=True)
print(f"🔥 合計新規取得件数: {total:,} 件", flush=True)

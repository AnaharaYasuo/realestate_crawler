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
from django.apps import apps

threshold = "2026-08-22 13:50:00"

results = []
total = 0
for model in apps.get_models():
    t = model._meta.db_table
    if t in ['django_migrations', 'django_content_type', 'auth_permission', 'property_evaluations']:
        continue
    if hasattr(model, 'inputDateTime'):
        try:
            cnt = model.objects.filter(inputDateTime__gte=threshold).count()
            if cnt > 0:
                print(f"• {t}: {cnt:,} 件", flush=True)
                results.append((t, cnt))
                total += cnt
        except Exception:
            pass

print("──────────────────────────────────────────", flush=True)
print(f"🔥 合計新規取得件数: {total:,} 件", flush=True)

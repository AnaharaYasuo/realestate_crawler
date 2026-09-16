# -*- coding: utf-8 -*-
import os
import sys
import django

# Djangoの環境設定 (project_root を追加)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "src", "crawler"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "realestateSettings")
django.setup()

from django.apps import apps
from django.db.models import CharField, TextField

def check_none_and_spaces():
    print("=== Checking Database for 'None' strings or double spaces ===")
    models = apps.get_models()
    
    found_count = 0
    for model in models:
        # クローラーデータに関連するモデルのみチェック
        if not model.__module__.startswith("package.models."):
            continue
            
        fields = [f for f in model._meta.fields if isinstance(f, (CharField, TextField))]
        if not fields:
            continue
            
        # None や 二重スペースを持つレコードを検索
        for item in model.objects.all():
            for f in fields:
                val = getattr(item, f.name, None)
                if val:
                    val_str = str(val)
                    has_literal_none = "None" in val_str or "none" in val_str
                    has_double_space = "  " in val_str
                    
                    if has_literal_none or has_double_space:
                        print(f"[{model.__name__}] ID: {item.pk} | Field: {f.name} | Value: '{val_str}'")
                        found_count += 1
                        if found_count >= 50:
                            print("Reached max display limit of 50.")
                            return
                            
    print(f"Total problematic records found: {found_count}")

if __name__ == "__main__":
    check_none_and_spaces()

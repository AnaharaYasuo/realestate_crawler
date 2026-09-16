# -*- coding: utf-8 -*-
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from django.apps import apps

def check_all_counts():
    print("=== 全物件モデル DB 取得件数チェック ===")
    app_config = apps.get_app_config("package")
    models = app_config.get_models()
    
    total_db_records = 0
    zero_models = []
    active_models = []
    
    for model in sorted(models, key=lambda m: m.__name__):
        model_name = model.__name__
        if model_name in ["PropertyEvaluation", "PropertyImage", "SelectorConfig"]:
            continue
            
        try:
            cnt = model.objects.count()
        except Exception as e:
            print(f"⚠️ Error query model {model_name}: {e}")
            continue
            
        total_db_records += cnt
        
        if cnt == 0:
            zero_models.append(model_name)
            print(f"❌ [0件] {model_name:35s}: 0件")
        else:
            active_models.append((model_name, cnt))
            print(f"✅ [取得済] {model_name:35s}: {cnt:6d}件")
            
    print(f"\n全総件数: {total_db_records}件")
    print(f"データ取得 0件のモデル数: {len(zero_models)} / {len(zero_models) + len(active_models)}")
    print(f"データ取得 成功のモデル数: {len(active_models)} / {len(zero_models) + len(active_models)}")
    
    print("\n--- [0件のモデル一覧] ---")
    for zm in zero_models:
        print(f" - {zm}")

if __name__ == "__main__":
    check_all_counts()

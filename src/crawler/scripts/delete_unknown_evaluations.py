# -*- coding: utf-8 -*-
import os
import sys

# Add src and crawler dirs to sys.path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)

# Initialize settings using realestateSettings
try:
    import realestateSettings
    realestateSettings.configure()
except Exception as e:
    print(f"Failed to configure settings: {e}")
    sys.exit(1)

from package.models.evaluation import PropertyEvaluation

def main():
    print("=== PropertyEvaluation Data Deletion Script ===")
    
    # 1. 現在 company='unknown' であるものを削除
    unknown_records = PropertyEvaluation.objects.filter(company='unknown')
    unknown_count = unknown_records.count()
    
    # 2. すでにクレンジングスクリプトで更新されてしまった古いゴミデータ (ID <= 2800) を削除
    # 2800以下の評価レコードはすべて過去の古いテストデータであり、不正データに該当します。
    old_records = PropertyEvaluation.objects.filter(id__lte=2800)
    old_count = old_records.count()
    
    print(f"Current unknown company records to delete: {unknown_count}")
    print(f"Old test evaluation records (ID <= 2800) to delete: {old_count}")
    
    # 削除実行
    # PropertyImage などは ForeignKey(on_delete=CASCADE) 設定されているため、自動的に紐づく画像レコードも削除されます。
    
    deleted_unknown, _ = unknown_records.delete()
    deleted_old, _ = old_records.delete()
    
    print("\nDeletion finished!")
    print(f"Deleted unknown company records: {deleted_unknown}")
    print(f"Deleted old test evaluation records: {deleted_old}")

if __name__ == '__main__':
    main()

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

import django
from package.models.evaluation import PropertyEvaluation

def main():
    print("=== PropertyEvaluation Data Cleansing Script ===")
    
    # 対象レコードの取得
    unknown_records = PropertyEvaluation.objects.filter(company='unknown')
    total_count = unknown_records.count()
    print(f"Found {total_count} records with company='unknown'. Starting cleansing...")
    
    companies = ["mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1", "mizuho", "odakyu", "afr", "sekisui", "daiwa", "totate", "athome", "homes", "seibu", "keikyu", "sotetsu", "keisei", "daikyo", "rearie", "heim", "sumirin", "keio"]
    
    updated_count = 0
    skipped_count = 0
    
    for ev in unknown_records:
        ptype = ev.property_type.lower()
        matched_company = None
        matched_type = None
        
        for c in companies:
            if ptype.startswith(c):
                matched_company = c
                matched_type = ptype.replace(c, "")
                break
                
        if matched_company and matched_type:
            # データベースを更新
            old_company = ev.company
            old_type = ev.property_type
            
            ev.company = matched_company
            ev.property_type = matched_type
            ev.save()
            
            updated_count += 1
            if updated_count <= 10 or updated_count % 100 == 0:
                print(f"[{updated_count}/{total_count}] Updated ID {ev.id}: company '{old_company}' -> '{ev.company}', type '{old_type}' -> '{ev.property_type}'")
        else:
            skipped_count += 1
            if skipped_count <= 10:
                print(f"WARNING: Could not guess company/type for ID {ev.id} (type: '{ev.property_type}')")
                
    print(f"\nCleansing finished!")
    print(f"Successfully updated: {updated_count} records.")
    print(f"Failed/Skipped: {skipped_count} records.")

if __name__ == '__main__':
    main()

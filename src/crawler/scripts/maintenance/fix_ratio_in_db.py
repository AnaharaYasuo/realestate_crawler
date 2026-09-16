import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from django.apps import apps
from package.utils import converter
import re

models = apps.get_models()

for model in models:
    name = model.__name__
    if not (name.endswith("Mansion") or name.endswith("Kodate") or name.endswith("Tochi") or "Investment" in name):
        continue
    if "PropertyEvaluation" in name:
        continue
        
    # Check if model has kenpei / youseki fields
    fields = [f.name for f in model._meta.fields]
    if "kenpei" not in fields or "youseki" not in fields:
        continue
        
    total = model.objects.count()
    if total == 0:
        continue
        
    # Find records where kenpeiStr is not empty but kenpei is null, or yousekiStr is not empty but youseki is null
    qs_kenpei = model.objects.filter(kenpei__isnull=True).exclude(kenpeiStr="")
    qs_youseki = model.objects.filter(youseki__isnull=True).exclude(yousekiStr="")
    
    # We combine them
    qs = (qs_kenpei | qs_youseki).distinct()
    count = qs.count()
    if count == 0:
        continue
        
    print(f"Fixing {count} ratio records for {name}...")
    fixed = 0
    for item in qs:
        # If kenpeiStr or yousekiStr contains combined pattern, try splitting
        kenpei_str = item.kenpeiStr or ""
        youseki_str = item.yousekiStr or ""
        
        # Check combined pattern in either
        combined_str = ""
        if "／" in kenpei_str or "/" in kenpei_str:
            combined_str = kenpei_str
        elif "／" in youseki_str or "/" in youseki_str:
            combined_str = youseki_str
            
        if combined_str:
            parts = re.split(r'[／/]', combined_str)
            if len(parts) >= 2:
                kenpei_str = parts[0].strip()
                youseki_str = parts[1].strip()
                item.kenpeiStr = kenpei_str
                item.yousekiStr = youseki_str
                
        # Parse
        if kenpei_str:
            item.kenpei = converter.parse_ratio(kenpei_str)
        if youseki_str:
            item.youseki = converter.parse_ratio(youseki_str)
            
        item.save()
        fixed += 1
        
    print(f"Finished {name}: fixed {fixed} ratio records.")

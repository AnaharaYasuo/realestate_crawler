import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from django.apps import apps
from django.db.models import Q

models = apps.get_models()

print(f"{'Model Name':<30} | {'Total':<6} | {'Null Kenpei':<11} | {'Null Youseki':<12} | {'Null WalkMin':<12}")
print("-" * 80)

for model in sorted(models, key=lambda m: m.__name__):
    name = model.__name__
    if not (name.endswith("Mansion") or name.endswith("Kodate") or name.endswith("Tochi") or "Investment" in name):
        continue
    if "PropertyEvaluation" in name:
        continue
        
    total = model.objects.count()
    if total == 0:
        continue
        
    # Check kenpei
    null_kenpei = 0
    if hasattr(model(), "kenpei"):
        try:
            null_kenpei = model.objects.filter(Q(kenpei__isnull=True) | Q(kenpei=0)).count()
        except Exception:
            null_kenpei = model.objects.filter(kenpei__isnull=True).count()
    else:
        null_kenpei = -1 # Not applicable
        
    # Check youseki
    null_youseki = 0
    if hasattr(model(), "youseki"):
        try:
            null_youseki = model.objects.filter(Q(youseki__isnull=True) | Q(youseki=0)).count()
        except Exception:
            null_youseki = model.objects.filter(youseki__isnull=True).count()
    else:
        null_youseki = -1
        
    # Check walk
    null_walk = 0
    if hasattr(model(), "railwayWalkMinute1"):
        null_walk = model.objects.filter(Q(railwayWalkMinute1__isnull=True) | Q(railwayWalkMinute1=0)).count()
    else:
        null_walk = -1
        
    print(f"{name:<30} | {total:<6} | {null_kenpei:<11} | {null_youseki:<12} | {null_walk:<12}")

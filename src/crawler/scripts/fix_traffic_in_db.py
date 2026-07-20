import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from django.apps import apps
from package.parser.baseParser import ParserBase

class DummyParser(ParserBase):
    def getCharset(self): pass
    def createEntity(self): pass
    def _parsePropertyDetailPage(self, item, response): pass

parser = DummyParser()
models = apps.get_models()

for model in models:
    name = model.__name__
    if not (name.endswith("Mansion") or name.endswith("Kodate") or name.endswith("Tochi") or "Investment" in name):
        continue
    if "PropertyEvaluation" in name:
        continue
        
    total = model.objects.count()
    if total == 0:
        continue
        
    # Find records with traffic but no railway1
    qs = model.objects.filter(railway1__isnull=True).exclude(traffic="")
    count = qs.count()
    if count == 0:
        continue
        
    print(f"Fixing {count} records for {name}...")
    fixed = 0
    for item in qs[:10]:
        old_traffic = item.traffic
        parser._populateTraffic(item, item.traffic)
        print(f"  Traffic: {repr(old_traffic)}")
        print(f"  Parsed -> R1: {repr(item.railway1)} | S1: {repr(item.station1)} | Walk1: {item.railwayWalkMinute1}")
        item.save()
        fixed += 1
        
    # Also save the rest without printing
    for item in qs[10:]:
        parser._populateTraffic(item, item.traffic)
        item.save()
        fixed += 1
    print(f"Finished {name}: fixed {fixed} records.")

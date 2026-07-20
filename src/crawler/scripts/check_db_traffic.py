import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from package.models.homes import HomesTochi
from package.models.athome import AthomeKodate

print("=== HomesTochi Traffic samples ===")
for x in HomesTochi.objects.filter(railwayWalkMinute1__isnull=True)[:5]:
    print(f"ID: {x.id} | Traffic: {repr(x.traffic)} | R1: {repr(x.railway1)} | S1: {repr(x.station1)} | Walk: {x.railwayWalkMinute1}")

print("\n=== AthomeKodate Traffic samples ===")
for x in AthomeKodate.objects.filter(railwayWalkMinute1__isnull=True)[:5]:
    print(f"ID: {x.id} | Traffic: {repr(x.traffic)} | R1: {repr(x.railway1)} | S1: {repr(x.station1)} | Walk: {x.railwayWalkMinute1}")

print("\n=== HomesTochi Kenpei samples ===")
for x in HomesTochi.objects.filter(kenpei__isnull=True)[:5]:
    print(f"ID: {x.id} | KenpeiStr: {repr(getattr(x, 'kenpeiStr', None))} | Kenpei: {x.kenpei}")

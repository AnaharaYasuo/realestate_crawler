# -*- coding: utf-8 -*-
import os
import sys

_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_crawler_dir = os.path.dirname(_scripts_dir)
sys.path.insert(0, _crawler_dir)

import realestateSettings
realestateSettings.configure()

from package.models.homes import HomesMansion, HomesKodate, HomesInvestmentApartment, HomesTochi
from package.models.athome import AthomeMansion, AthomeKodate, AthomeInvestmentApartment, AthomeTochi

print("=== DB Count Summary ===")
print(f"Homes Mansion count: {HomesMansion.objects.count()}")
print(f"Homes Kodate count: {HomesKodate.objects.count()}")
print(f"Homes InvestApartment count: {HomesInvestmentApartment.objects.count()}")
print(f"Homes Tochi count: {HomesTochi.objects.count()}")
print("---")
print(f"Athome Mansion count: {AthomeMansion.objects.count()}")
print(f"Athome Kodate count: {AthomeKodate.objects.count()}")
print(f"Athome InvestApartment count: {AthomeInvestmentApartment.objects.count()}")
print(f"Athome Tochi count: {AthomeTochi.objects.count()}")

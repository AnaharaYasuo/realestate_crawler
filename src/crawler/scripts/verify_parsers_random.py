# -*- coding: utf-8 -*-
import sys
import os
import django
import asyncio
import aiohttp
import random
import logging
from bs4 import BeautifulSoup

# Setup Django environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import realestateSettings
realestateSettings.configure()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

from package.models.homes import HomesInvestmentApartment, HomesMansion, HomesKodate, HomesTochi
from package.models.mitsui import MitsuiMansion
from package.models.keikyu import KeikyuMansion
from package.models.sumai1 import Sumai1Investment, Sumai1Mansion, Sumai1Kodate, Sumai1Tochi
from package.models.sumirin import SumirinInvestment, SumirinMansion, SumirinKodate, SumirinTochi
from package.models.tokyu import TokyuInvestmentApartment, TokyuInvestmentKodate, TokyuTochi, TokyuMansion, TokyuKodate

from package.parser.homesParser import HomesInvestmentApartmentParser, HomesMansionParser, HomesKodateParser, HomesTochiParser
from package.parser.mitsuiParser import MitsuiMansionParser
from package.parser.keikyuParser import KeikyuMansionParser
from package.parser.sumai1Parser import Sumai1InvestmentParser, Sumai1MansionParser, Sumai1KodateParser, Sumai1TochiParser
from package.parser.sumirinParser import SumirinInvestmentParser, SumirinMansionParser, SumirinKodateParser, SumirinTochiParser
from package.parser.tokyuParser import TokyuInvestmentApartmentParser, TokyuInvestmentKodateParser, TokyuTochiParser, TokyuMansionParser, TokyuKodateParser

TARGET_PARSERS = [
    # (ModelClass, ParserClass, name)
    (HomesInvestmentApartment, HomesInvestmentApartmentParser, "HomesInvestmentApartment"),
    (HomesMansion, HomesMansionParser, "HomesMansion"),
    (HomesKodate, HomesKodateParser, "HomesKodate"),
    (HomesTochi, HomesTochiParser, "HomesTochi"),
    (MitsuiMansion, MitsuiMansionParser, "MitsuiMansion"),
    (KeikyuMansion, KeikyuMansionParser, "KeikyuMansion"),
    (Sumai1Investment, Sumai1InvestmentParser, "Sumai1Investment"),
    (Sumai1Mansion, Sumai1MansionParser, "Sumai1Mansion"),
    (Sumai1Kodate, Sumai1KodateParser, "Sumai1Kodate"),
    (Sumai1Tochi, Sumai1TochiParser, "Sumai1Tochi"),
    (SumirinInvestment, SumirinInvestmentParser, "SumirinInvestment"),
    (SumirinMansion, SumirinMansionParser, "SumirinMansion"),
    (SumirinKodate, SumirinKodateParser, "SumirinKodate"),
    (SumirinTochi, SumirinTochiParser, "SumirinTochi"),
    (TokyuInvestmentApartment, TokyuInvestmentApartmentParser, "TokyuInvestmentApartment"),
    (TokyuInvestmentKodate, TokyuInvestmentKodateParser, "TokyuInvestmentKodate"),
    (TokyuTochi, TokyuTochiParser, "TokyuTochi"),
    (TokyuMansion, TokyuMansionParser, "TokyuMansion"),
    (TokyuKodate, TokyuKodateParser, "TokyuKodate"),
]

async def verify_parser_on_urls(session, model_class, parser_class, label, urls):
    parser = parser_class()
    success_count = 0
    total = len(urls)
    
    print(f"\n===== Testing {label} (Sample size: {total}) =====")
    for url in urls:
        try:
            # BaseParser handles fetch & parse inside parsePropertyDetailPage
            item = await parser.parsePropertyDetailPage(session, url)
            
            # Inspect key targeted fields based on previous failures
            detail_info = []
            if label.startswith("Homes"):
                detail_info = [
                    f"chimoku={getattr(item, 'chimoku', None)}",
                    f"currentStatus={getattr(item, 'currentStatus', None)}",
                    f"setsudou={getattr(item, 'setsudou', None)}",
                    f"kenpei={getattr(item, 'kenpei', None)}",
                    f"youseki={getattr(item, 'youseki', None)}"
                ]
            elif label == "MitsuiMansion":
                detail_info = [
                    f"floorType_kouzou={getattr(item, 'floorType_kouzou', None)}",
                    f"kouzou={getattr(item, 'kouzou', None)}"
                ]
            elif label == "KeikyuMansion":
                detail_info = [
                    f"senyuMenseki={getattr(item, 'senyuMenseki', None)}",
                    f"floorType_kai={getattr(item, 'floorType_kai', None)}",
                    f"floorType_chijo={getattr(item, 'floorType_chijo', None)}",
                    f"floorType_chika={getattr(item, 'floorType_chika', None)}"
                ]
            elif label.startswith("Sumai1"):
                detail_info = [
                    f"kenpei={getattr(item, 'kenpei', None)}",
                    f"youseki={getattr(item, 'youseki', None)}",
                    f"floorType_kai={getattr(item, 'floorType_kai', None)}",
                    f"soukosu={getattr(item, 'soukosu', None)}"
                ]
            elif label.startswith("Sumirin"):
                detail_info = [
                    f"annualRent={getattr(item, 'annualRent', None)}",
                    f"monthlyRent={getattr(item, 'monthlyRent', None)}",
                    f"soukosu={getattr(item, 'soukosu', None)}",
                    f"floorType_kai={getattr(item, 'floorType_kai', None)}",
                    f"kenpei={getattr(item, 'kenpei', None)}"
                ]
            elif label.startswith("Tokyu"):
                biko_val = getattr(item, 'biko', None)
                detail_info = [
                    f"biko={biko_val[:20] if biko_val else None}",
                    f"genkyo={getattr(item, 'genkyo', None)}",
                    f"hikiwatashi={getattr(item, 'hikiwatashi', None)}",
                    f"okuyuki={getattr(item, 'okuyuki', None)}"
                ]
                
            print(f"SUCCESS: {url} -> {', '.join(detail_info)}")
            success_count += 1
        except Exception as e:
            print(f"FAILED: {url} -> Reason: {type(e).__name__}: {str(e)}")
            
    print(f"RESULT: {label} -> {success_count}/{total} parsed without crash")
    return success_count, total

async def main():
    conn = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=conn) as session:
        tasks = []
        for model_class, parser_class, label in TARGET_PARSERS:
            # Query pageUrls safely from db
            from asgiref.sync import sync_to_async
            def get_urls(cls):
                return list(cls.objects.filter(pageUrl__isnull=False).values_list('pageUrl', flat=True))
            urls = await sync_to_async(get_urls)(model_class)
            if not urls:
                print(f"No URLs in DB for {label}. Skipping.")
                continue
            
            # Sample up to 10 random URLs to hit variations
            sample_size = min(10, len(urls))
            sampled_urls = random.sample(urls, sample_size)
            
            tasks.append(verify_parser_on_urls(session, model_class, parser_class, label, sampled_urls))
            
        results = await asyncio.gather(*tasks)
        
        # Summary
        print("\n\n" + "="*40 + " VERIFICATION SUMMARY " + "="*40)
        for (model_class, parser_class, label), (succ, tot) in zip(TARGET_PARSERS, results):
            print(f"{label:<30} : {succ}/{tot} parsed successfully")
        print("="*102)

if __name__ == "__main__":
    asyncio.run(main())

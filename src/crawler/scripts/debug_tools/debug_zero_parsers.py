# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import aiohttp
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from package.parser.afrParser import AfrMansionParser

async def test_afr_detail():
    url = "https://www.hebel-haus.com/stockhebel/purchase/forhome/details.html?bno=BMS09818"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            html = await resp.text()
            print(f"Detail Status: {resp.status}, HTML len: {len(html)}")
            soup = BeautifulSoup(html, "html.parser")
            parser = AfrMansionParser()
            item = parser.createEntity()
            try:
                parsed_item = parser._parsePropertyDetailPage(item, soup)
                print(f"Parsed Name: '{parsed_item.propertyName}'")
                print(f"Parsed Price: {parsed_item.price}")
                print(f"Parsed Address: '{parsed_item.address}'")
                parser.validate_required_fields(parsed_item)
                print("Validation PASSED!")
            except Exception as e:
                print(f"Parsing/Validation Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_afr_detail())

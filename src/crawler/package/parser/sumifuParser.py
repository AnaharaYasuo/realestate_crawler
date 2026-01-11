# -*- coding: utf-8 -*-
from abc import abstractmethod
import sys
import unicodedata


from bs4 import BeautifulSoup
from package.models.sumifu import SumifuMansion, SumifuModel, SumifuTochi, SumifuKodate, SumifuInvestment
from package.parser.investmentParser import InvestmentParser
from django.db import models
import importlib
importlib.reload(sys)
from decimal import Decimal
import datetime
import traceback
import re
from builtins import IndexError
from package.utils import converter
from concurrent.futures._base import TimeoutError
from package.parser.baseParser import ParserBase, LoadPropertyPageException, \
    ReadPropertyNameException
import logging
from package.utils.selector_loader import SelectorLoader


class SumifuParser(ParserBase):
    BASE_URL='https://www.stepon.co.jp'

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('sumifu', self.property_type)
    def getCharset(self):
        return "CP932"

    def createEntity(self):
        pass

    def getRegionXpath(self):
        return u''

    def getRegionDestUrl(self,linkUrl):
        return self.BASE_URL + linkUrl

    async def parseRegionPage(self, response):
        async for destUrl in self._parsePageCore(response, self.getRegionXpath, self.getRegionDestUrl):
            print(destUrl)
            yield destUrl

    def getAreaXpath(self):
        return u''

    def getAreaDestUrl(self,linkUrl):
        return self.BASE_URL + linkUrl + "?limit=1000&mode=2"

    async def parseAreaPage(self, response):       
        async for destUrl in self._parsePageCore(response, self.getAreaXpath, self.getAreaDestUrl):
            yield destUrl

    def getPropertyListXpath(self):
        return u''

    def getPropertyListDestUrl(self,linkUrl):
        return linkUrl

    async def parsePropertyListPage(self, response):
        async for destUrl in self._parsePageCore(response, self.getPropertyListXpath, self.getPropertyListDestUrl):
            yield destUrl

    async def getPropertyListNextPageUrl(self, response):
        logging.info("getPropertyListNextPageUrl")
        next_page_selector = self.selectors.get('next_page')
        next_link = response.select_one(next_page_selector)
        # Or simpler search for text "次へ"
        if not next_link:
             # Try finding by text "次へ"
             next_link = response.find('a', string=re.compile("次へ"))

        if not next_link:
            return None
            
        nextPageUrl = self.BASE_URL + next_link.get("href")
        logging.info("getPropertyListNextPageUrl nextPageUrl:" + nextPageUrl)
        return nextPageUrl

    def _getValueFromTable(self, response, target_th_text):
        table_config = self.selectors.get('table', {})
        table_selector = table_config.get('selector', 'table.table-detail')
        header_selector = table_config.get('header', 'th')
        value_selector = table_config.get('value', 'td')

        ths = response.select(f"{table_selector} {header_selector}")
        for th in ths:
            if target_th_text in th.get_text():
                td = th.find_next_sibling(value_selector)
                if td:
                    return td
                if td:
                    return td
        return None

    def _parseChikunengetsuText(self, text):
        if not text: return None
        # Example: 1998年3月
        try:
            m = re.match(r'(\d+)年(\d+)月', text.strip())
            if m:
                year = int(m.group(1))
                month = int(m.group(2))
                return datetime.date(year, month, 1)
        except:
            pass
        return None

    def _parseKenpeiYousekiText(self, text):
        # Example: 建ぺい率60% 容積率200%
        kenpei = None
        youseki = None
        try:
            k_match = re.search(r'建ぺい率(\d+)%', text)
            if k_match:
                kenpei = int(k_match.group(1))
            
            y_match = re.search(r'容積率(\d+)%', text)
            if y_match:
                youseki = int(y_match.group(1))
        except:
            pass
        return kenpei, youseki

    def _getChimokuChiseiText(self, item, text):
        # Implement parsing if needed, or just store generic text to a field?
        # SumifuTochi/Kodate has fields like chimoku, chisei.
        # The parser calls this, assuming it modifies item.
        # For simplicity, assign to chimoku if '地目' in key context, but here just raw text.
        # Let's try to split or assign.
        # Actually, simpler to just assign to item.chimokuChisei if exists, or separate.
        # Let's assume text is like "地目：宅地" or just "宅地"
        if hasattr(item, 'chimoku'): item.chimoku = text
        if hasattr(item, 'chisei'): item.chisei = text # Rough

    def _getSetudouText(self, item, text):
        if hasattr(item, 'setsudou'): item.setsudou = text
        if hasattr(item, 'roadCondition'): item.roadCondition = text

    def _getChiikiChikuText(self, item, text):
        if hasattr(item, 'chiikiChiku'): item.chiikiChiku = text
        if hasattr(item, 'urbanPlanning'): item.urbanPlanning = text

    MAPPING = {
        "価格": ("priceStr", None),
        "所在地": ("address", None),
        "交通": ("transportStr", None), # Special handling
        "引渡時期": ("hikiwatashi", None),
        "現況": ("genkyo", None),
        "土地権利": ("tochikenri", None),
        "取引態様": ("torihiki", None),
        "備考": ("biko", None),
    }

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        try:
            # New Name Selector
            name_selector = self.selectors.get('title')
            name_tag = response.select_one(name_selector)
            
            if not name_tag:
                 # Fallback
                 name_block_selector = self.selectors.get('name_block_fallback')
                 if name_block_selector:
                     name_block = response.select_one(name_block_selector)
                     if name_block:
                         # Safe traversal
                         h2s = name_block.find_all("h2")
                         if h2s:
                             spans = h2s[0].find_all("span")
                             if len(spans) > 1:
                                 name_tag = spans[1]
            
            if name_tag:
                item.propertyName = name_tag.get_text(strip=True)
            
            if not getattr(item, 'propertyName', None):
                # Try generic h1 if specific classes failed or were empty
                name_tag = response.select_one("h1")
                if name_tag:
                    item.propertyName = name_tag.get_text(strip=True)

            if not getattr(item, 'propertyName', None):
                logging.warn("Could not find property name")
                raise ReadPropertyNameException()

        except Exception:
            logging.error(traceback.format_exc())
            raise ReadPropertyNameException()
        
        
        # Extract fields from table using existing _getValueFromTable method
        # Price
        price_key = self.selectors.get('price_key', "価格")
        price_td = self._getValueFromTable(response, price_key)
        if price_td:
            price_text = price_td.get_text(strip=True)
            price_text = re.split(r"\(", price_text)[0]
            item.priceStr = price_text
            item.price = converter.parse_price(item.priceStr)
        else:
             # Fallback
             try:
                price_selector = self.selectors.get('price')
                if price_selector:
                    em = response.select_one(price_selector)
                    if em:
                        item.priceStr = em.get_text(strip=True)
                        item.price = converter.parse_price(item.priceStr)
             except:
                 logging.warn("Could not find price")
        
        # Address
        address_key = self.selectors.get('address_key', "所在地")
        address_td = self._getValueFromTable(response, address_key)
        if address_td:
            item.address = address_td.get_text(strip=True)

        # Address Fallback
        if not getattr(item, "address", None):
            try:
                address_selector = self.selectors.get('address')
                if address_selector:
                    addr_elem = response.select_one(address_selector)
                    if addr_elem:
                        item.address = addr_elem.get_text(strip=True)
            except:
                 pass

        
        # Extract other fields from MAPPING
        hiki_key = self.selectors.get('hikiwatashi_key', "引渡時期")
        hikiwatashi_td = self._getValueFromTable(response, hiki_key)
        if hikiwatashi_td:
            item.hikiwatashi = hikiwatashi_td.get_text(strip=True)
        
        genkyo_key = self.selectors.get('genkyo_key', "現況")
        genkyo_td = self._getValueFromTable(response, genkyo_key)
        if genkyo_td:
            item.genkyo = genkyo_td.get_text(strip=True)
        
        kenri_key = self.selectors.get('tochikenri_key', "土地権利")
        tochikenri_td = self._getValueFromTable(response, kenri_key)
        if tochikenri_td:
            item.tochikenri = tochikenri_td.get_text(strip=True)
        
        torihiki_key = self.selectors.get('torihiki_key', "取引態様")
        torihiki_td = self._getValueFromTable(response, torihiki_key)
        if torihiki_td:
            item.torihiki = torihiki_td.get_text(strip=True)
        
        biko_key = self.selectors.get('biko_key', "備考")
        biko_td = self._getValueFromTable(response, biko_key)
        if biko_td:
            item.biko = converter.truncate_str(biko_td.get_text(strip=True), 2000).strip()
        
        # Reset transport fields
        item.transfer1 = ""
        item.railway1 = ""
        item.station1 = ""
        item.railwayWalkMinute1Str = ""
        item.railwayWalkMinute1 = 0
        item.busStation1 = ""
        item.busWalkMinute1Str = ""
        item.busWalkMinute1 = 0
        item.busWalkMinute2 = 0
        item.busWalkMinute3 = 0
        item.busWalkMinute4 = 0
        item.busWalkMinute5 = 0
        item.railwayWalkMinute2 = 0
        item.railwayWalkMinute3 = 0
        item.railwayWalkMinute4 = 0
        item.railwayWalkMinute5 = 0


        # Transportation Logic
        transport_key = self.selectors.get('transport_key', "交通")
        transport_td = self._getValueFromTable(response, transport_key)

        if transport_td:
            # Replace br with newlines for splitting
            for br in transport_td.select("br"):
                br.replace_with("\n")
            
            # Text might be: "JR山手線 「品川」駅 徒歩10分\n京急本線 「北品川」駅 徒歩5分"
            full_text = transport_td.get_text("\n").strip() # Use newline as separator
            lines = [line.strip() for line in full_text.split("\n") if line.strip()]
            
            item.railwayCount = len(lines)
            
            for i, line in enumerate(lines):
                if i >= 5: break
                try:
                    match = re.search(r'(.*?)「(.*?)」(.*)', line)
                    if match:
                        railway = match.group(1).strip().replace("線駅", "線") # Cleanup
                        station = match.group(2).strip()
                        walk_part = match.group(3).strip() # "駅 徒歩10分" or similar
                        
                        if walk_part.startswith("駅"):
                            walk_part = walk_part[1:].strip()
                            
                        walk_min = 0
                        walk_min_str = ""
                        num_match = re.search(r'徒歩(\d+)分', walk_part)
                        if num_match:
                            walk_min_str = num_match.group(1)
                            walk_min = int(walk_min_str)
                        
                        bus_stop = ""
                        bus_min_str = ""
                        bus_min = 0
                        if "バス" in walk_part:
                             bus_match = re.search(r'バス(\d+)分', walk_part)
                             if bus_match:
                                 bus_min_str = bus_match.group(1)
                                 bus_min = int(bus_match.group(1))
                             
                             stop_match = re.search(r'「(.*?)」', walk_part) # Bus stop name
                             if stop_match:
                                 bus_stop = stop_match.group(1)
                        
                        if i == 0:
                             item.transfer1, item.railway1, item.station1 = line, railway, station
                             item.railwayWalkMinute1Str, item.railwayWalkMinute1 = walk_min_str, walk_min
                             item.busStation1, item.busWalkMinute1Str, item.busWalkMinute1 = bus_stop, bus_min_str, bus_min
                        elif i == 1:
                             item.transfer2, item.railway2, item.station2 = line, railway, station
                             item.railwayWalkMinute2Str, item.railwayWalkMinute2 = walk_min_str, walk_min
                             item.busStation2, item.busWalkMinute2Str, item.busWalkMinute2 = bus_stop, bus_min_str, bus_min
                        elif i == 2:
                             item.transfer3, item.railway3, item.station3 = line, railway, station
                             item.railwayWalkMinute3Str, item.railwayWalkMinute3 = walk_min_str, walk_min
                             item.busStation3, item.busWalkMinute3Str, item.busWalkMinute3 = bus_stop, bus_min_str, bus_min
                        elif i == 3:
                             item.transfer4, item.railway4, item.station4 = line, railway, station
                             item.railwayWalkMinute4Str, item.railwayWalkMinute4 = walk_min_str, walk_min
                             item.busStation4, item.busWalkMinute4Str, item.busWalkMinute4 = bus_stop, bus_min_str, bus_min
                        elif i == 4:
                             item.transfer5, item.railway5, item.station5 = line, railway, station
                             item.railwayWalkMinute5Str, item.railwayWalkMinute5 = walk_min_str, walk_min
                             item.busStation5, item.busWalkMinute5Str, item.busWalkMinute5 = bus_stop, bus_min_str, bus_min
                    else:
                        logging.warn(f"Could not parse line: {line}")
                except:
                    logging.warn(f"Error parsing transport line: {line}")

        else:
             # Fallback
             pass
        

        item.busUse1 = 0
        if(item.busWalkMinute1 > 0):
            item.busUse1 = 1
 
        return item

        count = 0
        sliced_text:str = ''
        for c in text:
            if unicodedata.east_asian_width(c) in 'FWA':
                count += 2
            else:
                count += 1

            # lenと同じ長さになったときに抽出完了
            if count > len:
                break
            sliced_text += c
        return sliced_text        

        
class SumifuInvestmentParser(InvestmentParser):
    property_type = 'investment'
    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('sumifu', self.property_type)
    def getCharset(self):
        return "utf-8"

    def createEntity(self) -> models.Model:
        return SumifuInvestment()

    def _getValueFromTable(self, response: BeautifulSoup, title: str):
        rows = response.select("table.table-detail tr")
        for tr in rows:
            th = tr.select_one("th")
            td = tr.select_one("td")
            if th and td and title in th.get_text():
                return td
        return None

    def parsePropertyListPage(self, response: BeautifulSoup):
        property_links_selector = self.selectors.get('property_links')
        links = response.select(property_links_selector)
        if not links:
             # Fallback
             fallback_selector = self.selectors.get('property_links_fallback')
             if fallback_selector:
                 links = response.select(fallback_selector)
             
        for link in links:
            href = link.get("href")
            if href.startswith("/"):
                href = "https://www.stepon.co.jp" + href
            yield href

    def parseNextPage(self, response: BeautifulSoup):
        # Text search for '次へ'
        next_text = self.selectors.get('next_page')
        next_link = response.find("a", string=lambda t: t and next_text in t)
        if next_link:
            href = next_link.get("href")
            # For Sumifu, pagination might be javascript post or URL part
            # Based on docs: /pro/ca_0_001/30_2/
            if href and href != "#":
                if href.startswith("/"):
                    return "https://www.stepon.co.jp" + href
                return href
        return ""

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        try:
            # New Name Selector
            name_selector = self.selectors.get('title')
            name_tag = response.select_one(name_selector)
            
            if not name_tag:
                 # Fallback
                 name_block_selector = self.selectors.get('name_block_fallback')
                 if name_block_selector:
                     name_block = response.select_one(name_block_selector)
                     if name_block:
                         # Safe traversal
                         h2s = name_block.find_all("h2")
                         if h2s:
                             spans = h2s[0].find_all("span")
                             if len(spans) > 1:
                                 name_tag = spans[1]
            
            if name_tag:
                item.propertyName = name_tag.get_text(strip=True)
            
            if not getattr(item, 'propertyName', None):
                # Try generic h1 if specific classes failed or were empty
                name_tag = response.select_one("h1")
                if name_tag:
                    item.propertyName = name_tag.get_text(strip=True)

            if not getattr(item, 'propertyName', None):
                logging.warn("Could not find property name")
                raise ReadPropertyNameException()

        except Exception:
            logging.error(traceback.format_exc())
            raise ReadPropertyNameException()
        
        # Price
        price_key = self.selectors.get('price_key', "価格")
        price_td = self._getValueFromTable(response, price_key)
        if price_td:
            # Handle cases like "5,980万円"
            price_text = price_td.get_text(strip=True)
            # Remove annotations like "(税込)"
            price_text = re.split(r"\(", price_text)[0] 
            item.priceStr = price_text
            
            priceWork = item.priceStr.replace(',', '').replace(u'万円', '')
            # If "億" exists
            oku = 0
            man = 0
            if u"億" in priceWork:
                parts = priceWork.split(u"億")
                if parts[0]:
                    oku = int(parts[0]) * 10000
                if len(parts) > 1 and parts[1]:
                    man = int(parts[1])
            else:
                try:
                    # Extract digits only to avoid "ローンシミュレーション" etc
                    digit_match = re.search(r'\d+', priceWork)
                    if digit_match:
                        man = int(digit_match.group())
                    else:
                        man = 0
                except:
                    man = 0
            item.price = oku + man
        else:
             # Old selector fallback
             try:
                price_selector = self.selectors.get('price')
                if price_selector:
                    em = response.select_one(price_selector)
                    if em:
                        item.priceStr = em.get_text(strip=True)
                        priceWork = item.priceStr.replace(',', '')
                        oku = 0
                        man = 0
                        if u"億" in item.priceStr:
                            priceArr = priceWork.split("億")
                            oku = int(priceArr[0]) * 10000
                            if len(priceArr) > 1 and len(priceArr[1]) != 0:
                                man = int(priceArr[1])
                        else:
                            digits = re.sub(r'\D', '', priceWork)
                            if digits:
                                man = int(digits)
                        item.price = oku + man
             except:
                 logging.warn("Could not find price")

        # Address
        address_key = self.selectors.get('address_key', "所在地")
        address_td = self._getValueFromTable(response, address_key)
        if address_td:
            item.address = address_td.get_text(strip=True)
        else:
            try:
                address_selector = self.selectors.get('address')
                if address_selector:
                    addr_elem = response.select_one(address_selector)
                    if addr_elem:
                        item.address = addr_elem.get_text(strip=True)
            except:
                 pass

        # Reset transport fields
        item.transfer1 = ""
        item.railway1 = ""
        item.station1 = ""
        item.railwayWalkMinute1Str = ""
        item.railwayWalkMinute1 = 0
        item.busStation1 = ""
        item.busWalkMinute1Str = ""
        item.busWalkMinute1 = 0

        item.transfer2 = ""
        item.railway2 = ""
        item.station2 = ""
        item.railwayWalkMinute2Str = ""
        item.railwayWalkMinute2 = 0
        item.busStation2 = ""
        item.busWalkMinute2Str = ""
        item.busWalkMinute2 = 0

        item.transfer3 = ""
        item.railway3 = ""
        item.station3 = ""
        item.railwayWalkMinute3Str = ""
        item.railwayWalkMinute3 = 0
        item.busStation3 = ""
        item.busWalkMinute3Str = ""
        item.busWalkMinute3 = 0

        item.transfer4 = ""
        item.railway4 = ""
        item.station4 = ""
        item.railwayWalkMinute4Str = ""
        item.railwayWalkMinute4 = 0
        item.busStation4 = ""
        item.busWalkMinute4Str = ""
        item.busWalkMinute4 = 0

        item.transfer5 = ""
        item.railway5 = ""
        item.station5 = ""
        item.railwayWalkMinute5Str = ""
        item.railwayWalkMinute5 = 0
        item.busStation5 = ""
        item.busWalkMinute5Str = ""
        item.busWalkMinute5 = 0

        # Transportation
        transport_td = self._getValueFromTable(response, "交通")
        if transport_td:
            # Replace br with newlines for splitting
            for br in transport_td.select("br"):
                br.replace_with("\n")
            
            # Text might be: "JR山手線 「品川」駅 徒歩10分\n京急本線 「北品川」駅 徒歩5分"
            full_text = transport_td.get_text().strip()
            lines = [line.strip() for line in full_text.split("\n") if line.strip()]
            
            item.railwayCount = len(lines)
            
            for i, line in enumerate(lines):
                if i >= 5: break
                # Parse line: "JR山手線 「品川」駅 徒歩10分"
                # Heuristic: split by space? Or use regex?
                # Existing logic expects: Railway, Station, Walk
                # Let's try to adapt existing generic parsing or simplified regex
                # regex for "Line 「Station」 Walk"
                # Match: (.*?) 「(.*?)」 (.*)
                try:
                    match = re.search(r'(.*?)「(.*?)」(.*)', line)
                    if match:
                        railway = match.group(1).strip().replace("線駅", "線") # Cleanup
                        station = match.group(2).strip()
                        walk_part = match.group(3).strip() # "駅 徒歩10分" or similar
                        
                        # walk_part might start with "駅", remove it
                        if walk_part.startswith("駅"):
                            walk_part = walk_part[1:].strip()
                            
                        # Logic to extract minutes
                        walk_min = 0
                        walk_min_str = ""
                        
                        # Try to find number in walk_part
                        num_match = re.search(r'徒歩(\d+)分', walk_part)
                        if num_match:
                            walk_min_str = num_match.group(1)
                            walk_min = int(walk_min_str)
                        
                        # Bus logic
                        bus_stop = ""
                        bus_min_str = ""
                        bus_min = 0
                        if "バス" in walk_part:
                             bus_match = re.search(r'バス(\d+)分', walk_part)
                             if bus_match:
                                 bus_min_str = bus_match.group(1)
                                 bus_min = int(bus_match.group(1))
                             
                             stop_match = re.search(r'「(.*?)」', walk_part) # Bus stop name
                             if stop_match:
                                 bus_stop = stop_match.group(1)
                        
                        # Assign to item fields
                        if i == 0:
                             item.transfer1, item.railway1, item.station1 = line, railway, station
                             item.railwayWalkMinute1Str, item.railwayWalkMinute1 = walk_min_str, walk_min
                             item.busStation1, item.busWalkMinute1Str, item.busWalkMinute1 = bus_stop, bus_min_str, bus_min
                        elif i == 1:
                             item.transfer2, item.railway2, item.station2 = line, railway, station
                             item.railwayWalkMinute2Str, item.railwayWalkMinute2 = walk_min_str, walk_min
                             item.busStation2, item.busWalkMinute2Str, item.busWalkMinute2 = bus_stop, bus_min_str, bus_min
                        elif i == 2:
                             item.transfer3, item.railway3, item.station3 = line, railway, station
                             item.railwayWalkMinute3Str, item.railwayWalkMinute3 = walk_min_str, walk_min
                             item.busStation3, item.busWalkMinute3Str, item.busWalkMinute3 = bus_stop, bus_min_str, bus_min
                        elif i == 3:
                             item.transfer4, item.railway4, item.station4 = line, railway, station
                             item.railwayWalkMinute4Str, item.railwayWalkMinute4 = walk_min_str, walk_min
                             item.busStation4, item.busWalkMinute4Str, item.busWalkMinute4 = bus_stop, bus_min_str, bus_min
                        elif i == 4:
                             item.transfer5, item.railway5, item.station5 = line, railway, station
                             item.railwayWalkMinute5Str, item.railwayWalkMinute5 = walk_min_str, walk_min
                             item.busStation5, item.busWalkMinute5Str, item.busWalkMinute5 = bus_stop, bus_min_str, bus_min
                    else:
                        logging.warn(f"Could not parse line: {line}")
                except:
                    logging.warn(f"Error parsing transport line: {line}")

        else:
             # Fallback to old logic (simplified)
            # Fallback to old logic (simplified)
            try:
                for i in response.select("br"):
                    i.replace_with("\n")
                
                transfer_dd = response.select_one('dd[id="s_summaryTransfer"]')
                if transfer_dd:
                    transferList = re.split("\n", transfer_dd.get_text())
                    transList = transfer_dd.select('a')
                    item.railwayCount = int(len(transList) // 2)
                    for i in range(item.railwayCount):
                        try:
                            if len(transList) > i * 2 + 1:
                                railway = transList[i * 2].get_text(strip=True)
                                station = transList[i * 2 + 1].get_text(strip=True)
                                
                                if len(transferList) > i:
                                    transfer = transferList[i].replace(" ", "")
                                    wkTransferList = transfer.split("」駅")
                                    if len(wkTransferList) > 1:
                                        walkStr = "」駅より" + wkTransferList[1]
                                        
                                        vals = self.__getRailWayPropertyValues(transfer, railway, station, walkStr)
                                        # vals tuple: transfer, railway, station, railWalkStr, railWalk, busSt, busWalkStr, busWalk
                                        
                                        if i == 0:
                                            item.transfer1, item.railway1, item.station1, item.railwayWalkMinute1Str, item.railwayWalkMinute1, item.busStation1, item.busWalkMinute1Str, item.busWalkMinute1 = vals
                                        elif i == 1:
                                            item.transfer2, item.railway2, item.station2, item.railwayWalkMinute2Str, item.railwayWalkMinute2, item.busStation2, item.busWalkMinute2Str, item.busWalkMinute2 = vals
                                        elif i == 2:
                                            item.transfer3, item.railway3, item.station3, item.railwayWalkMinute3Str, item.railwayWalkMinute3, item.busStation3, item.busWalkMinute3Str, item.busWalkMinute3 = vals
                                        elif i == 3:
                                            item.transfer4, item.railway4, item.station4, item.railwayWalkMinute4Str, item.railwayWalkMinute4, item.busStation4, item.busWalkMinute4Str, item.busWalkMinute4 = vals
                                        elif i == 4:
                                            item.transfer5, item.railway5, item.station5, item.railwayWalkMinute5Str, item.railwayWalkMinute5, item.busStation5, item.busWalkMinute5Str, item.busWalkMinute5 = vals

                        except IndexError:
                             logging.warn("IndexError in transport fallback")
            except Exception:
                pass


        item.busUse1 = 0
        if(item.busWalkMinute1 > 0):
            item.busUse1 = 1
 
        # Parse Generic Table Rows (Hikiwatashi, Genkyo, etc)
        # Iterate table again or use helper
        # Current logic iterates trs in detailBlock.
        # New structure: table.table-detail
        
        detail_rows = response.select("table.table-detail tr")
        for tr in detail_rows:
            ths = tr.select("th")
            tds = tr.select("td")
            if not ths or not tds: continue
            
            thTitle = ths[0].get_text(strip=True)
            tdValue = tds[0].get_text(strip=True)
            
            if "引渡時期" in thTitle:
                item.hikiwatashi = tdValue
            elif "現況" in thTitle:
                item.genkyo = tdValue
            elif "土地権利" in thTitle:
                item.tochikenri = tdValue
            elif "取引態様" in thTitle:
                item.torihiki = tdValue
            elif "備考" in thTitle:
                item.biko = self.truncate_double_byte_str(tdValue,2000).strip()

        return item

    def truncate_double_byte_str(self,text, len)->str:
        """ 全角・半角を区別して文字列を切り詰める
            """
        count = 0
        sliced_text:str = ''
        for c in text:
            if unicodedata.east_asian_width(c) in 'FWA':
                count += 2
            else:
                count += 1

            # lenと同じ長さになったときに抽出完了
            if count > len:
                break
            sliced_text += c
        return sliced_text        

    def __getRailWayPropertyValues(self, _transfer, _railway, _station, _walkStr):
        try:
            _railwayWalkMinuteStr = self.__getRailwayWalkText(_walkStr)
            _railwayWalkMinute = int(_railwayWalkMinuteStr)
            _busStation = self.__getBusStationText(_walkStr)
            _busWalkMinuteStr = self.__getBusWalkText(_walkStr)
            _busWalkMinute = int(_busWalkMinuteStr)
            return _transfer, _railway, _station, _railwayWalkMinuteStr, _railwayWalkMinute, _busStation, _busWalkMinuteStr, _busWalkMinute
        except ValueError as e:
            logging.warn(traceback.format_exc())
            raise LoadPropertyPageException()
        except Exception as e:
            logging.error("error __getRailWayPropertyValues:" + _walkStr)
            logging.error("error __getRailWayPropertyValues:" + _railwayWalkMinuteStr)
            raise e

    def __getPropertyValues(self, transList1, transList2, i):
        _transfer1 = self.__getTransferText(transList1, transList2, i)
        _railway1 = self.__getRailwayText(transList2, i)
        _station1 = self.__getRailwayStationText(transList2, i)
        _railwayWalkMinute1Str = self.__getRailwayWalkText(transList1[i + 1])
        if len(_railwayWalkMinute1Str) > 0:
            _railwayWalkMinute1 = int(_railwayWalkMinute1Str)
        _busStation1 = self.__getBusStationText(transList1[i + 1])
        _busWalkMinute1Str = self.__getBusWalkText(transList1[i + 1])
        _busWalkMinute1 = 0
        if len(_busWalkMinute1Str) > 0:
            _busWalkMinute1 = int(_busWalkMinute1Str)

        return _transfer1, _railway1, _station1, _railwayWalkMinute1Str, _railwayWalkMinute1, _busStation1, _busWalkMinute1Str, _busWalkMinute1


    def __getTransferText(self, transList1, transList2, i):
        sum_transfer = transList1[i] + self.__getRailwayText(transList2, i) + self.__getRailwayStationText(transList2, i) + transList1[i + 1].replace(' ', '')
        return sum_transfer

    def __getRailwayText(self, transList2, i):
        return transList2[i]

    def __getRailwayStationText(self, transList2, i):
        return transList2[i + 1]

    def __getBusStationText(self, walkStr):
        if u"バス" in walkStr:
            return walkStr[walkStr.find(u"「") + 1:walkStr.rfind(u"」")]
        return ""

    def __getWalkMinute(self, walkStr):
        return walkStr[walkStr.find(u"徒歩") + 2:walkStr.rfind(u"分")].replace(' ', '')

    def __getRailwayWalkText(self, walkStr):
        if u"バス" in walkStr:
            return "0"
        return self.__getWalkMinute(walkStr)

    def __getBusWalkText(self, walkStr):
        if u"バス" in walkStr:
            return self.__getWalkMinute(walkStr)
        return "0"

    def _getChimokuChiseiText(self, item, value):
        item.chimokuChisei = value
        item.chimoku = item.chimokuChisei.split("／")[0]
        item.chisei=""
        if (len(item.chimokuChisei.split("／"))>=2):
            item.chisei = item.chimokuChisei.split("／")[len(item.chimokuChisei.split("／"))-1]


    def _getSetudouText(self, item, value):
        item.setsudou = value
        if (item.setsudou.find("・")>-1):
            item.douro = item.setsudou.split("・")[0]

        for wkStr in item.setsudou.split("／"):
            if (wkStr.find("m")>-1):
                if (wkStr.find("・")>-1):
                    wkStr=wkStr.split("・")[1]
                douroHabaObj = re.search(r'[0-9\.]+', wkStr.split("m")[0])
                if (float(douroHabaObj.group())>float(item.douroHaba)):#複数ある場合、一番道路幅が広い面を
                    item.douroHaba = douroHabaObj.group()
                    item.douroKubun = wkStr.split("(")[1].split(")")[0]
                    item.douroMuki = wkStr.split("m")[0][0:(douroHabaObj.start())]
                    item.setsumen = wkStr.split("m")[1].split("接面")[1].replace("m","")

    def _getChiikiChikuText(self, item, value):
        item.chiikiChiku = value
        item.kuiki = ""
        item.youtoChiiki=""
        item.boukaChiiki=""
        item.sonotaChiiki=""
        for wkStr in item.chiikiChiku.split("／"):
            if (wkStr in ['市街化区域','市街化調整区域']):
                item.kuiki = wkStr
            elif (wkStr in ['第１種低層住居専用地域','第２種低層住居専用地域','第１種中高層住居専用地域','第２種中高層住居専用地域','第１種住居地域','第２種住居地域','準住居地域','田園住居地域','近隣商業地域','商業地域','準工業地域','工業地域','工業専用地域','無指定']):
                item.youtoChiiki = wkStr
            elif (wkStr.find("防火地域")>-1):
                item.boukaChiiki = wkStr
            elif (wkStr.find("再建築不可")>-1):
                item.saikenchiku = wkStr
            else :
                if(len(item.sonotaChiiki)>0):
                    item.sonotaChiiki = item.sonotaChiiki +"／"+ wkStr
                else:
                    item.sonotaChiiki = wkStr

    def _parseChikunengetsuText(self, item):
        if (item.chikunengetsuStr == u"築年月不詳"):
            nen = 1900
            tsuki = 1
        else:
            nen = int(item.chikunengetsuStr.split(u"年")[0])
            tsuki = int(item.chikunengetsuStr.split(u"年")[1].split(u"月")[0])
        item.chikunengetsu = datetime.date(nen, tsuki, 1)

    def _parseKenpeiYousekiText(self, item):
        item.kenpei = item.kenpeiYousekiStr.split("／")[0].split("%")[0].split(" ")[0]
        item.youseki = item.kenpeiYousekiStr.split("／")[1].split("%")[0].split(" ")[0]

class SumifuMansionParser(SumifuParser):
    property_type = 'mansion'

    def getRegionXpath(self):
        return self.selectors.get('region_xpath')

    def getAreaXpath(self):
        return self.selectors.get('area_xpath')

    def getPropertyListXpath(self):
        return self.selectors.get('property_list_xpath')

    def createEntity(self):
        return  SumifuMansion()
            
    MAPPING = SumifuParser.MAPPING.copy()
    MAPPING.update({
        "間取り": ("madori", None),
        "専有面積": ("senyuMensekiStr", None),
        "階建": ("floorType", None), # Try both 階建 and 階?
        "階": ("floorType", None),
        "築年月": ("chikunengetsuStr", None), # Base processes this logic but mapping helps? Base doesn't map chikunengetsuStr in MAPPING.
        "バルコニー": ("barukoniMensekiStr", None), # search contains 'バルコニー' and '面積'
        "採光方向": ("saikouKadobeya", None),
        "総戸数": ("soukosuStr", None),
        "管理方式": ("kanriKeitaiKaisya", None),
        "管理会社": ("kanriKeitaiKaisya", None),
        "管理費": ("kanrihiStr", None),
        "修繕積立金": ("syuzenTsumitateStr", None),
        "駐車場": ("tyusyajo", None),
        "施工会社": ("sekouKaisya", None),
        # Base handles Tochikenri, Hikiwatashi, Genkyo, Torihiki, Biko
    })

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item:SumifuMansion=super()._parsePropertyDetailPage(item, response)

        # Extract mansion-specific fields from MAPPING
        for field_name_jp, (field_name_en, _) in self.MAPPING.items():
            if field_name_jp not in ["価格", "所在地", "交通", "引渡時期", "現況", "土地権利", "取引態様", "備考"]:
                # Skip fields already handled by parent class
                td = self._getValueFromTable(response, field_name_jp)
                if td and hasattr(item, field_name_en):
                    setattr(item, field_name_en, td.get_text(strip=True))
        
        if hasattr(item, "senyuMensekiStr") and item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)

        # Floor / Structure logic
        if not item.floorType:
            # Fallback
            try:
                elem = response.select_one("dl#s_summaryFloor dd")
                if elem: item.floorType = elem.get_text(strip=True)
            except: pass

        if item.floorType:
            try:
                # Use simplified or existing regex logic
                part_match = re.search(r'(\d+)階部分', item.floorType)
                if not part_match: part_match = re.search(r'/\s*(\d+)階', item.floorType)
                
                if part_match:
                    item.floorType_kai = int(part_match.group(1))
                    if "地下" in item.floorType and "地下" in item.floorType.split(part_match.group(0))[0]: 
                         item.floorType_kai = -item.floorType_kai
                
                total_match = re.search(r'地上(\d+)階', item.floorType)
                if total_match: item.floorType_chijo = int(total_match.group(1))
                else: 
                     total_match = re.search(r'(\d+)階建', item.floorType)
                     if total_match: item.floorType_chijo = int(total_match.group(1))

                chika_match = re.search(r'地下(\d+)階', item.floorType)
                if chika_match: item.floorType_chika = int(chika_match.group(1))
                else: item.floorType_chika = 0
            except: pass
        
        # Chikunengetsu
        if not getattr(item, 'chikunengetsuStr', None):
              try:
                  elem = response.select_one("dl#s_summaryChikunengetsu dd")
                  if elem: item.chikunengetsuStr = elem.get_text(strip=True)
              except: pass
        
        if getattr(item, 'chikunengetsuStr', None):
             item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr) # Use converter!

        # Saikou / Kadobeya
        if getattr(item, "saikouKadobeya", None):
             temp = item.saikouKadobeya.split(u"／")
             if len(temp) == 1:
                 item.saikou = item.saikouKadobeya
                 item.kadobeya = ""
             else:
                 item.saikou = temp[0]
                 item.kadobeya = temp[1]

        # Soukosu
        if getattr(item, "soukosuStr", None):
             item.soukosu = converter.parse_numeric(item.soukosuStr)

        # Kanri
        if getattr(item, "kanriKeitaiKaisya", None):
             temp = item.kanriKeitaiKaisya.split(u"／")
             if len(temp) == 1:
                 item.kanriKeitai = temp[0]
                 item.kanriKaisya = ""
             else:
                 item.kanriKeitai = temp[0]
                 item.kanriKaisya = temp[1]

        # Kanrihi / Syuzen
        if getattr(item, "kanrihiStr", None):
             item.kanrihi = converter.parse_price(item.kanrihiStr) # Check unit? Usually 円. parse_price handles numbers ok?
             # parse_price expects X万X円 or numeric string
             if "万" not in item.kanrihiStr and "円" not in item.kanrihiStr: # just digits
                  try: item.kanrihi = int(re.sub(r'\D', '', item.kanrihiStr))
                  except: item.kanrihi = 0
             else:
                  item.kanrihi = converter.parse_price(item.kanrihiStr)

        if getattr(item, "syuzenTsumitateStr", None):
             if "万" not in item.syuzenTsumitateStr and "円" not in item.syuzenTsumitateStr: 
                  try: item.syuzenTsumitate = int(re.sub(r'\D', '', item.syuzenTsumitateStr))
                  except: item.syuzenTsumitate = 0
             else:
                  item.syuzenTsumitate = converter.parse_price(item.syuzenTsumitateStr)

        # Defaults and derived
        item.kaisu = ""
        item.kouzou = ""
        item.address1 = ""
        item.address2 = ""
        item.address3 = ""
        item.addressKyoto = ""
        item.sonotaHiyouStr = ""
        item.bunjoKaisya = ""
        
        if getattr(item, "floorType", ""):
            if(item.floorType.count(u"・ＲＣ造") > 0): item.floorType_kouzou = "ＲＣ造"
            elif(item.floorType.count(u"・ＳＲＣ造") > 0): item.floorType_kouzou = "ＳＲＣ造"
            elif(item.floorType.count(u"・Ｓ造") > 0): item.floorType_kouzou = "Ｓ造"
            elif(item.floorType.count(u"・木造") > 0): item.floorType_kouzou = "木造"
            elif(item.floorType.count(u"・その他") > 0): item.floorType_kouzou = "その他"

        item.kyutaishin = 0
        if item.chikunengetsu and item.chikunengetsu < datetime.date(1982, 1, 1):
            item.kyutaishin = 1
            
        item.barukoniMenseki = 0
        if getattr(item, "barukoniMensekiStr", "-") != "-" and item.barukoniMensekiStr:
            item.barukoniMenseki = converter.parse_menseki(item.barukoniMensekiStr.split(u"／")[0])

        item.senyouNiwaMenseki = 0
        if getattr(item, "barukoniMensekiStr", ""):
             senyouNiwaList = item.barukoniMensekiStr.split(u"専用庭面積")
             if len(senyouNiwaList) > 1:
                 item.senyouNiwaMenseki = converter.parse_menseki(senyouNiwaList[1])

        item.roofBarukoniMenseki = 0
        if getattr(item, "barukoniMensekiStr", ""):
             roofList = item.barukoniMensekiStr.split(u"ルーフバルコニー面積")
             if len(roofList) > 1:
                 item.roofBarukoniMenseki = converter.parse_menseki(roofList[1])

        if item.senyuMenseki and item.senyuMenseki > 0:
             item.kanrihi_p_heibei = item.kanrihi / item.senyuMenseki
             item.syuzenTsumitate_p_heibei = item.syuzenTsumitate / item.senyuMenseki
        else:
             item.kanrihi_p_heibei = 0
             item.syuzenTsumitate_p_heibei = 0

        return item

class SumifuTochiParser(SumifuParser):
    property_type = 'tochi'
    
    def getRegionXpath(self):
        return self.selectors.get('region_xpath')

    def getAreaXpath(self):
        return self.selectors.get('area_xpath')

    def getPropertyListXpath(self):
        return self.selectors.get('property_list_xpath')

    def createEntity(self):
        return  SumifuTochi()

    MAPPING = SumifuParser.MAPPING.copy()
    MAPPING.update({
        "土地面積": ("tochiMensekiStr", None),
        "建ぺい率": ("kenpeiStr", None),
        "容積率": ("yousekiStr", None),
        "地目": ("chimokuChisei", None),
        "地勢": ("chimokuChisei", None),
        "接道状況": ("setsudou", None),
        "地域地区": ("chiikiChiku", None),
        "建築条件": ("kenchikuJoken", None),
        "国土法": ("kokudoHou", None),
    })

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item:SumifuTochi=super()._parsePropertyDetailPage(item, response)
        
        # Extract tochi-specific fields from MAPPING
        for field_name_jp, (field_name_en, _) in self.MAPPING.items():
            if field_name_jp not in ["価格", "所在地", "交通", "引渡時期", "現況", "土地権利", "取引態様", "備考"]:
                td = self._getValueFromTable(response, field_name_jp)
                if td and hasattr(item, field_name_en):
                    setattr(item, field_name_en, td.get_text(strip=True))
        
        if getattr(item, "tochiMensekiStr", None):
             try: item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
             except: item.tochiMenseki = 0
        elif not item.tochiMensekiStr:
             # Fallback
             try:
                 elem = response.select_one("dl#s_summaryTochiMenseki dd")
                 if elem: 
                     item.tochiMensekiStr = elem.get_text(strip=True)
                     item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
             except: pass

        # Kenpei / Youseki
        item.kenpeiYousekiStr = ""
        if getattr(item, "kenpeiStr", "") and getattr(item, "yousekiStr", ""):
             item.kenpeiYousekiStr = f"{item.kenpeiStr}／{item.yousekiStr}"
        elif not getattr(item, "kenpeiStr", ""):
              try:
                  item.kenpeiYousekiStr = response.find_all("dl", id="s_coverageLandVolume")[0].find_all("dd")[0].contents[0]
              except: pass

        if item.kenpeiYousekiStr:
             self._parseKenpeiYousekiText(item)

        # Chimoku / Chisei
        if getattr(item, "chimokuChisei", None):
             self._getChimokuChiseiText(item, item.chimokuChisei)
        
        # Setsudou
        if getattr(item, "setsudou", None):
             self._getSetudouText(item, item.setsudou)

        # Chiiki / Chiku
        if getattr(item, "chiikiChiku", None):
             self._getChiikiChikuText(item, item.chiikiChiku)
            
        return item
    
class SumifuKodateParser(SumifuParser):
    property_type = 'kodate'
    
    def getRegionXpath(self):
        return self.selectors.get('region_xpath')

    def getAreaXpath(self):
        return self.selectors.get('area_xpath')

    def getPropertyListXpath(self):
        return self.selectors.get('property_list_xpath')

    def createEntity(self):
        return  SumifuKodate()


    MAPPING = SumifuParser.MAPPING.copy()
    MAPPING.update({
        "土地面積": ("tochiMensekiStr", None),
        "建物面積": ("tatemonoMensekiStr", None),
        "間取り": ("madori", None),
        "築年月": ("chikunengetsuStr", None),
        "建ぺい率": ("kenpeiStr", None),
        "容積率": ("yousekiStr", None),
        "階数": ("kaisuKouzou", None),
        "構造": ("kaisuKouzou", None),
        "階建": ("kaisuKouzou", None),
        "地目": ("chimokuChisei", None),
        "地勢": ("chimokuChisei", None),
        "接道状況": ("setsudou", None),
        "地域地区": ("chiikiChiku", None),
        "建築条件": ("kenchikuJoken", None),
        "国土法": ("kokudoHou", None),
    })

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item:SumifuKodate=super()._parsePropertyDetailPage(item, response)
        
        # Extract kodate-specific fields from MAPPING
        for field_name_jp, (field_name_en, _) in self.MAPPING.items():
            if field_name_jp not in ["価格", "所在地", "交通", "引渡時期", "現況", "土地権利", "取引態様", "備考"]:
                td = self._getValueFromTable(response, field_name_jp)
                if td and hasattr(item, field_name_en):
                    setattr(item, field_name_en, td.get_text(strip=True))
        
        # Tochi Menseki
        if getattr(item, "tochiMensekiStr", None):
             item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
        else:
              try:
                  elem = response.select_one("dl#s_summaryTochiMenseki dd")
                  if elem:
                      item.tochiMensekiStr = elem.get_text(strip=True)
                      item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
              except: pass

        # Tatemono Menseki
        if getattr(item, "tatemonoMensekiStr", None):
             item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)
        else:
              try:
                  elem = response.select_one("dl#s_summaryTatemonoMenseki dd")
                  if elem:
                      item.tatemonoMensekiStr = elem.get_text(strip=True)
                      item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)
              except: pass

        # Madori
        if not getattr(item, "madori", None):
             try:
                elem = response.select_one("dl#s_summaryMadori dd em")
                if elem: item.madori = elem.get_text(strip=True)
             except: pass

        # Chikunengetsu
        if not getattr(item, "chikunengetsuStr", None):
             try:
                 elem = response.select_one("dl#s_summaryChikunengetsu dd")
                 if elem: item.chikunengetsuStr = elem.get_text(strip=True)
             except: pass
        if getattr(item, "chikunengetsuStr", None):
             self._parseChikunengetsuText(item)

        # Kenpei / Youseki
        item.kenpeiYousekiStr = ""
        if getattr(item, "kenpeiStr", "") and getattr(item, "yousekiStr", ""):
             item.kenpeiYousekiStr = f"{item.kenpeiStr}／{item.yousekiStr}"
        
        if item.kenpeiYousekiStr:
             self._parseKenpeiYousekiText(item)
        else:
             try:
                 item.kenpeiYousekiStr = response.find_all("dl", id="s_coverageLandVolume")[0].find_all("dd")[0].contents[0]
                 self._parseKenpeiYousekiText(item)
             except: pass
        
        # Kaisu / Kouzou
        if getattr(item, "kaisuKouzou", None):
             if "・" in item.kaisuKouzou:
                  parts = item.kaisuKouzou.split("・")
                  item.kaisu = parts[0]
                  item.kouzou = parts[1]
             else:
                  item.kaisu = item.kaisuKouzou
                  item.kouzou = ""

        # Chimoku / Chisei
        if getattr(item, "chimokuChisei", None):
             self._getChimokuChiseiText(item, item.chimokuChisei)
        
        # Setsudou
        if getattr(item, "setsudou", None):
             self._getSetudouText(item, item.setsudou)

        # Chiiki / Chiku
        if getattr(item, "chiikiChiku", None):
             self._getChiikiChikuText(item, item.chiikiChiku)

        # Already mapped in Base/SubMapping: KenchikuJoken, KokudoHou
        # But we need to check if they need processing? 
        # Base implementation used tdValue.strip() or assign. Sets them as strings. So OK.
        
        return item
    

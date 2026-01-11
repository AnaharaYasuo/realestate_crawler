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
from concurrent.futures._base import TimeoutError
from package.parser.baseParser import ParserBase, LoadPropertyPageException, \
    ReadPropertyNameException
import logging


class SumifuParser(ParserBase):
    BASE_URL='https://www.stepon.co.jp'

    def __init__(self, params):
        ""
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
        nextPageXpath = '//*[@id="searchCondition"]/div/div[2]/div[2]/div[1]/ul/li[last()]/a'
        # Since we use BeautifulSoup, xpath is not supported directly unless we use lxml with xpath or adapt.
        # But wait, original code used response.xpath? 
        # ParserBase might be using standard BeautifulSoup response. 
        # If the original code was working, response object must support xpath (e.g. lxml html element) OR this code was broken/legacy.
        # Assuming response is BeautifulSoup object as per type hint in other methods.
        # BS4 doesn't support xpath. Inspecting usage suggests this might have been from a scrapy migration or similar?
        # But let's check parseRegionPage logic, it calls _parsePageCore.
        # Let's assume response is BS4 and use select_one for 'next page'.
        
        # Selector for "Next" button in pagination
        # Usually li.next > a, or checking text "次へ"
        # The xpath implies: id="searchCondition" -> ... -> ul -> li:last-child -> a
        
        next_link = response.select_one('#searchCondition ul.pagination li:last-child a') # Hypothesis selector based on xpath
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
        ths = response.select("table.table-detail th")
        for th in ths:
            if target_th_text in th.get_text():
                td = th.find_next_sibling("td")
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

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        try:
            # New Name Selector
            name_tag = response.select_one("h1.heading-1")
            if not name_tag:
                 name_tag = response.select_one("h1") 
            if not name_tag:
                 # Fallback
                 name_block = response.find("div", id="bukkenNameBlockIcon")
                 if name_block:
                     # Safe traversal
                     h2s = name_block.find_all("h2")
                     if h2s:
                         spans = h2s[0].find_all("span")
                         if len(spans) > 1:
                             name_tag = spans[1]
            
            if name_tag:
                item.propertyName = name_tag.get_text(strip=True)
            
            if not item.propertyName:
                # Try generic h1 if specific classes failed or were empty
                name_tag = response.select_one("h1")
                if name_tag:
                    item.propertyName = name_tag.get_text(strip=True)

            if not item.propertyName:
                logging.warn("Could not find property name")
                raise ReadPropertyNameException()

        except Exception:
            logging.error(traceback.format_exc())
            raise ReadPropertyNameException()
        
        # Price
        price_td = self._getValueFromTable(response, "価格")
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
                    try:
                        oku = int(parts[0]) * 10000
                    except:
                        oku = 0
                if len(parts) > 1 and parts[1]:
                    # Extract digits only from parts[1]
                    digit_match = re.search(r'\d+', parts[1])
                    if digit_match:
                        man = int(digit_match.group())
                    else:
                        man = 0
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
                price_dl = response.select_one("dl#s_summaryPrice")
                if price_dl:
                    em = price_dl.select_one("dd p em")
                    if em:
                        item.priceStr = em.get_text(strip=True)
                        parent_p = em.find_parent("p")
                        priceUnit = ""
                        if parent_p:
                             priceWork = item.priceStr.replace(',', '')
                             oku = 0
                             man = 0
                             if u"億" in item.priceStr:
                                 priceArr = priceWork.split("億")
                                 oku = int(priceArr[0]) * 10000
                                 if len(priceArr) > 1 and len(priceArr[1]) != 0:
                                     man = int(priceArr[1])
                             else:
                                 man = int(priceWork)
                             item.price = oku + man
             except:
                 logging.warn("Could not find price")

        # Address
        address_td = self._getValueFromTable(response, "所在地")
        if address_td:
            item.address = address_td.get_text(strip=True)
        else:
            try:
                addr_elem = response.select_one("div#bukkenDetailBlock div.itemInfo dl.address dd")
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
            # New structure: multiple p tags or line breaks
            transport_lines = []
            p_tags = transport_td.find_all("p")
            if p_tags:
                transport_lines = [p.get_text(strip=True) for p in p_tags]
            else:
                # Fallback: split by <br> or newlines
                transport_text = transport_td.get_text(separator="\n", strip=True)
                transport_lines = [line.strip() for line in transport_text.split("\n") if line.strip()]
            
            # Parse each line
            for i, line in enumerate(transport_lines):
                if i >= 5: break
                # Example line: "JR山手線 五反田駅 徒歩10分"
                # or "東京メトロ南北線 白金高輪駅 徒歩5分 バス5分"
                
                # Simple parsing: split by spaces
                parts = line.split()
                if len(parts) >= 3:
                    railway = parts[0]
                    station = parts[1]
                    walk_info = " ".join(parts[2:])
                    
                    # Extract walk minutes
                    walk_match = re.search(r'徒歩(\d+)分', walk_info)
                    walk_min = int(walk_match.group(1)) if walk_match else 0
                    
                    # Extract bus info
                    bus_match = re.search(r'バス(\d+)分', walk_info)
                    bus_min = int(bus_match.group(1)) if bus_match else 0
                    
                    if i == 0:
                        item.transfer1 = line
                        item.railway1 = railway
                        item.station1 = station
                        item.railwayWalkMinute1Str = f"{walk_min}分" if walk_min > 0 else ""
                        item.railwayWalkMinute1 = walk_min
                        item.busWalkMinute1Str = f"{bus_min}分" if bus_min > 0 else ""
                        item.busWalkMinute1 = bus_min
                    elif i == 1:
                        item.transfer2 = line
                        item.railway2 = railway
                        item.station2 = station
                        item.railwayWalkMinute2Str = f"{walk_min}分" if walk_min > 0 else ""
                        item.railwayWalkMinute2 = walk_min
                        item.busWalkMinute2Str = f"{bus_min}分" if bus_min > 0 else ""
                        item.busWalkMinute2 = bus_min
                    elif i == 2:
                        item.transfer3 = line
                        item.railway3 = railway
                        item.station3 = station
                        item.railwayWalkMinute3Str = f"{walk_min}分" if walk_min > 0 else ""
                        item.railwayWalkMinute3 = walk_min
                        item.busWalkMinute3Str = f"{bus_min}分" if bus_min > 0 else ""
                        item.busWalkMinute3 = bus_min
                    elif i == 3:
                        item.transfer4 = line
                        item.railway4 = railway
                        item.station4 = station
                        item.railwayWalkMinute4Str = f"{walk_min}分" if walk_min > 0 else ""
                        item.railwayWalkMinute4 = walk_min
                        item.busWalkMinute4Str = f"{bus_min}分" if bus_min > 0 else ""
                        item.busWalkMinute4 = bus_min
                    elif i == 4:
                        item.transfer5 = line
                        item.railway5 = railway
                        item.station5 = station
                        item.railwayWalkMinute5Str = f"{walk_min}分" if walk_min > 0 else ""
                        item.railwayWalkMinute5 = walk_min
                        item.busWalkMinute5Str = f"{bus_min}分" if bus_min > 0 else ""
                        item.busWalkMinute5 = bus_min
        else:
            # Old selector fallback
            try:
                transport_elem = response.select_one("div#bukkenDetailBlock div.itemInfo dl.traffic dd")
                if transport_elem:
                    # Old parsing logic
                    pass
            except Exception:
                pass


        item.busUse1 = 0
        if(item.busWalkMinute1 > 0):
            item.busUse1 = 1
 
        # Parse Generic Table Rows (Hikiwatashi, Genkyo, etc)
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

        
class SumifuInvestmentParser(InvestmentParser):
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
        # Pattern: a.property-info-anchor or internal links in list
        links = response.select("a.property-info-anchor")
        if not links:
             # Fallback: find links containing detail_
             links = response.select("a[href*='/pro/detail_']")
             
        for link in links:
            href = link.get("href")
            if href.startswith("/"):
                href = "https://www.stepon.co.jp" + href
            yield href

    def parseNextPage(self, response: BeautifulSoup):
        # a.post_param:contains('次へ') -> Handled by finding text
        next_link = response.find("a", string=lambda t: t and "次へ" in t)
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
            name_tag = response.select_one("h1.heading-1")
            if not name_tag:
                 name_tag = response.select_one("h1") 
            if not name_tag:
                 # Fallback
                 name_block = response.find("div", id="bukkenNameBlockIcon")
                 if name_block:
                     # Safe traversal
                     h2s = name_block.find_all("h2")
                     if h2s:
                         spans = h2s[0].find_all("span")
                         if len(spans) > 1:
                             name_tag = spans[1]
            
            if name_tag:
                item.propertyName = name_tag.get_text(strip=True)
            
            if not item.propertyName:
                # Try generic h1 if specific classes failed or were empty
                name_tag = response.select_one("h1")
                if name_tag:
                    item.propertyName = name_tag.get_text(strip=True)

            if not item.propertyName:
                logging.warn("Could not find property name")
                raise ReadPropertyNameException()

        except Exception:
            logging.error(traceback.format_exc())
            raise ReadPropertyNameException()
        
        # Price
        price_td = self._getValueFromTable(response, "価格")
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
             # Old selector fallback
             try:
                price_dl = response.select_one("dl#s_summaryPrice")
                if price_dl:
                    em = price_dl.select_one("dd p em")
                    if em:
                        item.priceStr = em.get_text(strip=True)
                        parent_p = em.find_parent("p")
                        priceUnit = ""
                        if parent_p:
                             # Extract text node after em?
                             # Assuming straightforward text logic:
                             priceWork = item.priceStr.replace(',', '')
                             oku = 0
                             man = 0
                             if u"億" in item.priceStr:
                                 priceArr = priceWork.split("億")
                                 oku = int(priceArr[0]) * 10000
                                 if len(priceArr) > 1 and len(priceArr[1]) != 0:
                                     man = int(priceArr[1])
                             else:
                                 man = int(priceWork)
                             item.price = oku + man
             except:
                 logging.warn("Could not find price")

        # Address
        address_td = self._getValueFromTable(response, "所在地")
        if address_td:
            item.address = address_td.get_text(strip=True)
        else:
            try:
                addr_elem = response.select_one("div#bukkenDetailBlock div.itemInfo dl.address dd")
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

    def getRegionXpath(self):
        return u'//a[contains(@href,"/mansion/area_")]/@href'

    def getAreaXpath(self):
        return u'//a[contains(@href,"/mansion/area_") and contains(@href,"/list_") and contains(text(),"（")]/@href'

    def getPropertyListXpath(self):
        return u'//*[@id="searchResultBlock"]/div/div/div/div[1]/*//label/h2/a/@href'

    def createEntity(self):
        return  SumifuMansion()
            
    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item:SumifuMansion=super()._parsePropertyDetailPage(item, response)

        # Madori
        madori_td = self._getValueFromTable(response, "間取り")
        if madori_td:
             item.madori = madori_td.get_text(strip=True)
        else:
             # Fallback
             try:
                elem = response.select_one("dl#s_summaryMadori dd em")
                if elem:
                     item.madori = elem.get_text(strip=True)
             except: pass

        # Senyu Menseki
        area_td = self._getValueFromTable(response, "専有面積")
        if area_td:
             item.senyuMensekiStr = area_td.get_text(strip=True)
        else:
             # Fallback
             try:
                elem = response.select_one("dl#s_summarySenyuMenseki dd")
                if elem:
                     item.senyuMensekiStr = elem.get_text(strip=True)
             except: pass

        if hasattr(item, "senyuMensekiStr") and item.senyuMensekiStr:
            # Extract numeric part from strings like "81.65m2(壁芯)" or "81.65平米"
            digit_match = re.search(r'[\d.]+', item.senyuMensekiStr)
            if digit_match:
                try:
                    item.senyuMenseki = Decimal(digit_match.group())
                except:
                    item.senyuMenseki = 0
            else:
                item.senyuMenseki = 0

        # Floor / Structure
        # The table usually has "階建 / 階" or similar.
        # Let's search for "階" in header
        floor_td = self._getValueFromTable(response, "階建") # e.g. "地上10階地下1階建 3階部分"
        if not floor_td:
             floor_td = self._getValueFromTable(response, "階") # Sometimes just "階"

        if floor_td:
             item.floorType = floor_td.get_text(strip=True)
        else:
             try:
                elem = response.select_one("dl#s_summaryFloor dd")
                if elem:
                    item.floorType = elem.get_text(strip=True)
             except: 
                item.floorType = ""

        if item.floorType:
            try:
                # Logic to parse "地上X階... Y階部分"
                # Existing logic:
                # item.floorType_kai = int(item.floorType.split(u"部分")[0].split(u"階")[0].replace(u"地下", "-"))
                # item.floorType_chijo = int(item.floorType.split(u"地上")[1].split(u"階")[0])
                
                # New strings might look like: "地上14階建 / 6階" or similar.
                # Let's try to adapt specific regex or keep existing logic if string format matches.
                # Assuming format is relatively consistent or we can make it robust.
                
                # Check for "階建" and "/" separator
                # Example: "RC14階建 / 6階"
                # Or: "地上14階 地下1階建 / 3階"
                
                # Try to parse "Floor" (part) first
                part_match = re.search(r'(\d+)階部分', item.floorType)
                if not part_match:
                     # Maybe it says " / 5階"
                     part_match = re.search(r'/\s*(\d+)階', item.floorType)

                if part_match:
                    item.floorType_kai = int(part_match.group(1))
                    if "地下" in item.floorType and "地下" in item.floorType.split(part_match.group(0))[0]: 
                         item.floorType_kai = -item.floorType_kai # Simplified heuristic
                
                # Total floors
                total_match = re.search(r'地上(\d+)階', item.floorType)
                if total_match:
                    item.floorType_chijo = int(total_match.group(1))
                else: 
                     # Try "14階建"
                     total_match = re.search(r'(\d+)階建', item.floorType)
                     if total_match:
                         item.floorType_chijo = int(total_match.group(1))


                # Basement
                chika_match = re.search(r'地下(\d+)階', item.floorType)
                if chika_match:
                    item.floorType_chika = int(chika_match.group(1))
                else:
                    item.floorType_chika = 0

            except Exception:
                logging.warn(f"Value Error item.floorType is {item.floorType}")
        
        # Chikunengetsu
        age_td = self._getValueFromTable(response, "築年月")
        if age_td:
             item.chikunengetsuStr = age_td.get_text(strip=True)
        else:
             try:
                  elem = response.select_one("dl#s_summaryChikunengetsu dd")
                  if elem:
                      item.chikunengetsuStr = elem.get_text(strip=True)
             except: pass
        if hasattr(item, 'chikunengetsuStr'):
            self._parseChikunengetsuText(item)

        # Iterate table for other fields
        detail_rows = response.select("table.table-detail tr")
        for tr in detail_rows:
            ths = tr.select("th")
            tds = tr.select("td")
            if not ths or not tds: continue
            
            thTitle = ths[0].get_text(strip=True)
            tdValue = tds[0].get_text(strip=True)

            if "バルコニー" in thTitle and "面積" in thTitle:
                item.barukoniMensekiStr = tdValue
            if thTitle == "採光方向":
                item.saikouKadobeya = tdValue
                temp = item.saikouKadobeya.split(u"／")
                if len(temp) == 1:
                    item.saikou = item.saikouKadobeya
                    item.kadobeya = ""
                else:
                    item.saikou = temp[0]
                    item.kadobeya = temp[1]
            if thTitle == "総戸数":
                item.soukosuStr = tdValue
                try:
                    item.soukosu = int(re.sub(r'\D', '', item.soukosuStr))
                except: item.soukosu = 0
            if "管理方式" in thTitle or "管理会社" in thTitle:
                item.kanriKeitaiKaisya = tdValue
                temp = item.kanriKeitaiKaisya.split(u"／")
                if len(temp) == 1:
                    item.kanriKeitai = temp[0]
                    item.kanriKaisya = ""
                else:
                    item.kanriKeitai = temp[0]
                    item.kanriKaisya = temp[1]
            if "管理費" in thTitle and "月額" in thTitle:
                item.kanrihiStr = tdValue
                if "-" in item.kanrihiStr:
                     item.kanrihi = 0
                else:
                     try:
                        item.kanrihi = int(re.sub(r'\D', '', item.kanrihiStr))
                     except: item.kanrihi = 0
            if "修繕積立金" in thTitle and "月額" in thTitle:
                item.syuzenTsumitateStr = tdValue
                if "-" in item.syuzenTsumitateStr:
                    item.syuzenTsumitate = 0
                else:
                    try:
                        item.syuzenTsumitate = int(re.sub(r'\D', '', item.syuzenTsumitateStr))
                    except: item.syuzenTsumitate = 0
            
            # Others
            if "引渡時期" in thTitle:
                    item.hikiwatashi = tdValue
            if "現況" in thTitle:
                item.genkyo = tdValue
            if "駐車場" in thTitle:
                item.tyusyajo = tdValue
            if "土地権利" in thTitle:
                item.tochikenri = tdValue
            if "施工会社" in thTitle:
                item.sekouKaisya = tdValue
            if "取引態様" in thTitle:
                item.torihiki = tdValue
            if "備考" in thTitle:
                 item.biko = "" # Already handled in base? Or re-read here.


        # 不要項目
        item.kaisu = ""
        item.kouzou = ""
        item.address1 = ""
        item.address2 = ""
        item.address3 = ""
        item.addressKyoto = ""
        item.sonotaHiyouStr = ""
        item.bunjoKaisya = ""
        
        if(item.floorType.count(u"・ＲＣ造") > 0):
            item.floorType_kouzou = "ＲＣ造"
        if(item.floorType.count(u"・ＳＲＣ造") > 0):
            item.floorType_kouzou = "ＳＲＣ造"
        if(item.floorType.count(u"・Ｓ造") > 0):
            item.floorType_kouzou = "Ｓ造"
        if(item.floorType.count(u"・木造") > 0):
            item.floorType_kouzou = "木造"
        if(item.floorType.count(u"・その他") > 0):
            item.floorType_kouzou = "その他"

        item.kyutaishin = 0
        item.kyutaishin = 0
        if(item.chikunengetsu and item.chikunengetsu < datetime.date(1982, 1, 1)):
            item.kyutaishin = 1
            
        item.barukoniMenseki = 0
        if item.barukoniMensekiStr != "--":
            barukoniMenseki = item.barukoniMensekiStr.split(u"／")[0].split(u"専用庭面積")[0].split(u"ルーフバルコニー面積")[0].split(u"m")[0].strip()
            if(len(barukoniMenseki) > 0):
                item.barukoniMenseki = Decimal(barukoniMenseki)

        item.senyouNiwaMenseki = 0
        senyouNiwaList = item.barukoniMensekiStr.split(u"専用庭面積")
        if(len(senyouNiwaList) > 1):
            item.senyouNiwaMenseki = Decimal(senyouNiwaList[1].split(u"m")[0])
        
        item.roofBarukoniMenseki = 0
        roofList = item.barukoniMensekiStr.split(u"ルーフバルコニー面積")
        if(len(roofList) > 1):
            item.roofBarukoniMenseki = Decimal(roofList[1].split(u"m")[0])

        if item.senyuMenseki and item.senyuMenseki > 0:
             item.kanrihi_p_heibei = item.kanrihi / item.senyuMenseki
             item.syuzenTsumitate_p_heibei = item.syuzenTsumitate / item.senyuMenseki
        else:
             item.kanrihi_p_heibei = 0
             item.syuzenTsumitate_p_heibei = 0

        return item

class SumifuTochiParser(SumifuParser):
    
    def getRegionXpath(self):
        return u'//a[contains(@href,"/tochi/area_")]/@href'

    def getAreaXpath(self):
        return u'//a[contains(@href,"/tochi/area_") and contains(@href,"/list_") and contains(text(),"（")]/@href'

    def getPropertyListXpath(self):
        return u'//*[@id="searchResultBlock"]/div/div/div/div[1]/*//label/h2/a/@href'

    def createEntity(self):
        return  SumifuTochi()

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item:SumifuTochi=super()._parsePropertyDetailPage(item, response)
        
        # Tochi Menseki
        tochi_td = self._getValueFromTable(response, "土地面積")
        if tochi_td:
            item.tochiMensekiStr = tochi_td.get_text(strip=True)
        else:
            try:
                elem = response.select_one("dl#s_summaryTochiMenseki dd")
                if elem:
                    item.tochiMensekiStr = elem.get_text(strip=True)
            except: pass
            
        if hasattr(item, "tochiMensekiStr") and item.tochiMensekiStr:
             try:
                # "100.00m2" -> 100.00
                item.tochiMenseki = Decimal(item.tochiMensekiStr.split("m")[0])
             except:
                item.tochiMenseki = 0

        # Kenpei / Youseki
        # Try finding combined first?
        # Often separate in table.
        kenpei_td = self._getValueFromTable(response, "建ぺい率")
        youseki_td = self._getValueFromTable(response, "容積率")
        
        kenpei_str = ""
        youseki_str = ""
        
        if kenpei_td: kenpei_str = kenpei_td.get_text(strip=True)
        if youseki_td: youseki_str = youseki_td.get_text(strip=True)
        
        if kenpei_str and youseki_str:
             item.kenpeiYousekiStr = f"{kenpei_str}／{youseki_str}"
             self._parseKenpeiYousekiText(item)
        else:
             # Fallback to old ID or check if combined
             try:
                 item.kenpeiYousekiStr = response.find_all("dl", id="s_coverageLandVolume")[0].find_all("dd")[0].contents[0]
                 self._parseKenpeiYousekiText(item)
             except: pass

        # Iterate table for other fields
        detail_rows = response.select("table.table-detail tr")
        for tr in detail_rows:
            ths = tr.select("th")
            tds = tr.select("td")
            if not ths or not tds: continue
            
            thTitle = ths[0].get_text(strip=True)
            tdValue = tds[0].get_text(strip=True)

            if "地目" in thTitle or "地勢" in thTitle:
                 self._getChimokuChiseiText(item, tdValue)
            elif "接道状況" in thTitle:
                 self._getSetudouText(item, tdValue)
            elif "地域地区" in thTitle:
                 self._getChiikiChikuText(item, tdValue)
            elif "建築条件" in thTitle:
                 item.kenchikuJoken = tdValue.strip()
            elif "国土法" in thTitle:
                 item.kokudoHou = tdValue
            
        return item
    
class SumifuKodateParser(SumifuParser):
    
    def getRegionXpath(self):
        return u'//a[contains(@href,"/kodate/area_")]/@href'

    def getAreaXpath(self):
        return u'//a[contains(@href,"/kodate/area_") and contains(@href,"/list_") and contains(text(),"（")]/@href'

    def getPropertyListXpath(self):
        return u'//*[@id="searchResultBlock"]/div/div/div/div[1]/*//label/h2/a/@href'

    def createEntity(self):
        return  SumifuKodate()


    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item:SumifuKodate=super()._parsePropertyDetailPage(item, response)
        
        # Tochi Menseki
        tochi_td = self._getValueFromTable(response, "土地面積")
        if tochi_td:
             item.tochiMensekiStr = tochi_td.get_text(strip=True)
             try: item.tochiMenseki = item.tochiMensekiStr.split("m")[0]
             except: item.tochiMenseki = 0
        else:
             try:
                 elem = response.select_one("dl#s_summaryTochiMenseki dd")
                 if elem:
                     item.tochiMensekiStr = elem.get_text(strip=True)
                     item.tochiMenseki = item.tochiMensekiStr.split("m")[0]
             except: pass

        # Tatemono Menseki
        tatemono_td = self._getValueFromTable(response, "建物面積")
        if tatemono_td:
             item.tatemonoMensekiStr = tatemono_td.get_text(strip=True)
             try: item.tatemonoMenseki = item.tatemonoMensekiStr.split("m")[0]
             except: item.tatemonoMenseki = 0
        else:
             try:
                 elem = response.select_one("dl#s_summaryTatemonoMenseki dd")
                 if elem:
                     item.tatemonoMensekiStr = elem.get_text(strip=True)
                     item.tatemonoMenseki = item.tatemonoMensekiStr.split("m")[0]
             except: pass

        # Madori
        madori_td = self._getValueFromTable(response, "間取り")
        if madori_td:
             item.madori = madori_td.get_text(strip=True)
        else:
             try:
                elem = response.select_one("dl#s_summaryMadori dd em")
                if elem:
                    item.madori = elem.get_text(strip=True)
             except: pass

        # Chikunengetsu
        age_td = self._getValueFromTable(response, "築年月")
        if age_td:
             item.chikunengetsuStr = age_td.get_text(strip=True)
             self._parseChikunengetsuText(item)
        else:
             try:
                 elem = response.select_one("dl#s_summaryChikunengetsu dd")
                 if elem:
                     item.chikunengetsuStr = elem.get_text(strip=True)
                     self._parseChikunengetsuText(item)
             except: pass


        # Kenpei/Youseki
        kenpei_td = self._getValueFromTable(response, "建ぺい率")
        youseki_td = self._getValueFromTable(response, "容積率")
        if kenpei_td and youseki_td:
             item.kenpeiYousekiStr = f"{kenpei_td.get_text(strip=True)}／{youseki_td.get_text(strip=True)}"
             self._parseKenpeiYousekiText(item)
        else:
             try:
                 item.kenpeiYousekiStr = response.find_all("dl", id="s_coverageLandVolume")[0].find_all("dd")[0].contents[0]
                 self._parseKenpeiYousekiText(item)
             except: pass
        
        
        # Iterate table for other fields
        detail_rows = response.select("table.table-detail tr")
        for tr in detail_rows:
            ths = tr.select("th")
            tds = tr.select("td")
            if not ths or not tds: continue
            
            thTitle = ths[0].get_text(strip=True)
            tdValue = tds[0].get_text(strip=True)
            
            if "階数" in thTitle or "構造" in thTitle or thTitle == "階建":
                 item.kaisuKouzou = tdValue
                 # Try to split "木造2階建" -> kaisu=2階建, kouzou=木造
                 # Heuristic split? Or keep raw?
                 # Existing logic expected "階数・構造" header and value split by "・"
                 # e.g. "2階建・木造"
                 if "・" in item.kaisuKouzou:
                     parts = item.kaisuKouzou.split("・")
                     item.kaisu = parts[0]
                     item.kouzou = parts[1]
                 else:
                     # Just assign raw to kaisu for now if not split
                     item.kaisu = item.kaisuKouzou
                     item.kouzou = ""

            elif "地目" in thTitle or "地勢" in thTitle:
                 self._getChimokuChiseiText(item, tdValue)
            elif "接道状況" in thTitle:
                 self._getSetudouText(item, tdValue)
            elif "建ぺい率" in thTitle: # Handled above but redundancy ok?
                 item.kenpei = tdValue.replace("%","").split(" ")[0]
            elif "容積率" in thTitle:
                 item.youseki = tdValue.replace("%","").split(" ")[0]
            elif "地域地区" in thTitle:
                 self._getChiikiChikuText(item, tdValue)
            elif "建築条件" in thTitle:
                 item.kenchikuJoken = tdValue.strip()
            elif "国土法" in thTitle:
                 item.kokudoHou = tdValue

        return item
    

from bs4 import BeautifulSoup
from abc import abstractmethod
from django.db import models
import logging
import re
from package.parser.investmentParser import InvestmentParser
from package.models.nomura import NomuraMansion, NomuraKodate, NomuraTochi, NomuraInvestmentKodate, NomuraInvestmentApartment
from package.utils import converter
from package.utils.selector_loader import SelectorLoader
from package.parser.baseParser import ReadPropertyNameException
import traceback
from decimal import Decimal

class NomuraParser(InvestmentParser):
    def __init__(self, token=""):
        super().__init__()
        self.selectors = SelectorLoader.load('nomura', self.property_type)

    def _get_specs(self, response: BeautifulSoup):
        # We use _scrape_specs for actual implementation but override _get_specs for compatibility with InvestmentParser
        return self._scrape_specs(response)

    def _scrape_specs(self, response: BeautifulSoup) -> dict:
        specs = {}
        # 1. Handle .item_status (Traditional/Mansion structure)
        item_statuses = response.select(".item_status")
        for status in item_statuses:
            title_el = status.select_one(".item_status_title")
            content_el = status.select_one(".item_status_content")
            if title_el and content_el:
                key = title_el.get_text(strip=True).replace(" ", "").replace("\u3000", "").rstrip("：")
                specs[key] = content_el.get_text(strip=True).replace("\xa0", " ")
                
        # 2. Handle dl/dt/dd (Detail tables)
        for dl in response.select("dl"):
            dts = dl.select("dt")
            dds = dl.select("dd")
            for dt, dd in zip(dts, dds):
                key = dt.get_text(strip=True).replace(" ", "").replace("\u3000", "").rstrip("：")
                val = dd.get_text(strip=True).replace("\xa0", " ")
                if key and (key not in specs or len(val) > len(specs.get(key, ""))):
                    specs[key] = val

        # 3. Handle table/tr/th/td
        # Helper to parse a single table
        def parse_table_element(table, force=False):
            for tr in table.select("tr"):
                ths = tr.select("th")
                tds = tr.select("td")
                for th, td in zip(ths, tds):
                    # Copy th to avoid breaking original soup if reused, but here it's fine
                    th_temp = BeautifulSoup(str(th), "html.parser").find("th")
                    help_el = th_temp.select_one(".item_help")
                    if help_el: help_el.decompose()
                    key = th_temp.get_text(strip=True).replace(" ", "").replace("\u3000", "").rstrip("：")
                    val = td.get_text(strip=True).replace("\xa0", " ")
                    if key:
                        # Special check for kouzou - ignore hashtags
                        if key == "構造" and val.startswith("#"):
                            continue
                            
                        # If force is True (c_table_spec), overwrite.
                        # If force is False, use length heuristic.
                        if force:
                            specs[key] = val
                        elif key not in specs or len(val) > len(specs.get(key, "")):
                            specs[key] = val

        # First pass: All tables (generic)
        for table in response.select("table"):
            parse_table_element(table, force=False)
            
        # Second pass: c_table_spec (canonical details) - Force overwrite
        # This ensures we get specific technical details even if shorter than hashtags
        for table in response.select("table.c_table_spec"):
            parse_table_element(table, force=True)
            
        return specs

    def _parsePropertyName(self, response):
        selector = self.selectors.get('property_name', "h1, .item_name")
        el = response.select_one(selector)
        if not el: raise ReadPropertyNameException("Property name not found")
        return el.get_text(strip=True)

    def _parsePriceStr(self, response):
        selector = self.selectors.get('price', ".item_price")
        el = response.select_one(selector)
        if el: return el.get_text(strip=True)
        
        fallback = self.selectors.get('price_fallback', ".num")
        el = response.select_one(fallback)
        return el.get_text(strip=True) if el else ""

    def _parsePrice(self, response):
        return converter.parse_price(self._parsePriceStr(response))

    def _parseAddress(self, response):
        specs = self._get_specs(response)
        addr = specs.get("所在地", "").replace("周辺地図を見る", "").strip()
        return addr

    def _parseAddress1(self, response):
        address = self._parseAddress(response)
        match = re.match(r'^([^都道府県]+[都道府県])([^市市区町村]+[市区町村])(.*)$', address)
        if match: return match.group(1)
        return ""

    def _parseAddress2(self, response):
        address = self._parseAddress(response)
        match = re.match(r'^([^都道府県]+[都道府県])([^市市区町村]+[市区町村])(.*)$', address)
        if match: return match.group(2)
        return ""

    def _parseAddress3(self, response):
        address = self._parseAddress(response)
        match = re.match(r'^([^都道府県]+[都道府県])([^市市区町村]+[市区町村])(.*)$', address)
        if match: return match.group(3).strip()
        return ""

    def _parseTrafficFull(self, response):
        specs = self._get_specs(response)
        return specs.get("交通", "")

    def _parseTrafficLines(self, response):
        traffic_full = self._parseTrafficFull(response)
        if not traffic_full: return []
        # Nomura often uses <br> which becomes \n in get_text()
        lines = [line.strip() for line in traffic_full.split("\n") if line.strip()]
        return lines

    def _parseRailwayCount(self, response):
        return len(self._parseTrafficLines(response))

    def _getTrafficField(self, response, index, field_to_get, default_val):
        lines = self._parseTrafficLines(response)
        if index > len(lines): return default_val
        
        line = lines[index-1]
        
        if field_to_get == 'transfer':
            return line
        elif field_to_get == 'railway':
            m = re.search(r'^([^「（]+)', line)
            return m.group(1).strip() if m else ""
        elif field_to_get == 'station':
            m = re.search(r'「([^」]+)」', line)
            return m.group(1).strip() if m else ""
        elif field_to_get.startswith('railwayWalkMinute'):
            # Only if it's not a bus line (or if it's the walk after bus)
            # Nomura: "駅 徒歩10分" OR "駅 バス21分 (バス停 ...) 徒歩5分"
            # If there's a bus, the walk minute is the LAST one.
            m_walks = re.findall(r'徒歩\s*(\d+)\s*分', line)
            val = m_walks[-1] if m_walks else default_val
            return int(val) if field_to_get == 'railwayWalkMinute' and val != default_val else val
        elif field_to_get.startswith('busWalkMinute'):
            m_bus = re.search(r'バス\s*(\d+)\s*分', line)
            val = m_bus.group(1) if m_bus else default_val
            return int(val) if field_to_get == 'busWalkMinute' and val != default_val else val
        elif field_to_get == 'busStation':
             m_bus_station = re.search(r'\((?:バス停|停)\s*([^)]+)\)', line)
             return m_bus_station.group(1).strip() if m_bus_station else default_val
        elif field_to_get == 'busUse':
             return 1 if "バス" in line else 0
            
        return default_val

    def _parseTransfer1(self, response): return self._getTrafficField(response, 1, 'transfer', "")
    def _parseRailway1(self, response): return self._getTrafficField(response, 1, 'railway', "")
    def _parseStation1(self, response): return self._getTrafficField(response, 1, 'station', "")
    def _parseRailwayWalkMinute1Str(self, response): return self._getTrafficField(response, 1, 'railwayWalkMinute1Str', "")
    def _parseRailwayWalkMinute1(self, response): return self._getTrafficField(response, 1, 'railwayWalkMinute', 0)
    def _parseBusStation1(self, response): return self._getTrafficField(response, 1, 'busStation', "")
    def _parseBusWalkMinute1Str(self, response): return self._getTrafficField(response, 1, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute1(self, response): return self._getTrafficField(response, 1, 'busWalkMinute', 0)
    def _parseBusUse1(self, response): return self._getTrafficField(response, 1, 'busUse', 0)

    def _parseTransfer2(self, response): return self._getTrafficField(response, 2, 'transfer', "")
    def _parseRailway2(self, response): return self._getTrafficField(response, 2, 'railway', "")
    def _parseStation2(self, response): return self._getTrafficField(response, 2, 'station', "")
    def _parseRailwayWalkMinute2Str(self, response): return self._getTrafficField(response, 2, 'railwayWalkMinute2Str', "")
    def _parseRailwayWalkMinute2(self, response): return self._getTrafficField(response, 2, 'railwayWalkMinute', 0)
    def _parseBusStation2(self, response): return self._getTrafficField(response, 2, 'busStation', "")
    def _parseBusWalkMinute2Str(self, response): return self._getTrafficField(response, 2, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute2(self, response): return self._getTrafficField(response, 2, 'busWalkMinute', 0)
    def _parseBusUse2(self, response): return self._getTrafficField(response, 2, 'busUse', 0)

    def _parseTransfer3(self, response): return self._getTrafficField(response, 3, 'transfer', "")
    def _parseRailway3(self, response): return self._getTrafficField(response, 3, 'railway', "")
    def _parseStation3(self, response): return self._getTrafficField(response, 3, 'station', "")
    def _parseRailwayWalkMinute3Str(self, response): return self._getTrafficField(response, 3, 'railwayWalkMinute3Str', "")
    def _parseRailwayWalkMinute3(self, response): return self._getTrafficField(response, 3, 'railwayWalkMinute', 0)
    def _parseBusStation3(self, response): return self._getTrafficField(response, 3, 'busStation', "")
    def _parseBusWalkMinute3Str(self, response): return self._getTrafficField(response, 3, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute3(self, response): return self._getTrafficField(response, 3, 'busWalkMinute', 0)
    def _parseBusUse3(self, response): return self._getTrafficField(response, 3, 'busUse', 0)

    def _parseTransfer4(self, response): return self._getTrafficField(response, 4, 'transfer', "")
    def _parseRailway4(self, response): return self._getTrafficField(response, 4, 'railway', "")
    def _parseStation4(self, response): return self._getTrafficField(response, 4, 'station', "")
    def _parseRailwayWalkMinute4Str(self, response): return self._getTrafficField(response, 4, 'railwayWalkMinute4Str', "")
    def _parseRailwayWalkMinute4(self, response): return self._getTrafficField(response, 4, 'railwayWalkMinute', 0)
    def _parseBusStation4(self, response): return self._getTrafficField(response, 4, 'busStation', "")
    def _parseBusWalkMinute4Str(self, response): return self._getTrafficField(response, 4, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute4(self, response): return self._getTrafficField(response, 4, 'busWalkMinute', 0)
    def _parseBusUse4(self, response): return self._getTrafficField(response, 4, 'busUse', 0)

    def _parseTransfer5(self, response): return self._getTrafficField(response, 5, 'transfer', "")
    def _parseRailway5(self, response): return self._getTrafficField(response, 5, 'railway', "")
    def _parseStation5(self, response): return self._getTrafficField(response, 5, 'station', "")
    def _parseRailwayWalkMinute5Str(self, response): return self._getTrafficField(response, 5, 'railwayWalkMinute5Str', "")
    def _parseRailwayWalkMinute5(self, response): return self._getTrafficField(response, 5, 'railwayWalkMinute', 0)
    def _parseBusStation5(self, response): return self._getTrafficField(response, 5, 'busStation', "")
    def _parseBusWalkMinute5Str(self, response): return self._getTrafficField(response, 5, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute5(self, response): return self._getTrafficField(response, 5, 'busWalkMinute', 0)
    def _parseBusUse5(self, response): return self._getTrafficField(response, 5, 'busUse', 0)

    async def parsePropertyListPage(self, response: BeautifulSoup):
        links_selector = self.selectors.get('property_links', "a[href*='/pro/bukken_local_id/']")
        if hasattr(response, 'select'):
            elements = response.select(links_selector)
        else:
            xpath = self.selectors.get('property_links_xpath', "//a[contains(@href, '/pro/bukken_local_id/')] | //a[contains(@href, '/mansion/') and contains(@href, '/id/')]")
            elements = response.xpath(xpath)

        for link in elements:
            href = link.get("href")
            if href and not href.startswith("#") and not href.startswith("javascript:") and "/library/" not in href:
                href = href.split("?")[0]
                if href.startswith("/"): href = "https://www.nomu.com" + href
                yield href

    async def parseNextPage(self, response: BeautifulSoup):
        next_selector = self.selectors.get('next_page', "a.next")
        if hasattr(response, 'select'):
            next_link = response.select_one(next_selector)
        else:
            xpath = self.selectors.get('next_page_xpath', "//a[contains(@class, 'next')]")
            links = response.xpath(xpath)
            next_link = links[0] if links else None
        return next_link.get("href") if next_link else ""

    async def parseAreaPage(self, response: BeautifulSoup):
        if hasattr(response, 'select'):
            selector = self.selectors.get('area_links', ".c_selection_list a")
            elements = response.select(selector)
        else:
            xpath = self.selectors.get('area_links_xpath', "//div[contains(@class, 'c_selection_list')]//a")
            elements = response.xpath(xpath)
            
        for link in elements:
            href = link.get("href")
            if href and not href.startswith("#") and not href.startswith("javascript:"):
                # Area/Region pages usually don't have query params but safe to strip
                href = href.split("?")[0]
                if href.startswith("/"): href = "https://www.nomu.com" + href
                yield href

    async def parseRegionPage(self, response: BeautifulSoup):
        if hasattr(response, 'select'):
            selector = self.selectors.get('region_links', ".c_selection_list a")
            elements = response.select(selector)
        else:
            xpath = self.selectors.get('region_links_xpath', "//div[contains(@class, 'c_selection_list')]//a")
            elements = response.xpath(xpath)

        for link in elements:
            href = link.get("href")
            if href and not href.startswith("#") and not href.startswith("javascript:"):
                 # Region pages usually don't have query params but safe to strip
                href = href.split("?")[0]
                if href.startswith("/"): href = "https://www.nomu.com" + href
                yield href


    def _parseMadori(self, response):
        specs = self._get_specs(response)
        return specs.get("間取り", "")

    def _parseSenyuMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("専有面積", "")

    def _parseSenyuMenseki(self, response):
        value = self._parseSenyuMensekiStr(response)
        return converter.parse_menseki(value) or Decimal(0)

    def _parseBalconyMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("バルコニー面積", "")

    def _parseBalconyMenseki(self, response):
        value = self._parseBalconyMensekiStr(response)
        return converter.parse_menseki(value) if value else None

    def _parseSaikou(self, response):
        specs = self._get_specs(response)
        return specs.get("向き", "")

    def _parseOtherArea(self, response):
        specs = self._get_specs(response)
        return specs.get("その他面積", "")

    def _parseKouzou(self, response):
        specs = self._get_specs(response)
        return specs.get("構造", "")

    def _parseKaisu(self, response):
        specs = self._get_specs(response)
        return specs.get("所在階", "")

    def _parseKaisuStr(self, response):
        specs = self._get_specs(response)
        val = specs.get("階数", specs.get("階建", ""))
        if val: return val
        # Fallback: check kouzou
        kouzou = specs.get("構造", "")
        if kouzou:
             match = re.search(r'(\d+階建)', kouzou)
             if match:
                 return match.group(0)
        return ""

    def _parseChikunengetsuStr(self, response):
        specs = self._get_specs(response)
        return specs.get("築年月", "")

    def _parseChikunengetsu(self, response):
        value = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(value)

    def _parseSoukosuStr(self, response):
        specs = self._get_specs(response)
        return specs.get("総戸数", specs.get("住戸数", ""))

    def _parseSoukosu(self, response):
        value = self._parseSoukosuStr(response)
        return converter.parse_numeric(value)

    def _parseTochikenri(self, response):
        specs = self._get_specs(response)
        return specs.get("土地権利", "")

    def _parseYoutoChiiki(self, response):
        specs = self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseKanriKaisya(self, response):
        specs = self._get_specs(response)
        return specs.get("管理会社", "")

    def _parseKanriKeitai(self, response):
        specs = self._get_specs(response)
        return specs.get("管理形態", "")

    def _parseManager(self, response):
        specs = self._get_specs(response)
        return specs.get("管理員", "")

    def _parseKanrihiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("管理費", "")

    def _parseSyuzenTsumitateStr(self, response):
        specs = self._get_specs(response)
        return specs.get("修繕積立金", "")

    def _parseOtherFees(self, response):
        specs = self._get_specs(response)
        return specs.get("その他費用", "")

    def _parseTyusyajo(self, response):
        specs = self._get_specs(response)
        return specs.get("駐車場", "")
    
    def _parseCurrentStatus(self, response):
        specs = self._get_specs(response)
        return specs.get("現況", "") or "不明"

    def _parseHikiwatashi(self, response):
        specs = self._get_specs(response)
        return specs.get("引渡", specs.get("引渡時期", "")) or "相談"

    def _parseTorihiki(self, response):
        specs = self._get_specs(response)
        return specs.get("取引態様", "") or "仲介"

    def _parseBiko(self, response):
        specs = self._get_specs(response)
        return specs.get("備考", "")

    def _parseUpdateDate(self, response):
        specs = self._get_specs(response)
        return specs.get("更新日", specs.get("情報更新日", ""))

    def _parseNextUpdateDate(self, response):
        specs = self._get_specs(response)
        return specs.get("次回更新予定日", "")

class NomuraMansionParser(NomuraParser):
    property_type = 'mansion'
    def createEntity(self): return NomuraMansion()
    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)
        item.address1 = self._parseAddress1(response)
        item.address2 = self._parseAddress2(response)
        item.address3 = self._parseAddress3(response)
        item.traffic = self._parseTrafficFull(response)
        
        item.railwayCount = self._parseRailwayCount(response)
        item.railway1 = self._parseRailway1(response)
        item.station1 = self._parseStation1(response)
        item.railwayWalkMinute1Str = self._parseRailwayWalkMinute1Str(response)
        item.railwayWalkMinute1 = self._parseRailwayWalkMinute1(response)
        item.busStation1 = self._parseBusStation1(response)
        item.busWalkMinute1Str = self._parseBusWalkMinute1Str(response)
        item.busWalkMinute1 = self._parseBusWalkMinute1(response)
        item.busUse1 = self._parseBusUse1(response)
        
        item.railway2 = self._parseRailway2(response)
        item.station2 = self._parseStation2(response)
        item.railwayWalkMinute2Str = self._parseRailwayWalkMinute2Str(response)
        item.railwayWalkMinute2 = self._parseRailwayWalkMinute2(response)
        item.busStation2 = self._parseBusStation2(response)
        item.busWalkMinute2Str = self._parseBusWalkMinute2Str(response)
        item.busWalkMinute2 = self._parseBusWalkMinute2(response)
        item.busUse2 = self._parseBusUse2(response)
        
        item.railway3 = self._parseRailway3(response)
        item.station3 = self._parseStation3(response)
        item.railwayWalkMinute3Str = self._parseRailwayWalkMinute3Str(response)
        item.railwayWalkMinute3 = self._parseRailwayWalkMinute3(response)
        item.busStation3 = self._parseBusStation3(response)
        item.busWalkMinute3Str = self._parseBusWalkMinute3Str(response)
        item.busWalkMinute3 = self._parseBusWalkMinute3(response)
        item.busUse3 = self._parseBusUse3(response)

        item.madori = self._parseMadori(response)
        item.senyuMensekiStr = self._parseSenyuMensekiStr(response)
        item.senyuMenseki = self._parseSenyuMenseki(response)
        item.balconyMensekiStr = self._parseBalconyMensekiStr(response)
        item.balconyMenseki = self._parseBalconyMenseki(response)
        item.saikou = self._parseSaikou(response)
        item.otherArea = self._parseOtherArea(response)
        item.kouzou = self._parseKouzou(response)
        item.kaisu = self._parseKaisu(response)
        item.kaisuStr = self._parseKaisuStr(response)
        
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        item.soukosuStr = self._parseSoukosuStr(response)
        item.soukosu = self._parseSoukosu(response)
        item.tochikenri = self._parseTochikenri(response)
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.kanriKaisya = self._parseKanriKaisya(response)
        item.kanriKeitai = self._parseKanriKeitai(response)
        item.manager = self._parseManager(response)
        item.kanrihiStr = self._parseKanrihiStr(response)
        item.kanrihi = converter.parse_numeric(item.kanrihiStr)
        item.syuzenTsumitateStr = self._parseSyuzenTsumitateStr(response)
        item.syuzenTsumitate = converter.parse_numeric(item.syuzenTsumitateStr)
        item.otherFees = self._parseOtherFees(response)
        item.tyusyajo = self._parseTyusyajo(response)
        
        item.currentStatus = self._parseCurrentStatus(response)
        item.hikiwatashi = self._parseHikiwatashi(response)
        item.torihiki = self._parseTorihiki(response)
        item.biko = self._parseBiko(response)
        item.updateDate = self._parseUpdateDate(response)
        item.nextUpdateDate = self._parseNextUpdateDate(response)
        return item



class NomuraKodateParser(NomuraParser):
    property_type = 'kodate'
    def createEntity(self): return NomuraKodate()
    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)
        item.address1 = self._parseAddress1(response)
        item.address2 = self._parseAddress2(response)
        item.address3 = self._parseAddress3(response)
        item.traffic = self._parseTrafficFull(response)
        
        item.railwayCount = self._parseRailwayCount(response)
        item.railway1 = self._parseRailway1(response)
        item.station1 = self._parseStation1(response)
        item.railwayWalkMinute1Str = self._parseRailwayWalkMinute1Str(response)
        item.railwayWalkMinute1 = self._parseRailwayWalkMinute1(response)
        item.busStation1 = self._parseBusStation1(response)
        item.busWalkMinute1Str = self._parseBusWalkMinute1Str(response)
        item.busWalkMinute1 = self._parseBusWalkMinute1(response)
        item.busUse1 = self._parseBusUse1(response)

        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        item.tatemonoMenseki = self._parseTatemonoMenseki(response)
        item.kouzou = self._parseKouzou(response)
        item.kaisuStr = self._parseKaisuStr(response)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        item.tyusyajo = self._parseTyusyajo(response)
        item.tochikenri = self._parseTochikenri(response)
        item.chimoku = self._parseChimoku(response)
        item.privateRoadBurden = self._parsePrivateRoadBurden(response)
        item.setback = self._parseSetback(response)
        item.cityPlanning = self._parseCityPlanning(response)
        
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.kenpei = self._parseKenpei(response)
        item.yousekiStr = self._parseYousekiStr(response)
        item.youseki = self._parseYouseki(response)
        
        item.currentStatus = self._parseCurrentStatus(response)
        item.hikiwatashi = self._parseHikiwatashi(response)
        item.torihiki = self._parseTorihiki(response)
        item.biko = self._parseBiko(response)
        item.updateDate = self._parseUpdateDate(response)
        item.nextUpdateDate = self._parseNextUpdateDate(response)
        return item

    def _parseTochiMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseTochiMenseki(self, response):
        value = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(value) or Decimal(0)

    def _parseTatemonoMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建物面積", specs.get("延床面積", ""))

    def _parseTatemonoMenseki(self, response):
        value = self._parseTatemonoMensekiStr(response)
        return converter.parse_menseki(value) or Decimal(0)

    def _parseChimoku(self, response):
        specs = self._get_specs(response)
        return specs.get("地目", "")

    def _parsePrivateRoadBurden(self, response):
        specs = self._get_specs(response)
        return specs.get("私道負担", "")

    def _parseSetback(self, response):
        specs = self._get_specs(response)
        return specs.get("セットバック", "")

    def _parseCityPlanning(self, response):
        specs = self._get_specs(response)
        return specs.get("都市計画", "")

    def _parseKenpeiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response):
        value = self._parseKenpeiStr(response)
        return converter.parse_numeric(value)

    def _parseYousekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response):
        value = self._parseYousekiStr(response)
        return converter.parse_numeric(value)
    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")
    def _parseFacilities(self, response):
        specs = self._get_specs(response)
        return specs.get("設備", "")

class NomuraTochiParser(NomuraParser):
    property_type = 'tochi'
    def createEntity(self): return NomuraTochi()
    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)
        item.address1 = self._parseAddress1(response)
        item.address2 = self._parseAddress2(response)
        item.address3 = self._parseAddress3(response)
        item.traffic = self._parseTrafficFull(response)
        
        item.railwayCount = self._parseRailwayCount(response)
        item.railway1 = self._parseRailway1(response)
        item.station1 = self._parseStation1(response)
        item.railwayWalkMinute1Str = self._parseRailwayWalkMinute1Str(response)
        item.railwayWalkMinute1 = self._parseRailwayWalkMinute1(response)
        item.busStation1 = self._parseBusStation1(response)
        item.busWalkMinute1Str = self._parseBusWalkMinute1Str(response)
        item.busWalkMinute1 = self._parseBusWalkMinute1(response)
        item.busUse1 = self._parseBusUse1(response)
        
        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.tochikenri = self._parseTochikenri(response)
        item.kaisuStr = "-"
        item.chimoku = self._parseChimoku(response)
        item.setsudou = self._parseSetsudou(response)
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.kenpei = self._parseKenpei(response)
        item.yousekiStr = self._parseYousekiStr(response)
        item.youseki = self._parseYouseki(response)
        item.cityPlanning = self._parseCityPlanning(response)
        
        item.currentStatus = self._parseCurrentStatus(response)
        item.hikiwatashi = self._parseHikiwatashi(response)
        item.torihiki = self._parseTorihiki(response)
        item.biko = self._parseBiko(response)
        item.updateDate = self._parseUpdateDate(response)
        item.nextUpdateDate = self._parseNextUpdateDate(response)
        return item

    def _parseTochiMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseTochiMenseki(self, response):
        value = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(value)

    def _parseChimoku(self, response):
        specs = self._get_specs(response)
        return specs.get("地目", "")

    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseKenpeiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response):
        value = self._parseKenpeiStr(response)
        return converter.parse_numeric(value)

    def _parseYousekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response):
        value = self._parseYousekiStr(response)
        return converter.parse_numeric(value)

    def _parseCityPlanning(self, response):
        specs = self._get_specs(response)
        return specs.get("都市計画", "")

class NomuraInvestmentParser(NomuraParser):
    @abstractmethod
    def createEntity(self): pass
    def _parsePropertyDetailPage(self, item, response):
        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)
        item.address1 = self._parseAddress1(response)
        item.address2 = self._parseAddress2(response)
        item.address3 = self._parseAddress3(response)
        item.traffic = self._parseTrafficFull(response)
        
        item.railwayCount = self._parseRailwayCount(response)
        item.railway1 = self._parseRailway1(response)
        item.station1 = self._parseStation1(response)
        item.railwayWalkMinute1Str = self._parseRailwayWalkMinute1Str(response)
        item.railwayWalkMinute1 = self._parseRailwayWalkMinute1(response)
        item.busStation1 = self._parseBusStation1(response)
        item.busWalkMinute1Str = self._parseBusWalkMinute1Str(response)
        item.busWalkMinute1 = self._parseBusWalkMinute1(response)
        item.busUse1 = self._parseBusUse1(response)

        item.hikiwatashi = self._parseHikiwatashiInvest(response)
        item.torihiki = self._parseTorihikiInvest(response)
        item.updateDate = self._parseUpdateDate(response)
        item.nextUpdateDate = self._parseNextUpdateDate(response)
        
        item.grossYield = self._parseGrossYield(response)
        item.annualRent = self._parseAnnualRent(response)
        item.monthlyRent = self._parseMonthlyRent(response)
        
        item.currentStatus = self._parseCurrentStatus(response)
        item.kouzou = self._parseKouzouInvest(response)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        
        item.stories = self._parseStories(response)
        item.kaisuStr = self._parseKaisuStr(response)
        item.tochiMenseki = self._parseTochiMensekiInvest(response)
        item.tatemonoMenseki = self._parseTatemonoMensekiInvest(response)
        item.biko = self._parseBiko(response)
        return item

    def _parseHikiwatashiInvest(self, response):
        specs = self._get_specs(response)
        return specs.get("引渡", specs.get("引渡時期", "即時"))

    def _parseTorihikiInvest(self, response):
        specs = self._get_specs(response)
        return specs.get("取引態様", "仲介")
    
    def _parseGrossYield(self, response):
        specs = self._get_specs(response)
        yield_val = specs.get("利回り", specs.get("表面利回り", ""))
        return Decimal(yield_val.replace("%", "").strip()) if yield_val else Decimal(0)
        
    def _parseAnnualRent(self, response):
        specs = self._get_specs(response)
        rent_val = specs.get("想定年商", specs.get("想定年間収入", specs.get("満室時想定年収", "")))
        return converter.parse_price(rent_val) if rent_val else 0

    def _parseMonthlyRent(self, response):
        annualRent = self._parseAnnualRent(response)
        return (annualRent // 12) if annualRent else 0

    def _parseKouzouInvest(self, response):
        specs = self._get_specs(response)
        return specs.get("構造", "不明")
    
    def _parseStories(self, response):
        specs = self._get_specs(response)
        stories_val = specs.get("階数", specs.get("階建", ""))
        m = re.search(r'(\d+)', stories_val) if stories_val else None
        return int(m.group(1)) if m else 0
        
    def _parseTochiMensekiInvest(self, response):
        specs = self._get_specs(response)
        land_area = specs.get("土地面積", "")
        return Decimal(str(converter.parse_menseki(land_area))) if land_area else Decimal(0)

    def _parseTatemonoMensekiInvest(self, response):
        specs = self._get_specs(response)
        bldg_area = specs.get("建物面積", specs.get("延床面積", specs.get("専有面積", "")))
        return Decimal(str(converter.parse_menseki(bldg_area))) if bldg_area else Decimal(0)

    # Missing helpers/Refactored for Investment Parsing
    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseChimoku(self, response):
        specs = self._get_specs(response)
        return specs.get("地目", "")

    def _parseYoutoChiiki(self, response):
        specs = self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseTochikenri(self, response):
        specs = self._get_specs(response)
        return specs.get("土地権利", "")

    def _parseKenpeiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response):
        value = self._parseKenpeiStr(response)
        return converter.parse_numeric(value)

    def _parseYousekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response):
        value = self._parseYousekiStr(response)
        return converter.parse_numeric(value)

    def _parseSoukosuStr(self, response):
        specs = self._get_specs(response)
        return specs.get("総戸数", specs.get("住戸数", ""))

    def _parseSoukosu(self, response):
        value = self._parseSoukosuStr(response)
        return converter.parse_numeric(value)

class NomuraInvestmentKodateParser(NomuraInvestmentParser):
    property_type = 'invest_kodate'
    def createEntity(self): return NomuraInvestmentKodate()
    def _parsePropertyDetailPage(self, item, response):
        item = super()._parsePropertyDetailPage(item, response)
        item.propertyType = "Kodate"
        item.setsudou = self._parseSetsudou(response)
        item.chimoku = self._parseChimoku(response)
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.tochikenri = self._parseTochikenri(response)
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.kenpei = self._parseKenpei(response)
        item.yousekiStr = self._parseYousekiStr(response)
        item.youseki = self._parseYouseki(response)
        return item

class NomuraInvestmentApartmentParser(NomuraInvestmentParser):
    property_type = 'invest_apartment'
    def createEntity(self): return NomuraInvestmentApartment()
    def _parsePropertyDetailPage(self, item, response):
        item = super()._parsePropertyDetailPage(item, response)
        item.propertyType = "Apartment"
        item.soukosuStr = self._parseSoukosuStr(response)
        item.soukosu = self._parseSoukosu(response)
        item.setsudou = self._parseSetsudou(response)
        item.chimoku = self._parseChimoku(response)
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.tochikenri = self._parseTochikenri(response)
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.kenpei = self._parseKenpei(response)
        item.yousekiStr = self._parseYousekiStr(response)
        item.youseki = self._parseYouseki(response)
        return item

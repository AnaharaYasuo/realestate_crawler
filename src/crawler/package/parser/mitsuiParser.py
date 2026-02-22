# -*- coding: utf-8 -*-
import sys
# from tokenize import String  # Removed problematic import
import unicodedata

from bs4 import BeautifulSoup
from abc import abstractmethod
from package.models.mitsui import MitsuiKodate, MitsuiMansion, MitsuiTochi
import importlib
importlib.reload(sys)
from decimal import Decimal
import datetime
import traceback
from concurrent.futures._base import TimeoutError
from package.parser.baseParser import LoadPropertyPageException, \
    ReadPropertyNameException, ParserBase
from bs4.element import NavigableString, Tag
import logging
import re
from package.utils.selector_loader import SelectorLoader
from package.utils import converter


class MitsuiParser(ParserBase):
    BASE_URL='https://www.rehouse.co.jp'

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('mitsui', self.property_type)

    # _get_specs is now handled by ParserBase, so it's removed from here.
        
    def getCharset(self):
        return None  # Auto-detect

    def createEntity(self):
        pass

    def getRootXpath(self):
        xpath = self.selectors.get('root_xpath', u'')
        logging.info(f"[{self.property_type}] root_xpath: {xpath}")
        return xpath

    def getRootDestUrl(self,linkUrl):
        return self.BASE_URL +  linkUrl

    async def parseRootPage(self, response):
        async for destUrl in self._parsePageCore(response, self.getRootXpath, self.getRootDestUrl):
            #yield destUrl
            yield destUrl +"city/"

    def getAreaXpath(self):
        xpath = self.selectors.get('area_xpath', u'')
        logging.info(f"[{self.property_type}] area_xpath: {xpath}")
        return xpath

    def getAreaDestUrl(self,linkUrl):
        return  self.BASE_URL + linkUrl + "?limit=1000"

    async def parseAreaPage(self, response):        
        async for destUrl in self._parsePageCore(response, self.getAreaXpath, self.getAreaDestUrl):
            yield destUrl

    def getPropertyListXpath(self):
        xpath = self.selectors.get('property_list_xpath', u'')
        logging.info(f"[{self.property_type}] property_list_xpath: {xpath}")
        return xpath

    def getPropertyListDestUrl(self,linkUrl):
        return self.BASE_URL+linkUrl

    async def parsePropertyListPage(self, response):
        
        async for destUrl in self._parsePageCore(response, self.getPropertyListXpath, self.getPropertyListDestUrl):
            yield destUrl

    async def getPropertyListNextPageUrl(self, response):
        logging.info("getPropertyListNextPageUrl")
        next_page_xpath = self.selectors.get('next_page_xpath')
        linkUrlList = response.xpath(next_page_xpath)
        if (len(linkUrlList) > 0):
            linkUrl = linkUrlList[0]
            return self.BASE_URL + linkUrl
        
        return ""

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)
        
        item.address1 = self._parseAddress1(response)
        item.address2 = self._parseAddress2(response)
        item.address3 = self._parseAddress3(response)

        item.hikiwatashi = self._parseHikiwatashi(response)
        item.genkyo = self._parseGenkyo(response)
        item.tochikenri = self._parseTochikenri(response)
        item.sonotaHiyouStr = self._parseSonotaHiyou(response)
        item.torihiki = self._parseTorihiki(response)
        item.biko = self._parseBiko(response)
        
        # Traffic
        item.railwayCount = self._parseRailwayCount(response)
        
        item.transfer1 = self._parseTransfer1(response)
        item.railway1 = self._parseRailway1(response)
        item.station1 = self._parseStation1(response)
        item.railwayWalkMinute1Str = self._parseRailwayWalkMinute1Str(response)
        item.railwayWalkMinute1 = self._parseRailwayWalkMinute1(response)
        item.busStation1 = self._parseBusStation1(response)
        item.busWalkMinute1Str = self._parseBusWalkMinute1Str(response)
        item.busWalkMinute1 = self._parseBusWalkMinute1(response)
        item.busUse1 = self._parseBusUse1(response)
        
        item.transfer2 = self._parseTransfer2(response)
        item.railway2 = self._parseRailway2(response)
        item.station2 = self._parseStation2(response)
        item.railwayWalkMinute2Str = self._parseRailwayWalkMinute2Str(response)
        item.railwayWalkMinute2 = self._parseRailwayWalkMinute2(response)
        item.busStation2 = self._parseBusStation2(response)
        item.busWalkMinute2Str = self._parseBusWalkMinute2Str(response)
        item.busWalkMinute2 = self._parseBusWalkMinute2(response)
        item.busUse2 = self._parseBusUse2(response)
        
        item.transfer3 = self._parseTransfer3(response)
        item.railway3 = self._parseRailway3(response)
        item.station3 = self._parseStation3(response)
        item.railwayWalkMinute3Str = self._parseRailwayWalkMinute3Str(response)
        item.railwayWalkMinute3 = self._parseRailwayWalkMinute3(response)
        item.busStation3 = self._parseBusStation3(response)
        item.busWalkMinute3Str = self._parseBusWalkMinute3Str(response)
        item.busWalkMinute3 = self._parseBusWalkMinute3(response)
        item.busUse3 = self._parseBusUse3(response)

        item.transfer4 = self._parseTransfer4(response)
        item.railway4 = self._parseRailway4(response)
        item.station4 = self._parseStation4(response)
        item.railwayWalkMinute4Str = self._parseRailwayWalkMinute4Str(response)
        item.railwayWalkMinute4 = self._parseRailwayWalkMinute4(response)
        item.busStation4 = self._parseBusStation4(response)
        item.busWalkMinute4Str = self._parseBusWalkMinute4Str(response)
        item.busWalkMinute4 = self._parseBusWalkMinute4(response)
        item.busUse4 = self._parseBusUse4(response)

        item.transfer5 = self._parseTransfer5(response)
        item.railway5 = self._parseRailway5(response)
        item.station5 = self._parseStation5(response)
        item.railwayWalkMinute5Str = self._parseRailwayWalkMinute5Str(response)
        item.railwayWalkMinute5 = self._parseRailwayWalkMinute5(response)
        item.busStation5 = self._parseBusStation5(response)
        item.busWalkMinute5Str = self._parseBusWalkMinute5Str(response)
        item.busWalkMinute5 = self._parseBusWalkMinute5(response)
        item.busUse5 = self._parseBusUse5(response)

        return item

    def _parsePropertyName(self, response):
        title_selector = self.selectors.get('title')
        title_tag = response.select_one(title_selector) if title_selector else None
        name = ""
        if title_tag:
             name = title_tag.get_text(strip=True)
        else:
             res = self._getValueByLabel(response, "物件名") or response.select_one("h1")
             if res: name = res.get_text(strip=True)

        if not name:
            raise ReadPropertyNameException("Could not find property name")
        return name

    def _parsePriceStr(self, response):
        specs = self._get_specs(response)
        return specs.get("価格", "")

    def _parsePrice(self, response):
        return converter.parse_price(self._parsePriceStr(response))


    def _parseAddress(self, response):
        specs = self._get_specs(response)
        return specs.get("所在地", "")

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

    def _parseHikiwatashi(self, response):
        specs = self._get_specs(response)
        return specs.get("引渡時期", "")

    def _parseGenkyo(self, response):
        specs = self._get_specs(response)
        return specs.get("現況", "")

    def _parseTochikenri(self, response):
        specs = self._get_specs(response)
        return specs.get("土地権利", "")

    def _parseSonotaHiyou(self, response):
        specs = self._get_specs(response)
        return specs.get("その他費用", "")

    def _parseTorihiki(self, response):
        specs = self._get_specs(response)
        return specs.get("取引態様", "")

    def _parseBiko(self, response):
        specs = self._get_specs(response)
        return specs.get("備考", "")

    def _parseTrafficLines(self, response):
        res = self._getValueByLabel(response, "最寄り駅") or self._getValueByLabel(response, "交通")
        if not res: return []
        lines = [p.get_text(strip=True) for p in res.find_all("p")]
        if not lines: lines = [res.get_text(strip=True)]
        return [l for l in lines if l]

    def _parseRailwayCount(self, response):
        return len(self._parseTrafficLines(response))

    def _getTrafficField(self, response, index, field_to_get, default):
        lines = self._parseTrafficLines(response)
        if index > len(lines): return default
        
        line = lines[index-1]
        
        if field_to_get == 'transfer':
            return line
        elif field_to_get == 'railway':
            m = re.search(r'^([^「]+)', line)
            return m.group(1).strip() if m else ""
        elif field_to_get == 'station':
            m = re.search(r'「([^」]+)」', line)
            return m.group(1).strip() if m else ""
        elif field_to_get == 'railwayWalkMinuteStr':
            m_walk = re.search(r'(?:徒歩|停歩)\s*(\d+)\s*分', line)
            return str(m_walk.group(1)) if m_walk else default
        elif field_to_get == 'railwayWalkMinute':
            m_walk = re.search(r'(?:徒歩|停歩)\s*(\d+)\s*分', line)
            return int(m_walk.group(1)) if m_walk else 0
        elif field_to_get == 'busWalkMinuteStr':
            m_bus = re.search(r'バス\s*(\d+)\s*分', line)
            return str(m_bus.group(1)) if m_bus else default
        elif field_to_get == 'busWalkMinute':
            m_bus = re.search(r'バス\s*(\d+)\s*分', line)
            return int(m_bus.group(1)) if m_bus else 0
        elif field_to_get == 'busStation':
             return default # Mitsui format implies bus station might be in line but parsing logic was simpler before
        elif field_to_get == 'busUse':
             return 1 if "バス" in line else 0
            
        return default

    def _parseTransfer1(self, response): return self._getTrafficField(response, 1, 'transfer', "")
    def _parseRailway1(self, response): return self._getTrafficField(response, 1, 'railway', "")
    def _parseStation1(self, response): return self._getTrafficField(response, 1, 'station', "")
    def _parseRailwayWalkMinute1Str(self, response): return self._getTrafficField(response, 1, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute1(self, response): return self._getTrafficField(response, 1, 'railwayWalkMinute', 0)
    def _parseBusStation1(self, response): return self._getTrafficField(response, 1, 'busStation', "")
    def _parseBusWalkMinute1Str(self, response): return self._getTrafficField(response, 1, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute1(self, response): return self._getTrafficField(response, 1, 'busWalkMinute', 0)
    def _parseBusUse1(self, response): return self._getTrafficField(response, 1, 'busUse', 0)

    def _parseTransfer2(self, response): return self._getTrafficField(response, 2, 'transfer', "")
    def _parseRailway2(self, response): return self._getTrafficField(response, 2, 'railway', "")
    def _parseStation2(self, response): return self._getTrafficField(response, 2, 'station', "")
    def _parseRailwayWalkMinute2Str(self, response): return self._getTrafficField(response, 2, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute2(self, response): return self._getTrafficField(response, 2, 'railwayWalkMinute', 0)
    def _parseBusStation2(self, response): return self._getTrafficField(response, 2, 'busStation', "")
    def _parseBusWalkMinute2Str(self, response): return self._getTrafficField(response, 2, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute2(self, response): return self._getTrafficField(response, 2, 'busWalkMinute', 0)
    def _parseBusUse2(self, response): return self._getTrafficField(response, 2, 'busUse', 0)

    def _parseTransfer3(self, response): return self._getTrafficField(response, 3, 'transfer', "")
    def _parseRailway3(self, response): return self._getTrafficField(response, 3, 'railway', "")
    def _parseStation3(self, response): return self._getTrafficField(response, 3, 'station', "")
    def _parseRailwayWalkMinute3Str(self, response): return self._getTrafficField(response, 3, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute3(self, response): return self._getTrafficField(response, 3, 'railwayWalkMinute', 0)
    def _parseBusStation3(self, response): return self._getTrafficField(response, 3, 'busStation', "")
    def _parseBusWalkMinute3Str(self, response): return self._getTrafficField(response, 3, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute3(self, response): return self._getTrafficField(response, 3, 'busWalkMinute', 0)
    def _parseBusUse3(self, response): return self._getTrafficField(response, 3, 'busUse', 0)

    def _parseTransfer4(self, response): return self._getTrafficField(response, 4, 'transfer', "")
    def _parseRailway4(self, response): return self._getTrafficField(response, 4, 'railway', "")
    def _parseStation4(self, response): return self._getTrafficField(response, 4, 'station', "")
    def _parseRailwayWalkMinute4Str(self, response): return self._getTrafficField(response, 4, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute4(self, response): return self._getTrafficField(response, 4, 'railwayWalkMinute', 0)
    def _parseBusStation4(self, response): return self._getTrafficField(response, 4, 'busStation', "")
    def _parseBusWalkMinute4Str(self, response): return self._getTrafficField(response, 4, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute4(self, response): return self._getTrafficField(response, 4, 'busWalkMinute', 0)
    def _parseBusUse4(self, response): return self._getTrafficField(response, 4, 'busUse', 0)

    def _parseTransfer5(self, response): return self._getTrafficField(response, 5, 'transfer', "")
    def _parseRailway5(self, response): return self._getTrafficField(response, 5, 'railway', "")
    def _parseStation5(self, response): return self._getTrafficField(response, 5, 'station', "")
    def _parseRailwayWalkMinute5Str(self, response): return self._getTrafficField(response, 5, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute5(self, response): return self._getTrafficField(response, 5, 'railwayWalkMinute', 0)
    def _parseBusStation5(self, response): return self._getTrafficField(response, 5, 'busStation', "")
    def _parseBusWalkMinute5Str(self, response): return self._getTrafficField(response, 5, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute5(self, response): return self._getTrafficField(response, 5, 'busWalkMinute', 0)
    def _parseBusUse5(self, response): return self._getTrafficField(response, 5, 'busUse', 0)

    def _parseSetudouDetails(self, setsudou):
        details = {
            'douroHaba': 0,
            'douroKubun': "",
            'douroMuki': "",
            'setsumen': Decimal(0)
        }
        if not setsudou: return details
        
        target_setsudou = setsudou
        max_haba = -1.0
        
        for wkStr in setsudou.split(u"、"):
            douroHabaObj = re.search(r'[0-9\.]+', wkStr.split(u"ｍ")[0])
            try:
                if douroHabaObj:
                    haba = float(douroHabaObj.group())
                    if haba > max_haba:
                        max_haba = haba
                        target_setsudou = wkStr
                        
                        details['douroHaba'] = douroHabaObj.group()
                        details['douroKubun'] = wkStr.split(u"ｍ")[1].replace(u"(","").replace(u")","").strip()
                        details['douroMuki'] = wkStr[0:(douroHabaObj.start())].split("：")[0]
                        details['setsumen'] = Decimal(0)
            except: pass
        return details

    def _parseKenpeiDetails(self, value):
        if not value: return None
        if(value.find(u"前面道路幅員により")>-1 and value.find(u"前面道路幅員により前面道路幅員")==-1):
            s:str = value.split(u"前面道路幅員により")[1].split(u"％")[0]
            s=unicodedata.normalize("NFKD", s)
            sObj = re.search(r'[0-9\.]+', s)
            return sObj.group() if sObj else None
        else:
            try: return int(value.split("%")[0].strip())
            except: return None

    def _parseYousekiDetails(self, value):
        if not value: return None
        if(value.find(u"前面道路幅員により")>-1 and value.find(u"前面道路幅員により前面道路幅員")==-1):
            s:str = value.split(u"前面道路幅員により")[1].split("％")[0]
            s=unicodedata.normalize("NFKD", s)
            sObj = re.search(r'[0-9\.]+', s)
            return sObj.group() if sObj else None
        else:
            try: return int(value.split("%")[0].strip())
            except: return None



class MitsuiMansionParser(MitsuiParser):
    property_type = 'mansion'

    def createEntity(self):
        return  MitsuiMansion()
    
    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        item.madori = self._parseMadori(response)
        item.senyuMensekiStr = self._parseSenyuMensekiStr(response)
        item.senyuMenseki = self._parseSenyuMenseki(response)
        item.kaisuStr = self._parseKaisuStr(response)
        item.kaisu = self._parseKaisu(response)
        item.kouzou = self._parseKouzou(response)


        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        item.kyutaishin = self._parseKyutaishin(response)

        item.balconyMensekiStr = self._parseBalconyMensekiStr(response)
        item.balconyMenseki = self._parseBalconyMenseki(response)
        
        item.saikou = self._parseSaikou(response)
        item.soukosuStr = self._parseSoukosuStr(response)
        item.soukosu = self._parseSoukosu(response)
        
        item.kanriKaisya = self._parseKanriKaisya(response)
        item.kanriKeitai = self._parseKanriKeitai(response)
        item.kanriKeitaiKaisya = self._parseKanriKeitaiKaisya(response)
        
        item.kanrihiStr = self._parseKanrihiStr(response)
        item.kanrihi = self._parseKanrihi(response)
        
        item.syuzenTsumitateStr = self._parseSyuzenTsumitateStr(response)
        item.syuzenTsumitate = self._parseSyuzenTsumitate(response)

        item.tyusyajo = self._parseTyusyajo(response)
        item.bunjoKaisya = self._parseBunjoKaisya(response)
        item.sekouKaisya = self._parseSekouKaisya(response)
        
        # Derived fields from kaisu
        item.kaisuStr = self._parseKaisuStr(response)
        item.floorType_kai = self._parseFloorTypeKai(response)
        item.floorType_chijo = self._parseFloorTypeChijo(response)
        item.floorType_chika = self._parseFloorTypeChika(response)
        
        # Derived fields from kouzou
        item.floorType_kouzou = self._parseFloorTypeKouzou(response)
        
        # Others
        item.saikouKadobeya = self._parseSaikouKadobeya(response)
        item.kadobeya = "-"
        item.senyouNiwaMenseki = self._parseSenyouNiwaMenseki(response)
        item.roofBalconyMenseki = self._parseRoofBalconyMenseki(response)
        
        # Derived metrics
        item.kanrihi_p_heibei = self._parseKanrihiPerHeibei(response)
        item.syuzenTsumitate_p_heibei = self._parseSyuzenPerHeibei(response)

        return item

    def _parseKouzou(self, response):
        specs = self._get_specs(response)
        return specs.get("構造", "-")

    def _parseKaisuStr(self, response):
        specs = self._get_specs(response)
        val = specs.get("所在階") or specs.get("所在階 / 階建") or specs.get("階数") or specs.get("階数 / 階建", "")
        return val

    def _parseKaisu(self, response):
        val = self._parseKaisuStr(response)
        if val:
            try: return int(re.search(r'(\d+)', val).group(1))
            except: pass
        return 0

    def _convert_price_string(self, price_str):
        if not price_str: return 0
        if "万" in price_str: return converter.parse_price(price_str)
        return converter.parse_yen(price_str)

    def _parseChikunengetsuStr(self, response):
        specs = self._get_specs(response)
        return specs.get("築年月", "")

    def _parseMadori(self, response):
        specs = self._get_specs(response)
        return specs.get("間取り", "")

    def _parseSenyuMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("専有面積", "")

    def _parseSenyuMenseki(self, response):
        mensekiStr = self._parseSenyuMensekiStr(response)
        return converter.parse_menseki(mensekiStr) if mensekiStr else Decimal(0)

    def _parseKyutaishin(self, response):
        dt = self._parseChikunengetsu(response)
        try:
            if dt and dt < datetime.date(1982, 1, 1):
                return 1
        except: pass
        return 0

    def _parseBalconyMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("バルコニー", "")
    
    def _parseBalconyMenseki(self, response):
         mensekiStr = self._parseBalconyMensekiStr(response)
         return converter.parse_menseki(mensekiStr) if mensekiStr else None

    def _parseSaikou(self, response):
        specs = self._get_specs(response)
        return specs.get("向き", "")

    def _parseSoukosuStr(self, response):
        specs = self._get_specs(response)
        return specs.get("総戸数", "")

    def _parseChikunengetsu(self, response):
        chikunengetsuStr = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(chikunengetsuStr) if chikunengetsuStr else None

    def _parseSoukosu(self, response):
        soukosuStr = self._parseSoukosuStr(response)
        if soukosuStr and soukosuStr != "-":
            try: return int(str(soukosuStr).replace(",", "").replace("戸", "").strip())
            except: pass
        return 0

    def _parseKanriKaisya(self, response):
        specs = self._get_specs(response)
        return specs.get("管理会社", "")

    def _parseKanriKeitai(self, response):
        specs = self._get_specs(response)
        return specs.get("管理形態(方式)", specs.get("管理形態", ""))

    def _parseKanriKeitaiKaisya(self, response):
        specs = self._get_specs(response)
        return specs.get("管理員の勤務形態", "-")

    def _parseKanrihiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("管理費等", "")

    def _parseKanrihi(self, response):
        kanrihiStr = self._parseKanrihiStr(response)
        if kanrihiStr and "-" not in kanrihiStr:
            try: return int(str(kanrihiStr).replace(",", "").replace("円", "").split("/")[0].strip())
            except: pass
        return 0

    def _parseSyuzenTsumitateStr(self, response):
        specs = self._get_specs(response)
        return specs.get("修繕積立金", "")

    def _parseSyuzenTsumitate(self, response):
        syuzenStr = self._parseSyuzenTsumitateStr(response)
        if syuzenStr and "-" not in syuzenStr:
            try: return int(str(syuzenStr).replace(",", "").replace("円", "").split("/")[0].strip())
            except: pass
        return 0

    def _parseTyusyajo(self, response):
        specs = self._get_specs(response)
        return specs.get("駐車場", "")

    def _parseBunjoKaisya(self, response):
        specs = self._get_specs(response)
        return specs.get("分譲会社", "").replace(" (新築分譲時における売主)", "")

    def _parseSekouKaisya(self, response):
        specs = self._get_specs(response)
        return specs.get("施工会社", "")



    def _parseFloorTypeKai(self, response):
        return self._parseKaisu(response)

    def _parseFloorTypeChijo(self, response):
        kaisu = self._parseKaisuStr(response)
        if not kaisu or " / 地上" not in kaisu: return None
        try: return int(kaisu.split(u" / 地上")[1].split(u" 地下")[0].replace(u"階", "").replace(u"建", ""))
        except: return None

    def _parseFloorTypeChika(self, response):
        kaisu = self._parseKaisuStr(response)
        if not kaisu or " 地下" not in kaisu: return 0
        try: return int(kaisu.split(u" 地下")[1].replace(u"階", "").replace(u"建", ""))
        except: return 0

    def _parseFloorTypeKouzou(self, response):
        kouzou = self._parseKouzou(response)
        if kouzou == u"鉄筋コンクリート造": return "ＲＣ造"
        if kouzou == u"鉄骨鉄筋コンクリート造": return "ＳＲＣ造"
        if kouzou == u"鉄骨造": return "Ｓ造"
        if kouzou == u"木造": return "木造"
        return ""

    def _parseSaikouKadobeya(self, response):
        specs = self._get_specs(response)
        return specs.get("角部屋", "-")

    def _parseSenyouNiwaMenseki(self, response):
        specs = self._get_specs(response)
        s = specs.get("専用庭", "")
        if s:
            try: return converter.parse_menseki(s)
            except: pass
        return Decimal(0)

    def _parseRoofBalconyMenseki(self, response):
        specs = self._get_specs(response)
        s = specs.get("ルーフバルコニー", "")
        if s:
            try: return converter.parse_menseki(s)
            except: pass
        return Decimal(0)

    def _parseKanrihiPerHeibei(self, response):
        kanrihi = self._parseKanrihi(response)
        menseki = self._parseSenyuMenseki(response)
        if kanrihi and menseki:
            raw_val = kanrihi / menseki
            return round(Decimal(str(raw_val)), 3) if raw_val < 10000000 else None
        return None

    def _parseSyuzenPerHeibei(self, response):
        syuzen = self._parseSyuzenTsumitate(response)
        menseki = self._parseSenyuMenseki(response)
        if syuzen and menseki:
            raw_val = syuzen / menseki
            return round(Decimal(str(raw_val)), 3) if raw_val < 10000000 else None
        return None

class MitsuiTochiParser(MitsuiParser):
    property_type = 'tochi'
    def createEntity(self):
        return  MitsuiTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.kenchikuJoken = self._parseKenchikuJoken(response)
        item.chimoku = self._parseChimoku(response)
        
        item.setsudou = self._parseSetsudou(response)
        item.douroHaba = self._parseDouroHaba(response)
        item.douroKubun = self._parseDouroKubun(response)
        item.douroMuki = self._parseDouroMuki(response)
        item.setsumen = self._parseSetsumen(response)
        
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.kenpei = self._parseKenpei(response)
        
        item.yousekiStr = self._parseYousekiStr(response)
        item.youseki = self._parseYouseki(response)
        
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.kuiki = self._parseKuiki(response)
        item.kokudoHou = self._parseKokudoHou(response)

        return item

    def _parseTochiMenseki(self, response):
        tochiMensekiStr = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(tochiMensekiStr) if tochiMensekiStr else Decimal(0)

    def _parseTochiMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseKenchikuJoken(self, response):
        specs = self._get_specs(response)
        return specs.get("建築条件", "-")

    def _parseChimoku(self, response):
        specs = self._get_specs(response)
        return specs.get("地目", "-")

    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseDouroHaba(self, response):
        return self._parseSetudouDetails(self._parseSetsudou(response))['douroHaba']

    def _parseDouroKubun(self, response):
        return self._parseSetudouDetails(self._parseSetsudou(response))['douroKubun']

    def _parseDouroMuki(self, response):
        return self._parseSetudouDetails(self._parseSetsudou(response))['douroMuki']

    def _parseSetsumen(self, response):
        return self._parseSetudouDetails(self._parseSetsudou(response))['setsumen']

    def _parseKenpeiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response):
        return self._parseKenpeiDetails(self._parseKenpeiStr(response))

    def _parseYousekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response):
        return self._parseYousekiDetails(self._parseYousekiStr(response))

    def _parseYoutoChiiki(self, response):
        specs = self._get_specs(response)
        return specs.get("用途地域", "-")

    def _parseKuiki(self, response):
        specs = self._get_specs(response)
        return specs.get("都市計画", "-")

    def _parseKokudoHou(self, response):
        specs = self._get_specs(response)
        return specs.get("国土法", "-")

    def _parseSetudouDetails(self, value):
        # Default to safe values for DB (Decimal fields need "0", CharFields can handle "-")
        res = {'douroHaba': "0", 'douroKubun': "-", 'douroMuki': "-", 'setsumen': "0"}
        if not value: return res
        
        m_muki = re.search(u'(北|東|西|南)+', value)
        if m_muki: res['douroMuki'] = m_muki.group(0)
        
        m_haba = re.search(r'幅員\s*([\d\.]+)\s*m', value)
        if m_haba: res['douroHaba'] = m_haba.group(1)
        
        m_setsumen = re.search(r'接面\s*([\d\.]+)\s*m', value)
        if m_setsumen: res['setsumen'] = m_setsumen.group(1)
        
        # 道路区分
        for k in [u"公道", u"私道"]:
            if k in value:
                res['douroKubun'] = k
                break
        return res

    def _parseKenpeiDetails(self, value):
        if not value: return 0
        m = re.search(r'(\d+)%', value)
        return int(m.group(1)) if m else 0

    def _parseYousekiDetails(self, value):
        if not value: return 0
        m = re.search(r'(\d+)%', value)
        return int(m.group(1)) if m else 0

class MitsuiKodateParser(MitsuiParser):
    property_type = 'kodate'
    def createEntity(self):
        return  MitsuiKodate()

    def get_table_value_sub(self, tr):
        val = tr.select_one('.table-data')
        if val: return val.get_text(strip=True)
        tds = tr.select('td')
        return tds[1].get_text(strip=True) if len(tds) > 1 else ""

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        item.tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        item.tatemonoMenseki = self._parseTatemonoMenseki(response)
        
        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        
        item.kaisuKouzou = self._parseKaisuKouzou(response)
        item.kouzou = self._parseKouzou(response)
        item.kaisu = self._parseKaisu(response)
        item.kaisuStr = self._parseKaisuStr(response)
        
        item.tyusyajo = self._parseTyusyajo(response)
        item.chimoku = self._parseChimoku(response)
        
        item.setsudou = self._parseSetsudou(response)
        item.douroHaba = self._parseDouroHaba(response)
        item.douroKubun = self._parseDouroKubun(response)
        item.douroMuki = self._parseDouroMuki(response)
        item.setsumen = self._parseSetsumen(response)
        
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.kenpei = self._parseKenpei(response)
        
        item.yousekiStr = self._parseYousekiStr(response)
        item.youseki = self._parseYouseki(response)
        
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.kuiki = self._parseKuiki(response)

        return item

    def _parseTatemonoMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建物面積", specs.get("延床面積", ""))

    def _parseTatemonoMenseki(self, response):
        tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        return converter.parse_menseki(tatemonoMensekiStr) if tatemonoMensekiStr else Decimal(0)

    def _parseTochiMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseTochiMenseki(self, response):
        tochiMensekiStr = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(tochiMensekiStr) if tochiMensekiStr else Decimal(0)

    def _parseKaisuKouzou(self, response):
        specs = self._get_specs(response)
        return specs.get("建物構造", "")

    def _parseKouzouFromKaisuKouzou(self, value):
        if not value: return ""
        if "その他" in value: return "その他"
        if "-" in value: return "-"
        try: return value.split("造")[0].strip() + "造"
        except: return value

    def _parseKaisuFromKaisuKouzou(self, value):
        if not value: return ""
        if "その他" in value:
            try: return value.split("その他")[1].strip()
            except: return ""
        if "-" in value: return ""
        try: return value.split("造")[1].strip()
        except: return value

    def _parseKaisuStrFromKaisuKouzou(self, value):
        if not value: return None
        stories_match = re.search(r'(\d+)階建', value)
        return str(stories_match.group(1)) if stories_match else None

    def _parseKouzou(self, response):
        value = self._parseKaisuKouzou(response)
        return self._parseKouzouFromKaisuKouzou(value)

    def _parseKaisu(self, response):
        value = self._parseKaisuKouzou(response)
        return self._parseKaisuFromKaisuKouzou(value)

    def _parseKaisuStr(self, response):
        value = self._parseKaisuKouzou(response)
        return self._parseKaisuStrFromKaisuKouzou(value)

    def _parseTyusyajo(self, response):
        specs = self._get_specs(response)
        return specs.get("駐車場", "")

    def _parseChimoku(self, response):
        specs = self._get_specs(response)
        return specs.get("地目", "")

    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseDouroHaba(self, response):
        return self._parseSetudouDetails(response)['douroHaba']

    def _parseDouroKubun(self, response):
        return self._parseSetudouDetails(response)['douroKubun']

    def _parseDouroMuki(self, response):
        return self._parseSetudouDetails(response)['douroMuki']

    def _parseSetsumen(self, response):
        return self._parseSetudouDetails(response)['setsumen']

    def _parseKenpeiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response):
        return self._parseKenpeiDetails(response)

    def _parseYousekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response):
        return self._parseYousekiDetails(response)

    def _parseYoutoChiiki(self, response):
        specs = self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseKuiki(self, response):
        specs = self._get_specs(response)
        return specs.get("都市計画", "")

    def _parseSetudouDetails(self, response):
        value = self._parseSetsudou(response)
        # Default to safe values for DB (Decimal fields need "0", CharFields can handle "-")
        res = {'douroHaba': "0", 'douroKubun': "-", 'douroMuki': "-", 'setsumen': "0"}
        if not value: return res
        
        m_muki = re.search(u'(北|東|西|南)+', value)
        if m_muki: res['douroMuki'] = m_muki.group(0)
        
        m_haba = re.search(r'幅員\s*([\d\.]+)\s*m', value)
        if m_haba: res['douroHaba'] = m_haba.group(1)
        
        m_setsumen = re.search(r'接面\s*([\d\.]+)\s*m', value)
        if m_setsumen: res['setsumen'] = m_setsumen.group(1)
        
        # 道路区分
        for k in [u"公道", u"私道"]:
            if k in value:
                res['douroKubun'] = k
                break
        return res

    def _parseKenpeiDetails(self, response):
        value = self._parseKenpeiStr(response)
        if not value: return 0
        m = re.search(r'(\d+)%', value)
        return int(m.group(1)) if m else 0

    def _parseYousekiDetails(self, response):
        value = self._parseYousekiStr(response)
        if not value: return 0
        m = re.search(r'(\d+)%', value)
        return int(m.group(1)) if m else 0


class MitsuiInvestmentParser(MitsuiParser):

    property_type = 'investment'
    
    def getRootDestUrl(self,linkUrl):
        # 投資用トップからのリンクは相対パス(prefecture/13/)なので、プレフィックスを調整
        if linkUrl.startswith('prefecture/'):
            return self.BASE_URL + "/buy/tohshi/" + linkUrl
        return self.BASE_URL + linkUrl

    def createEntity(self):
        # Abstract or default to Kodate if instantiated directly (should not happen for scraping)
        from package.models.mitsui import MitsuiInvestmentKodate
        return MitsuiInvestmentKodate()

    def _scrape_to_dict(self, soup: BeautifulSoup):
        # Override to handle tables with only td elements (no th)
        data = super()._scrape_to_dict(soup)
        
        if not soup: return data

        # Fallback for tables where headers are td (not th)
        # Verify valid tables by checking if we found little data
        # or just run this strategy anyway as addition
        for tr in soup.find_all("tr"):
            # If already processed by base (th/td), skip? 
            # Base uses th find. If found, it's in data.
            # But we might have mixed rows.
            
            cells = tr.find_all(['th', 'td'])
            if len(cells) >= 2:
                # Assume chunks of 2: Label, Value, Label, Value...
                # Mitsui tables often have 2 or 4 columns
                for i in range(0, len(cells), 2):
                    if i + 1 < len(cells):
                        key = cells[i].get_text(strip=True)
                        val = cells[i+1] # Keep as Tag for compatibility
                        
                        # Only add if not present (prefer th if base found it)
                        if key and key not in data:
                             data[key] = val
        return data

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        
        item.grossYield = self._parseGrossYield(response)
        item.annualRent = self._parseAnnualRent(response)
        item.monthlyRent = self._parseMonthlyRent(response)
        item.currentStatus = self._parseCurrentStatus(response)
        item.kouzou = self._parseKouzou(response)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.kenpei = self._parseKenpei(response)
        item.yousekiStr = self._parseYousekiStr(response)
        item.youseki = self._parseYouseki(response)
        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        item.tatemonoMenseki = self._parseTatemonoMenseki(response)
        item.kaisuStr = self._parseKaisuStr(response)
        item.madori = self._parseMadori(response)
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.setsudou = self._parseSetsudou(response)
        item.tochikenri = self._parseTochikenri(response)
        item.chimoku = self._parseChimoku(response)

        return item

    def _parseGrossYield(self, response):
        specs = self._get_specs(response)
        yield_val = specs.get("利回り", specs.get("表面利回り", specs.get("想定利回り", "")))
        if yield_val:
            try: return Decimal(yield_val.replace("%", "").strip())
            except: pass
        return Decimal(0)

    def _parseAnnualRent(self, response):
        specs = self._get_specs(response)
        rent_val = specs.get("想定年収", specs.get("年間想定賃料", specs.get("想定賃料", specs.get("想定年額", specs.get("想定賃料(年間)", "")))))
        if not rent_val: return 0
        if "円" in rent_val and "万" not in rent_val:
            try:
                val = rent_val.replace(",", "").replace("円", "")
                val = re.sub(r'[（\(].*?[）\)]', '', val)
                return int(val)
            except: return 0
        return converter.parse_price(rent_val)

    def _parseMonthlyRent(self, response):
        annualRent = self._parseAnnualRent(response)
        return (annualRent // 12) if annualRent else 0

    def _parseCurrentStatus(self, response):
        specs = self._get_specs(response)
        return specs.get("現況", specs.get("賃貸状況", ""))


    def _parseKouzou(self, response):
        specs = self._get_specs(response)
        return specs.get("構造", specs.get("建物構造", ""))

    def _parseChikunengetsuStr(self, response):
        specs = self._get_specs(response)
        return specs.get("築年月", "")

    def _parseChikunengetsu(self, response):
        s = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(s) if s else None

    def _parseTochiMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseTochiMenseki(self, response):
        land_area = self._parseTochiMensekiStr(response)
        if land_area:
             try: return Decimal(str(converter.parse_menseki(land_area)))
             except: pass
        return Decimal(0)

    def _parseTatemonoMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建物面積", specs.get("専有面積", specs.get("延床面積", "")))

    def _parseTatemonoMenseki(self, response):
        bldg_area = self._parseTatemonoMensekiStr(response)
        if bldg_area:
             try: return Decimal(str(converter.parse_menseki(bldg_area)))
             except: pass
        return Decimal(0)

    def _parseKaisuStr(self, response):
        specs = self._get_specs(response)
        kaisu = specs.get("階数", "")
        if kaisu: return kaisu
        kouzou = self._parseKouzou(response)
        if kouzou:
            stories_match = re.search(r'(\d+)階', kouzou)
            if stories_match: return str(stories_match.group(1))
        return None

    def _parseMadori(self, response):
        specs = self._get_specs(response)
        return specs.get("間取り", "")

    def _parseYoutoChiiki(self, response): # Renamed from _parseZoning
        specs = self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseTochikenri(self, response):
        specs = self._get_specs(response)
        return specs.get("土地権利", "")

    def _parseChimoku(self, response):
        specs = self._get_specs(response)
        return specs.get("地目", "")

    def _parseKenpeiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response):
        return self._parseKenpeiDetails(self._parseKenpeiStr(response))

    def _parseYousekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response):
        return self._parseYousekiDetails(self._parseYousekiStr(response))


# ========== Investment Kodate & Apartment Parsers ==========
# API endpoint separation: dedicated parsers for each property type

class MitsuiInvestmentKodateParser(MitsuiInvestmentParser):
    """
    Kodate (戸建て賃貸) 専用パーサー
    MitsuiInvestmentKodate モデルに保存
    一棟物件のみを対象（buildingTypes=1,2,3）
    """
    def createEntity(self):
        from package.models.mitsui import MitsuiInvestmentKodate
        return MitsuiInvestmentKodate()
    
    async def parseAreaPage(self, response):
        """
        一棟物件用のフィルタリング: buildingTypes=4 を付与 (戸建)
        4: 戸建
        """
        building_types = [4]
        
        async for base_url in self._parsePageCore(response, self.getAreaXpath, self.getAreaDestUrl):
            # Each area URL gets variant with buildingTypes=4
            for building_type in building_types:
                # Add buildingTypes parameter to existing URL
                separator = '&' if '?' in base_url else '?'
                filtered_url = f"{base_url}{separator}buildingTypes={building_type}"
                logging.info(f"[Kodate] Generated URL with buildingTypes={building_type}: {filtered_url}")
                yield filtered_url
    
    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        item.propertyType = "Kodate"
        return item


class MitsuiInvestmentApartmentParser(MitsuiInvestmentParser):
    """
    Apartment (アパート) 専用パーサー
    MitsuiInvestmentApartment モデルに保存
    区分所有物件のみを対象（/mansion/ パス）
    """
    def createEntity(self):
        from package.models.mitsui import MitsuiInvestmentApartment
        return MitsuiInvestmentApartment()

    async def parseAreaPage(self, response):
        """
        一棟物件用のフィルタリング: buildingTypes=2 を付与 (アパート)
        2: 一棟アパート
        """
        building_types = [2]
        
        async for base_url in self._parsePageCore(response, self.getAreaXpath, self.getAreaDestUrl):
            # Each area URL gets variant with buildingTypes=2
            for building_type in building_types:
                # Add buildingTypes parameter to existing URL
                separator = '&' if '?' in base_url else '?'
                filtered_url = f"{base_url}{separator}buildingTypes={building_type}"
                logging.info(f"[Apartment] Generated URL with buildingTypes={building_type}: {filtered_url}")
                yield filtered_url

    async def parsePropertyListPage(self, response):
        """
        すべての中身を取得（一棟アパートとしてフィルタリング済みのため）
        """
        async for dest_url in self._parsePageCore(response, self.getPropertyListXpath, self.getPropertyListDestUrl):
            yield dest_url

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        item.propertyType = "Apartment"
        
        item.soukosuStr = self._parseSoukosuStr(response)
        item.soukosu = self._parseSoukosu(response)
        item.kanrihi = self._parseKanrihi(response)
        item.syuzenTsumitate = self._parseSyuzenTsumitate(response)

        return item

    def _parseKanrihi(self, response):
        specs = self._get_specs(response)
        return converter.parse_price(specs["管理費"]) if "管理費" in specs else 0
    
    def _parseSyuzenTsumitate(self, response):
        specs = self._get_specs(response)
        return converter.parse_price(specs["修繕積立金"]) if "修繕積立金" in specs else 0

    def _parseSoukosuStr(self, response):
        specs = self._get_specs(response)
        val = specs.get("総戸数", "")
        if val: return val
        
        # Fallback: Extract from "賃貸状況" (Rental Status) if available
        # Example value: "総戸数7戸、稼働戸数4戸"
        status = specs.get("賃貸状況", specs.get("現況", ""))
        if status:
            # Look for pattern like "総戸数X戸"
            match = re.search(r'総戸数\s*(\d+戸?)', status)
            if match:
                return f"総戸数{match.group(1)}"
        
        return ""

    def _parseSoukosu(self, response):
        specs = self._get_specs(response)
        soukosu = 0
        total_units = self._parseSoukosuStr(response)
        if total_units:
             match = re.search(r'(\d+)', total_units)
             if match: soukosu = int(match.group(1))

        if not soukosu:
             # Fallback logic to other fields if necessary, but keep it minimal
             pass
        
        return soukosu

# -*- coding: utf-8 -*-
import importlib
import sys

# from tokenize import String  # Removed problematic import
import unicodedata

from bs4 import BeautifulSoup

from package.models.mitsui import MitsuiKodate, MitsuiMansion, MitsuiTochi

importlib.reload(sys)
import datetime
import logging
import re
from decimal import Decimal, InvalidOperation

from package.parser.baseParser import (
    InvestmentParserBase,
    KodateParserBase,
    MansionParserBase,
    ParserBase,
    TochiParserBase,
)
from package.utils import converter
from package.utils.selector_loader import SelectorLoader


class MitsuiParser(ParserBase):

    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    property_type = ""
    BASE_URL='https://www.rehouse.co.jp'

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('mitsui', self.property_type)

    # _get_specs is now handled by ParserBase, so it's removed from here.
        
    def getCharset(self):
        return None  # Auto-detect

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        return super()._parseTransport1(response, specs)

    def createEntity(self):
        pass

    def getRootXpath(self):
        xpath = self.selectors.get('root_xpath', u'')
        logging.info(f"[{self.property_type}] root_xpath: {xpath}")
        return xpath

    def getRootDestUrl(self, linkUrl):
        if not linkUrl:
            return ""
        if linkUrl.startswith("http"):
            url = linkUrl
        elif linkUrl.startswith("/"):
            url = self.BASE_URL + linkUrl
        else:
            section = "tohshi" if self.property_type == "investment" else self.property_type
            url = f"{self.BASE_URL}/buy/{section}/{linkUrl}"
        return url

    async def parseRootPage(self, response):
        async for destUrl in self._parsePageCore(response, self.getRootXpath, self.getRootDestUrl):
            if not destUrl:
                continue
            if not destUrl.startswith("http"):
                destUrl = self.BASE_URL + ("/" if not destUrl.startswith("/") else "") + destUrl
            # 都道府県URL (/prefecture/XX/) の場合、市区町村選択親ページ (/city/) へ誘導
            if re.search(r'/prefecture/\d+/?$', destUrl):
                destUrl = destUrl.rstrip('/') + '/city/'
            yield destUrl

    def getAreaXpath(self):
        xpath = self.selectors.get('area_xpath', u'')
        logging.info(f"[{self.property_type}] area_xpath: {xpath}")
        return xpath

    def getAreaDestUrl(self, linkUrl):
        if not linkUrl:
            return ""
        # 親ページ自身 (/city/) はスキップ
        clean = linkUrl.split("?")[0].rstrip("/")
        if clean.endswith("/city"):
            return ""
        dest = self.BASE_URL + linkUrl if not linkUrl.startswith("http") else linkUrl
        separator = "&" if "?" in dest else "?"
        return f"{dest}{separator}limit=1000"

    async def parseAreaPage(self, response):        
        async for destUrl in self._parsePageCore(response, self.getAreaXpath, self.getAreaDestUrl):
            if destUrl:
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
        try:
            if hasattr(response, 'select_one'):
                next_css = self.selectors.get('next_page_css', 'a.pagination-next, a.is-next, a[rel="next"]')
                next_el = response.select_one(next_css)
                if not next_el:
                    next_el = response.find('a', string=re.compile("次へ|次"))
                if next_el and next_el.get('href'):
                    href = next_el.get('href')
                    return href if href.startswith('http') else self.BASE_URL + href
        except (AttributeError, TypeError, ValueError, KeyError) as e:
            logging.warning(f"getPropertyListNextPageUrl exception: {e}")
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
        
        # 築年月の追加
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        
        # Traffic
        traffic_lines = self._parseTrafficLines(response)
        item.railwayCount = len(traffic_lines)
        traffic_str = "  ".join(traffic_lines)
        self._populateTraffic(item, traffic_str)

        return item

    def _parseChikunengetsuStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("築年月", "")

    def _parseChikunengetsu(self, response, specs=None):
        s = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(s) if s else None

    def _parsePriceStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("価格", "")

    def _parsePrice(self, response, specs=None):
        return converter.parse_price(self._parsePriceStr(response))


    def _parseAddress(self, response, specs=None):
        specs = self._get_specs(response)
        addr = specs.get("所在地", "")
        if addr:
            addr = re.sub(r'GoogleMaps.*$', '', addr).strip()
        return addr

    def _parseAddress1(self, response, specs=None):
        address = self._parseAddress(response)
        pref, _, _ = self._split_address(address)
        return pref

    def _parseAddress2(self, response, specs=None):
        address = self._parseAddress(response)
        _, city, _ = self._split_address(address)
        return city

    def _parseAddress3(self, response, specs=None):
        address = self._parseAddress(response)
        _, _, town = self._split_address(address)
        return town.strip() if town else ""

    def _parseHikiwatashi(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("引渡時期", "")

    def _parseGenkyo(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("現況", "")

    def _parseTochikenri(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("土地権利", "")

    def _parseSonotaHiyou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("その他費用", "")

    def _parseTorihiki(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("取引態様", "")

    def _parseBiko(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("備考", "")

    def _parseTrafficLines(self, response, specs=None):
        res = self._getValueByLabel(response, "最寄り駅") or self._getValueByLabel(response, "交通")
        if not res: return []
        
        lines = []
        for p in res.find_all("p"):
            text_parts = list(p.stripped_strings)
            if text_parts:
                lines.append(" ".join(text_parts))
            
        if not lines:
            text_parts = list(res.stripped_strings)
            if text_parts:
                lines = [" ".join(text_parts)]

        filtered_lines = []
        for l in lines:
            if l and not ("@context" in l or "schema" in l.lower() or "{" in l):
                filtered_lines.append(l)
        return filtered_lines

    def _parseRailwayCount(self, response, specs=None):
        return len(self._parseTrafficLines(response))

    def _getTrafficField(self, response, index, field_to_get, default):
        lines = self._parseTrafficLines(response)
        if index > len(lines):
            return default
        line = lines[index - 1]
        handler = {
            "transfer": lambda: line,
            "railway": lambda: self._traffic_railway(line),
            "station": lambda: self._traffic_station(line),
            "railwayWalkMinuteStr": lambda: self._traffic_walk_str(line, default),
            "railwayWalkMinute": lambda: self._traffic_walk_int(line),
            "busWalkMinuteStr": lambda: self._traffic_bus_str(line, default),
            "busWalkMinute": lambda: self._traffic_bus_int(line),
            "busStation": lambda: default,
            "busUse": lambda: 1 if "バス" in line else 0,
        }.get(field_to_get)
        return handler() if handler else default

    @staticmethod
    def _traffic_railway(line: str) -> str:
        if "「" in line:
            m = re.search(r"^([^「]+)", line)
            return m.group(1).strip() if m else ""
        m = re.search(r"^([^\s]+)\s+([^\s]+)駅", line)
        if m:
            return m.group(1).strip()
        parts = line.split()
        return parts[0].strip() if parts else ""

    @staticmethod
    def _traffic_station(line: str) -> str:
        m = re.search(r"「([^」]+)」|([^\s「」]+)駅", line)
        if m:
            return (m.group(1) or m.group(2)).strip()
        return ""

    @staticmethod
    def _traffic_walk_str(line: str, default):
        m_walk = re.search(r"(?:徒歩|停歩)\s*(\d+)\s*分", line)
        return str(m_walk.group(1)) if m_walk else default

    @staticmethod
    def _traffic_walk_int(line: str) -> int:
        m_walk = re.search(r"(?:徒歩|停歩)\s*(\d+)\s*分", line)
        return int(m_walk.group(1)) if m_walk else 0

    @staticmethod
    def _traffic_bus_str(line: str, default):
        m_bus = re.search(r"バス\s*(\d+)\s*分", line)
        return str(m_bus.group(1)) if m_bus else default

    @staticmethod
    def _traffic_bus_int(line: str) -> int:
        m_bus = re.search(r"バス\s*(\d+)\s*分", line)
        return int(m_bus.group(1)) if m_bus else 0

    def _parseTransfer1(self, response, specs=None): return self._getTrafficField(response, 1, 'transfer', "")
    def _parseRailway1(self, response, specs=None): return self._getTrafficField(response, 1, 'railway', "")
    def _parseStation1(self, response, specs=None): return self._getTrafficField(response, 1, 'station', "")
    def _parseRailwayWalkMinute1Str(self, response, specs=None): return self._getTrafficField(response, 1, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute1(self, response, specs=None): return self._getTrafficField(response, 1, 'railwayWalkMinute', 0)
    def _parseBusStation1(self, response, specs=None): return self._getTrafficField(response, 1, 'busStation', "")
    def _parseBusWalkMinute1Str(self, response, specs=None): return self._getTrafficField(response, 1, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute1(self, response, specs=None): return self._getTrafficField(response, 1, 'busWalkMinute', 0)
    def _parseBusUse1(self, response, specs=None): return self._getTrafficField(response, 1, 'busUse', 0)

    def _parseTransfer2(self, response, specs=None): return self._getTrafficField(response, 2, 'transfer', "")
    def _parseRailway2(self, response, specs=None): return self._getTrafficField(response, 2, 'railway', "")
    def _parseStation2(self, response, specs=None): return self._getTrafficField(response, 2, 'station', "")
    def _parseRailwayWalkMinute2Str(self, response, specs=None): return self._getTrafficField(response, 2, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute2(self, response, specs=None): return self._getTrafficField(response, 2, 'railwayWalkMinute', 0)
    def _parseBusStation2(self, response, specs=None): return self._getTrafficField(response, 2, 'busStation', "")
    def _parseBusWalkMinute2Str(self, response, specs=None): return self._getTrafficField(response, 2, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute2(self, response, specs=None): return self._getTrafficField(response, 2, 'busWalkMinute', 0)
    def _parseBusUse2(self, response, specs=None): return self._getTrafficField(response, 2, 'busUse', 0)

    def _parseTransfer3(self, response, specs=None): return self._getTrafficField(response, 3, 'transfer', "")
    def _parseRailway3(self, response, specs=None): return self._getTrafficField(response, 3, 'railway', "")
    def _parseStation3(self, response, specs=None): return self._getTrafficField(response, 3, 'station', "")
    def _parseRailwayWalkMinute3Str(self, response, specs=None): return self._getTrafficField(response, 3, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute3(self, response, specs=None): return self._getTrafficField(response, 3, 'railwayWalkMinute', 0)
    def _parseBusStation3(self, response, specs=None): return self._getTrafficField(response, 3, 'busStation', "")
    def _parseBusWalkMinute3Str(self, response, specs=None): return self._getTrafficField(response, 3, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute3(self, response, specs=None): return self._getTrafficField(response, 3, 'busWalkMinute', 0)
    def _parseBusUse3(self, response, specs=None): return self._getTrafficField(response, 3, 'busUse', 0)

    def _parseTransfer4(self, response, specs=None): return self._getTrafficField(response, 4, 'transfer', "")
    def _parseRailway4(self, response, specs=None): return self._getTrafficField(response, 4, 'railway', "")
    def _parseStation4(self, response, specs=None): return self._getTrafficField(response, 4, 'station', "")
    def _parseRailwayWalkMinute4Str(self, response, specs=None): return self._getTrafficField(response, 4, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute4(self, response, specs=None): return self._getTrafficField(response, 4, 'railwayWalkMinute', 0)
    def _parseBusStation4(self, response, specs=None): return self._getTrafficField(response, 4, 'busStation', "")
    def _parseBusWalkMinute4Str(self, response, specs=None): return self._getTrafficField(response, 4, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute4(self, response, specs=None): return self._getTrafficField(response, 4, 'busWalkMinute', 0)
    def _parseBusUse4(self, response, specs=None): return self._getTrafficField(response, 4, 'busUse', 0)

    def _parseTransfer5(self, response, specs=None): return self._getTrafficField(response, 5, 'transfer', "")
    def _parseRailway5(self, response, specs=None): return self._getTrafficField(response, 5, 'railway', "")
    def _parseStation5(self, response, specs=None): return self._getTrafficField(response, 5, 'station', "")
    def _parseRailwayWalkMinute5Str(self, response, specs=None): return self._getTrafficField(response, 5, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute5(self, response, specs=None): return self._getTrafficField(response, 5, 'railwayWalkMinute', 0)
    def _parseBusStation5(self, response, specs=None): return self._getTrafficField(response, 5, 'busStation', "")
    def _parseBusWalkMinute5Str(self, response, specs=None): return self._getTrafficField(response, 5, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute5(self, response, specs=None): return self._getTrafficField(response, 5, 'busWalkMinute', 0)
    def _parseBusUse5(self, response, specs=None): return self._getTrafficField(response, 5, 'busUse', 0)

    def _parseSetudouDetails(self, setsudou):
        details = {
            'douroHaba': Decimal(0),
            'douroKubun': "",
            'douroMuki': "",
            'setsumen': Decimal(0)
        }
        if not setsudou: return details
        
        max_haba = -1.0
        
        for wkStr in setsudou.split(u"、"):
            douroHabaObj = re.search(r'[0-9\.]+', wkStr.split(u"ｍ")[0])
            try:
                if douroHabaObj:
                    haba = float(douroHabaObj.group())
                    if haba > max_haba:
                        max_haba = haba
                        
                        details['douroHaba'] = Decimal(str(haba))
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



class MitsuiMansionParser(MitsuiParser, MansionParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseFloor(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("階数", "") or specs.get("所在階", "") or super()._parseFloor(response, specs)

    def _parseSouKosu(self, response, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("総戸数", "")
        if val:
            m = re.search(r'(\d+)', val)
            return int(m.group(1)) if m else None
        return super()._parseSouKosu(response, specs)

    def _parseManagementFee(self, response, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("管理費", "") or specs.get("管理費等", "")
        return converter.parse_yen(val) if val and 'converter' in globals() else super()._parseManagementFee(response, specs)

    def _parseReserveFund(self, response, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("修繕積立金", "")
        return converter.parse_yen(val) if val and 'converter' in globals() else super()._parseReserveFund(response, specs)

    def _parseKenpei(self, response, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseYouseki(self, response, specs=None):
        return super()._parseYouseki(response, specs)

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
        item.kadobeya = item.saikouKadobeya
        item.senyouNiwaMenseki = self._parseSenyouNiwaMenseki(response)
        item.roofBalconyMenseki = self._parseRoofBalconyMenseki(response)
        
        # Derived metrics
        item.kanrihi_p_heibei = self._parseKanrihiPerHeibei(response)
        item.syuzenTsumitate_p_heibei = self._parseSyuzenPerHeibei(response)

        return item

    def _parseKouzou(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("建物構造", "") or specs.get("構造", "")

    def _parseKaisuStr(self, response, specs=None):
        specs = self._get_specs(response)
        val = specs.get("所在階") or specs.get("所在階 / 階建") or specs.get("階数") or specs.get("階数 / 階建", "")
        return val

    def _parseKaisu(self, response, specs=None):
        val = self._parseKaisuStr(response)
        if val:
            try:
                m = re.search(r'(\d+)', val)
                if m:
                    return int(m.group(1))
            except: pass
        return 0

    def _convert_price_string(self, price_str):
        if not price_str: return 0
        if "万" in price_str or "億" in price_str: return converter.parse_price(price_str)
        return converter.parse_yen(price_str)


    def _parseMadori(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("間取り", "")

    def _parseSenyuMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("専有面積", "")

    def _parseSenyuMenseki(self, response, specs=None):
        mensekiStr = self._parseSenyuMensekiStr(response)
        return converter.parse_menseki(mensekiStr) if mensekiStr else Decimal(0)

    def _parseKyutaishin(self, response, specs=None):
        dt = self._parseChikunengetsu(response)
        try:
            if dt and dt < datetime.date(1982, 1, 1):
                return 1
        except: pass
        return 0

    def _parseBalconyMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("バルコニー", "")
    
    def _parseBalconyMenseki(self, response, specs=None):
         mensekiStr = self._parseBalconyMensekiStr(response)
         return converter.parse_menseki(mensekiStr) if mensekiStr else None

    def _parseSaikou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("向き", "")

    def _parseSoukosuStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("総戸数", "")

    def _parseChikunengetsu(self, response, specs=None):
        chikunengetsuStr = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(chikunengetsuStr) if chikunengetsuStr else None

    def _parseSoukosu(self, response, specs=None):
        soukosuStr = self._parseSoukosuStr(response)
        if soukosuStr and soukosuStr != "-":
            try: return int(str(soukosuStr).replace(",", "").replace("戸", "").strip())
            except: pass
        return 0

    def _parseKanriKaisya(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("管理会社", "")

    def _parseKanriKeitai(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("管理形態(方式)", specs.get("管理形態", ""))

    def _parseKanriKeitaiKaisya(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("管理員の勤務形態", "")

    def _parseKanrihiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("管理費等", "")

    def _parseKanrihi(self, response, specs=None):
        kanrihiStr = self._parseKanrihiStr(response)
        if kanrihiStr and "-" not in kanrihiStr:
            try: return int(str(kanrihiStr).replace(",", "").replace("円", "").split("/")[0].strip())
            except: pass
        return 0

    def _parseSyuzenTsumitateStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("修繕積立金", "")

    def _parseSyuzenTsumitate(self, response, specs=None):
        syuzenStr = self._parseSyuzenTsumitateStr(response)
        if syuzenStr and "-" not in syuzenStr:
            try: return int(str(syuzenStr).replace(",", "").replace("円", "").split("/")[0].strip())
            except: pass
        return 0

    def _parseTyusyajo(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("駐車場", "")

    def _parseBunjoKaisya(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("分譲会社", "").replace(" (新築分譲時における売主)", "")

    def _parseSekouKaisya(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("施工会社", "")



    def _parseFloorTypeKai(self, response, specs=None):
        return self._parseKaisu(response)

    def _parseFloorTypeChijo(self, response, specs=None):
        kaisu = self._parseKaisuStr(response)
        if not kaisu or " / 地上" not in kaisu: return None
        try: return int(kaisu.split(u" / 地上")[1].split(u" 地下")[0].replace(u"階", "").replace(u"建", ""))
        except: return None

    def _parseFloorTypeChika(self, response, specs=None):
        kaisu = self._parseKaisuStr(response)
        if not kaisu or " 地下" not in kaisu: return 0
        try: return int(kaisu.split(u" 地下")[1].replace(u"階", "").replace(u"建", ""))
        except: return 0

    def _parseFloorTypeKouzou(self, response, specs=None):
        kouzou = self._parseKouzou(response, specs)
        if not kouzou:
            return ""
        if "鉄骨鉄筋コンクリート" in kouzou: return "ＳＲＣ造"
        if "鉄筋コンクリート" in kouzou: return "ＲＣ造"
        if "鉄骨" in kouzou: return "Ｓ造"
        if "木造" in kouzou: return "木造"
        # Standard fallback mappings
        if "SRC" in kouzou or "ＳＲＣ" in kouzou: return "ＳＲＣ造"
        if "RC" in kouzou or "ＲＣ" in kouzou: return "ＲＣ造"
        if "S" in kouzou or "Ｓ" in kouzou: return "Ｓ造"
        return ""

    def _parseSaikouKadobeya(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("角部屋", "")

    def _parseSenyouNiwaMenseki(self, response, specs=None):
        specs = self._get_specs(response)
        s = specs.get("専用庭", "")
        if s:
            try: return converter.parse_menseki(s)
            except: pass
        return Decimal(0)

    def _parseRoofBalconyMenseki(self, response, specs=None):
        specs = self._get_specs(response)
        s = specs.get("ルーフバルコニー", "")
        if s:
            try: return converter.parse_menseki(s)
            except: pass
        return Decimal(0)

    def _parseKanrihiPerHeibei(self, response, specs=None):
        kanrihi = self._parseKanrihi(response)
        menseki = self._parseSenyuMenseki(response)
        if kanrihi and menseki:
            raw_val = kanrihi / menseki
            return round(Decimal(str(raw_val)), 3) if raw_val < 10000000 else None
        return None

    def _parseSyuzenPerHeibei(self, response, specs=None):
        syuzen = self._parseSyuzenTsumitate(response)
        menseki = self._parseSenyuMenseki(response)
        if syuzen and menseki:
            raw_val = syuzen / menseki
            return round(Decimal(str(raw_val)), 3) if raw_val < 10000000 else None
        return None

class MitsuiTochiParser(MitsuiParser, TochiParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseMaguchi(self, response, specs=None):
        return super()._parseMaguchi(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseRights(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or super()._parseRights(response, specs)

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

        self._apply_tochi_road_eval_fields(item, response)
        return item

    def _apply_tochi_road_eval_fields(self, item, response: BeautifulSoup) -> None:
        """統一土地評価フィールドのパース ＆ 代入"""
        self._apply_maguchi_from_setsumen(item)
        self._apply_road_width_from_douro_haba(item)
        full_text = response.get_text()
        self._fallback_maguchi_from_text(item, full_text)
        self._fallback_road_width_from_text(item, full_text)
        self._apply_road_direction_and_type(item, full_text)
        self._apply_road_structure_and_okuyuki(item)

    @staticmethod
    def _apply_maguchi_from_setsumen(item) -> None:
        if item.setsumen is None:
            return
        item.maguchiStr = item.setsumen
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(item.maguchiStr))
        if m:
            item.maguchi = Decimal(m.group(1))

    @staticmethod
    def _apply_road_width_from_douro_haba(item) -> None:
        if item.douroHaba is None:
            return
        item.roadWidthStr = item.douroHaba
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(item.roadWidthStr))
        if m:
            item.roadWidth = Decimal(m.group(1))

    @staticmethod
    def _fallback_maguchi_from_text(item, full_text: str) -> None:
        if getattr(item, "maguchi", None) is not None and item.maguchi != 0:
            return
        if getattr(item, "setsudou", None):
            m_maguchi = re.search(r"(?:約)?\s*([\d\.]+)\s*[mｍ]", item.setsudou)
            if m_maguchi:
                item.maguchi = Decimal(m_maguchi.group(1))
                item.maguchiStr = f"{m_maguchi.group(1)}m"
                return
        if not full_text:
            return
        if getattr(item, "maguchi", None) is not None and item.maguchi != 0:
            return
        m_maguchi = re.search(
            r"(?:接道間口|接面|間口)[：:]?\s*(?:約)?\s*([\d\.]+)\s*[mｍ]", full_text
        )
        if m_maguchi:
            item.maguchi = Decimal(m_maguchi.group(1))
            item.maguchiStr = f"{m_maguchi.group(1)}m"

    @staticmethod
    def _fallback_road_width_from_text(item, full_text: str) -> None:
        if getattr(item, "roadWidth", None) is not None and item.roadWidth != 0:
            return
        if not full_text:
            return
        m_width = re.search(r"幅員[：:]?\s*(?:約)?\s*([\d\.]+)\s*[mｍ]", full_text) or re.search(
            r"接道[：:]?[^\n\r\t]*?(?:約)?\s*([\d\.]+)\s*[mｍ]", full_text
        )
        if m_width:
            item.roadWidth = Decimal(m_width.group(1))
            item.roadWidthStr = f"{m_width.group(1)}m"

    @staticmethod
    def _apply_road_direction_and_type(item, full_text: str) -> None:
        if not getattr(item, "roadDirection", None) and full_text:
            m_dir = re.search(r"接道[：:][^\n\r\t]*?((?:北|東|西|南)+側)", full_text)
            if m_dir:
                item.roadDirection = m_dir.group(1).replace("側", "")
        if item.douroMuki and not item.roadDirection:
            item.roadDirection = item.douroMuki
        if item.douroKubun and not item.roadType:
            item.roadType = item.douroKubun

    @staticmethod
    def _apply_road_structure_and_okuyuki(item) -> None:
        if item.setsudou:
            structure_match = re.search(
                r"(角地|二方|三方|四方|敷延|袋小路|中間地|両面道路)", str(item.setsudou)
            )
            item.roadStructure = structure_match.group(1) if structure_match else "中間地"
        else:
            item.roadStructure = "中間地"
        if item.tochiMenseki and item.maguchi and item.maguchi > 0:
            item.okuyuki = round(item.tochiMenseki / item.maguchi, 2)
            item.okuyukiStr = f"{item.okuyuki}m"

    def _parseTochiMenseki(self, response, specs=None):
        tochiMensekiStr = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(tochiMensekiStr) if tochiMensekiStr else Decimal(0)

    def _parseTochiMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseKenchikuJoken(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("建築条件", "")

    def _parseChimoku(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("地目", "")

    def _parseSetsudou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseDouroHaba(self, response, specs=None):
        return self._parseSetudouDetails(self._parseSetsudou(response))['douroHaba']

    def _parseDouroKubun(self, response, specs=None):
        return self._parseSetudouDetails(self._parseSetsudou(response))['douroKubun']

    def _parseDouroMuki(self, response, specs=None):
        return self._parseSetudouDetails(self._parseSetsudou(response))['douroMuki']

    def _parseSetsumen(self, response, specs=None):
        return self._parseSetudouDetails(self._parseSetsudou(response))['setsumen']

    def _parseKenpeiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response, specs=None):
        return self._parseKenpeiDetails(self._parseKenpeiStr(response))

    def _parseYousekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response, specs=None):
        return self._parseYousekiDetails(self._parseYousekiStr(response))

    def _parseYoutoChiiki(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseKuiki(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("都市計画", "")

    def _parseKokudoHou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("国土法", "")

    def _parseSetudouDetails(self, value):
        # Default to safe values for DB (Decimal fields need "0", CharFields can handle "")
        res = {'douroHaba': "0", 'douroKubun': "", 'douroMuki': "", 'setsumen': "0"}
        if not value: return res
        
        m_muki = re.search(u'(北|東|西|南)+', value)
        if m_muki: res['douroMuki'] = m_muki.group(0)
        
        m_haba = re.search(r'(?:幅員[：:]?)?\s*(?:約)?\s*([\d\.]+)\s*[mｍ]', value)
        if m_haba: res['douroHaba'] = m_haba.group(1)
        
        m_setsumen = re.search(r'(?:接面|間口)[：:]?\s*(?:約)?\s*([\d\.]+)\s*[mｍ]', value)
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

class MitsuiKodateParser(MitsuiParser, KodateParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseMadori(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "") or super()._parseMadori(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseRights(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or super()._parseRights(response, specs)

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

    def _parseTatemonoMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("建物面積", specs.get("延床面積", ""))

    def _parseTatemonoMenseki(self, response, specs=None):
        tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        return converter.parse_menseki(tatemonoMensekiStr) if tatemonoMensekiStr else Decimal(0)

    def _parseTochiMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseTochiMenseki(self, response, specs=None):
        tochiMensekiStr = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(tochiMensekiStr) if tochiMensekiStr else Decimal(0)

    def _parseKaisuKouzou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("建物構造", "")

    def _parseKouzouFromKaisuKouzou(self, value):
        if not value: return ""
        if "その他" in value: return "その他"
        if "-" in value: return ""
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

    def _parseKouzou(self, response, specs=None):
        value = self._parseKaisuKouzou(response)
        return self._parseKouzouFromKaisuKouzou(value)

    def _parseKaisu(self, response, specs=None):
        value = self._parseKaisuKouzou(response)
        return self._parseKaisuFromKaisuKouzou(value)

    def _parseKaisuStr(self, response, specs=None):
        value = self._parseKaisuKouzou(response)
        return self._parseKaisuStrFromKaisuKouzou(value)

    def _parseTyusyajo(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("駐車場", "")

    def _parseChimoku(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("地目", "")

    def _parseSetsudou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseDouroHaba(self, response, specs=None):
        return self._parseSetudouDetails(response)['douroHaba']

    def _parseDouroKubun(self, response, specs=None):
        return self._parseSetudouDetails(response)['douroKubun']

    def _parseDouroMuki(self, response, specs=None):
        return self._parseSetudouDetails(response)['douroMuki']

    def _parseSetsumen(self, response, specs=None):
        return self._parseSetudouDetails(response)['setsumen']

    def _parseKenpeiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response, specs=None):
        return self._parseKenpeiDetails(response)

    def _parseYousekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response, specs=None):
        return self._parseYousekiDetails(response)

    def _parseYoutoChiiki(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseKuiki(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("都市計画", "")

    def _parseSetudouDetails(self, response, specs=None):
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

    def _parseKenpeiDetails(self, response, specs=None):
        value = self._parseKenpeiStr(response)
        if not value: return 0
        m = re.search(r'(\d+)%', value)
        return int(m.group(1)) if m else 0

    def _parseYousekiDetails(self, response, specs=None):
        value = self._parseYousekiStr(response)
        if not value: return 0
        m = re.search(r'(\d+)%', value)
        return int(m.group(1)) if m else 0


class MitsuiInvestmentParser(MitsuiParser, InvestmentParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)


    property_type = 'investment'
    _is_delegating: bool = False

    
    def getRootDestUrl(self,linkUrl):
        # 投資用トップからのリンクは相対パス(prefecture/13/)なので、プレフィックスを調整
        if linkUrl.startswith('prefecture/'):
            return self.BASE_URL + "/buy/tohshi/" + linkUrl
        return self.BASE_URL + linkUrl

    def createEntity(self):
        # Abstract or default to Kodate if instantiated directly (should not happen for scraping)
        from package.models.mitsui import MitsuiInvestmentKodate
        return MitsuiInvestmentKodate()

    def _get_specs(self, soup: BeautifulSoup):
        data = super()._get_specs(soup)
        if not soup:
            return data
        # Fallback for tables where headers are td (not th).
        # Store plain text (not Tags) so Decimal/str parsers never see Tag.replace failures.
        self._merge_td_header_specs(soup, data)
        return data

    @staticmethod
    def _merge_td_header_specs(soup: BeautifulSoup, data: dict) -> None:
        for tr in soup.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) >= 2:
                MitsuiInvestmentParser._merge_cell_pairs(cells, data)

    @staticmethod
    def _merge_cell_pairs(cells, data: dict) -> None:
        for i in range(0, len(cells), 2):
            if i + 1 >= len(cells):
                continue
            key = re.sub(r"\s+", "", cells[i].get_text(strip=True))
            val = cells[i + 1].get_text(strip=True)
            if key and key not in data:
                data[key] = val
            # Also keep spaced form for legacy lookups.
            key_spaced = cells[i].get_text(" ", strip=True)
            if key_spaced and key_spaced not in data:
                data[key_spaced] = val

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # 物件種目の動的判定と委譲処理 (Dynamic Dispatch)
        if not getattr(self, '_is_delegating', False):
            specs = self._get_specs(response)
            shumoku = specs.get("物件種目", specs.get("物件種別", specs.get("種別", "")))
            is_apartment_parser = self.__class__.__name__ == "MitsuiInvestmentApartmentParser"
            
            if shumoku:
                if "アパート" in shumoku or "マンション" in shumoku or "ビル" in shumoku:
                    if not is_apartment_parser:
                        parser = MitsuiInvestmentApartmentParser()
                        parser._is_delegating = True
                        new_item = parser.createEntity()
                        new_item.pageUrl = item.pageUrl
                        return parser._parsePropertyDetailPage(new_item, response)
                else:
                    if is_apartment_parser:
                        parser = MitsuiInvestmentKodateParser()
                        parser._is_delegating = True
                        new_item = parser.createEntity()
                        new_item.pageUrl = item.pageUrl
                        return parser._parsePropertyDetailPage(new_item, response)

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

    def _parseGrossYield(self, response, specs=None):
        specs = self._get_specs(response)
        yield_val = (
            specs.get("想定利回り")
            or specs.get("表面利回り")
            or specs.get("利回り")
            or specs.get("現行利回り")
            or ""
        )
        if not yield_val:
            for k, v in specs.items():
                if "利回" in str(k) and v:
                    yield_val = v
                    break
        text = str(yield_val).replace("%", "").replace("％", "").strip()
        if not text:
            return Decimal(0)
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        if not m:
            return Decimal(0)
        try:
            return Decimal(m.group(1))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal(0)

    def _parseAnnualRent(self, response, specs=None):
        specs = self._get_specs(response)
        rent_val = self._lookup_annual_rent_value(specs)
        if not rent_val:
            return 0
        return self._convert_annual_rent(str(rent_val))

    @staticmethod
    def _lookup_annual_rent_value(specs: dict):
        rent_val = (
            specs.get("想定年収")
            or specs.get("年間想定賃料")
            or specs.get("想定賃料(年間)")
            or specs.get("想定賃料（年間）")
            or specs.get("想定賃料")
            or specs.get("想定年額")
            or ""
        )
        if rent_val:
            return rent_val
        for k, v in specs.items():
            ks = re.sub(r"\s+", "", str(k))
            if ("想定" in ks and "賃料" in ks) or ("想定" in ks and "年収" in ks):
                return v
        return ""

    @staticmethod
    def _convert_annual_rent(rent_val: str):
        if "円" in rent_val and "万" not in rent_val:
            try:
                val = rent_val.replace(",", "").replace("円", "")
                val = re.sub(r"[（\(].*?[）\)]", "", val)
                return int(val)
            except (ValueError, TypeError):
                return 0
        return converter.parse_price(rent_val)

    def _parseMonthlyRent(self, response, specs=None):
        annualRent = self._parseAnnualRent(response)
        return (annualRent // 12) if annualRent else 0

    def _parseCurrentStatus(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("現況", specs.get("賃貸状況", ""))


    def _parseKouzou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("構造", specs.get("建物構造", ""))

    def _parseChikunengetsuStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("築年月", "")

    def _parseChikunengetsu(self, response, specs=None):
        s = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(s) if s else None

    def _parseTochiMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseTochiMenseki(self, response, specs=None):
        land_area = self._parseTochiMensekiStr(response)
        if land_area:
             try: return Decimal(str(converter.parse_menseki(land_area)))
             except: pass
        return Decimal(0)

    def _parseTatemonoMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("建物面積", specs.get("専有面積", specs.get("延床面積", "")))

    def _parseTatemonoMenseki(self, response, specs=None):
        bldg_area = self._parseTatemonoMensekiStr(response)
        if bldg_area:
             try: return Decimal(str(converter.parse_menseki(bldg_area)))
             except: pass
        return Decimal(0)

    def _parseKaisuStr(self, response, specs=None):
        specs = self._get_specs(response)
        kaisu = specs.get("階数", "")
        if kaisu: return kaisu
        kouzou = self._parseKouzou(response)
        if kouzou:
            stories_match = re.search(r'(\d+)階', kouzou)
            if stories_match: return str(stories_match.group(1))
        return None

    def _parseMadori(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("間取り", "")

    def _parseYoutoChiiki(self, response, specs=None): # Renamed from _parseZoning
        specs = self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseSetsudou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseTochikenri(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("土地権利", "")

    def _parseChimoku(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("地目", "")

    def _parseKenpeiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response, specs=None):
        return self._parseKenpeiDetails(self._parseKenpeiStr(response))

    def _parseYousekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response, specs=None):
        return self._parseYousekiDetails(self._parseYousekiStr(response))


# ========== Investment Kodate & Apartment Parsers ==========
# API endpoint separation: dedicated parsers for each property type

class MitsuiInvestmentKodateParser(MitsuiInvestmentParser, KodateParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)


    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    def _parseMadori(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "") or super()._parseMadori(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("建物構造", "") or specs.get("構造", "") or super()._parseKouzou(response, specs)

    def _parseKenpei(self, response, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseYouseki(self, response, specs=None):
        return super()._parseYouseki(response, specs)

    def _parseRights(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "") or super()._parseYoutoChiiki(response, specs)

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
        if item.__class__ != self.createEntity().__class__:
            return item
        item.propertyType = "Kodate"
        return item


class MitsuiInvestmentApartmentParser(MitsuiInvestmentParser, InvestmentParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)


    def _parseGrossYield(self, response, specs=None):
        return super()._parseGrossYield(response, specs)

    def _parseAnnualRent(self, response, specs=None):
        return super()._parseAnnualRent(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None):
        return super()._parseKouzou(response, specs)

    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

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
        if item.__class__ != self.createEntity().__class__:
            return item
        item.propertyType = "Apartment"
        
        item.soukosuStr = self._parseSoukosuStr(response)
        item.soukosu = self._parseSoukosu(response)
        item.kanrihi = self._parseKanrihi(response)
        item.syuzenTsumitate = self._parseSyuzenTsumitate(response)

        return item

    def _parseKanrihi(self, response, specs=None):
        specs = self._get_specs(response)
        return converter.parse_price(specs["管理費"]) if "管理費" in specs else 0
    
    def _parseSyuzenTsumitate(self, response, specs=None):
        specs = self._get_specs(response)
        return converter.parse_price(specs["修繕積立金"]) if "修繕積立金" in specs else 0

    def _parseSoukosuStr(self, response, specs=None):
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

    def _parseSoukosu(self, response, specs=None):
        self._get_specs(response)
        soukosu = 0
        total_units = self._parseSoukosuStr(response)
        if total_units:
             match = re.search(r'(\d+)', total_units)
             if match: soukosu = int(match.group(1))

        if not soukosu:
             # Fallback logic to other fields if necessary, but keep it minimal
             pass
        
        return soukosu
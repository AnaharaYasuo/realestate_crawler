# -*- coding: utf-8 -*-
import sys

from bs4 import BeautifulSoup
from package.models.tokyu import TokyuMansion, TokyuTochi, TokyuKodate
from package.parser.investmentParser import InvestmentParser
from django.db import models
import re
from package.utils import converter
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
from package.utils.selector_loader import SelectorLoader

class TokyuParser(ParserBase):
    BASE_URL = 'https://www.livable.co.jp'
    property_type = None

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('tokyu', self.property_type)
        
    def getCharset(self):
        return "utf-8"

    def createEntity(self):
        pass

    def getRootXpath(self):
        return u''

    def getRootDestUrl(self, linkUrl):
        return self.BASE_URL + linkUrl

    async def parseRootPage(self, response):
        async for destUrl in self._parsePageCore(response, self.getRootXpath, self.getRootDestUrl):
            yield destUrl

    def getAreaXpath(self):
        return u''

    def getAreaDestUrl(self, linkUrl):
        return self.BASE_URL + linkUrl

    async def parseAreaPage(self, response):        
        async for destUrl in self._parsePageCore(response, self.getAreaXpath, self.getAreaDestUrl):
            yield destUrl

    def getPropertyListXpath(self):
        return u''

    def getPropertyListDestUrl(self, linkUrl):
        return self.BASE_URL + linkUrl

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

    def _scrape_specs(self, response: BeautifulSoup) -> dict:
        """
        Extracts key-value pairs from the property detail table.
        Returns a dictionary where keys are the header text (th/dt)
        and values are a dict containing 'value' (text) and 'element' (dd tag).
        """
        specs = {}
        table_config = self.selectors.get('table', {})
        table_selector = table_config.get('selector', 'div.m-status-table__wrapper, #propertySummarySection dl, dl')
        row_selector = table_config.get('row_selector', 'div, dl')
        header_selector = table_config.get('header', 'dt')
        value_selector = table_config.get('value', 'dd')

        wrappers = response.select(table_selector)
        if not wrappers:
            return {}

        for target_wrapper in wrappers:
            rows = target_wrapper.select(row_selector)
            
            # Case 1: dt/dd are direct children of dl
            if target_wrapper.name == 'dl' and not rows:
                 dts = target_wrapper.find_all('dt', recursive=False)
                 for dt in dts:
                     dd = dt.find_next_sibling('dd')
                     if dd:
                         title = dt.get_text(strip=True).rstrip("：").rstrip(":")
                         if title and title not in specs:
                             specs[title] = {
                                 'value': dd.get_text(strip=True),
                                 'element': dd,
                                 'row_element': target_wrapper
                             }

            # Case 2: rows (div/dl) contain dt/dd
            for tr in rows:
                dds = tr.select(value_selector)
                dts = tr.select(header_selector)
                for j, th in enumerate(dts):
                    thTitle = th.get_text(strip=True) if len(th.contents) > 0 else "Unknown"
                    if not thTitle: thTitle = "Unknown"
                    thTitle = thTitle.rstrip("：").rstrip(":")
                    
                    if len(dds) > j:
                        if thTitle not in specs or specs[thTitle]['value'] == "":
                            specs[thTitle] = {
                                'value': dds[j].get_text(strip=True),
                                'element': dds[j],
                                'row_element': tr
                            }
        return specs

    def _clean_text(self, text):
        if text:
            return text.strip()
        return ""

    async def parsePropertyListPage(self, response):
        async for destUrl in self._parsePageCore(response, self.getPropertyListXpath, self.getPropertyListDestUrl):
            yield destUrl

    def _parsePropertyDetailPage(self, item, response):
        # Fallback to base implementation if no Next.js data
        item = super()._parsePropertyDetailPage(item, response)
        
        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        
        item.address = self._parseAddress(response)
        item.address1 = self._parseAddress1(response)
        item.address2 = self._parseAddress2(response)
        item.address3 = self._parseAddress3(response)
        item.addressKyoto = ""
        
        item.transport1 = self._parseTransport1(response)
        
        item.hikiwatashi = self._parseHikiwatashi(response)
        item.genkyo = self._parseGenkyo(response)
        item.tochikenri = self._parseTochikenri(response)
        item.sonotaHiyouStr = self._parseSonotaHiyouStr(response)
        item.torihiki = self._parseTorihiki(response)
        item.biko = self._parseBiko(response)
        
        return item

    def _parsePropertyName(self, response: BeautifulSoup) -> str:
        try:
            selector = self.selectors.get('title', 'h1')
            el = response.select_one(selector)
            if not el and selector != "title":
                el = response.select_one("title")
            if el:
                text = self._clean_text(el.get_text())
                if "｜" in text:
                    text = text.split("｜")[0].strip()
                return text
            return ""
        except Exception:
            raise ReadPropertyNameException()

        item.hikiwatashi = self._parseHikiwatashi(response)
        item.genkyo = self._parseGenkyo(response)
        item.tochikenri = self._parseTochikenri(response)
        item.sonotaHiyouStr = self._parseSonotaHiyouStr(response)
        item.torihiki = self._parseTorihiki(response)
        item.biko = self._parseBiko(response)
        
        return item

    # --- Common Extraction Methods ---
    def _parsePriceStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = self.selectors.get('price_key', u"価格")
        if key in specs:
             return specs[key]['value']
        return ""

    def _parsePrice(self, response: BeautifulSoup) -> int:
        return converter.parse_price(self._parsePriceStr(response))

    def _parseAddress(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = self.selectors.get('address_key', u"所在地")
        if key in specs:
             val = specs[key]['value']
             if "Googleマップ" in val:
                 val = val.split("Googleマップ")[0].strip()
             return val
        return ""

    def _parseAddress1(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = self.selectors.get('address_key', u"所在地")
        if key in specs:
            links = specs[key]['element'].select('a')
            if len(links) >= 1: return links[0].text
        return ""

    def _parseAddress2(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = self.selectors.get('address_key', u"所在地")
        if key in specs:
            links = specs[key]['element'].select('a')
            if len(links) >= 2: return links[1].text
        return ""

    def _parseAddress3(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = self.selectors.get('address_key', u"所在地")
        if key in specs:
            links = specs[key]['element'].select('a')
            if len(links) >= 3: return links[2].text
        return ""

    def _parseTransport1(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = self.selectors.get('transport_key', u"交通")
        return specs[key]['value'] if key in specs else ""

    def _parseHikiwatashi(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = self.selectors.get('hikiwatashi_key', u"引渡時")
        if key not in specs: key = u"引渡"
        if key not in specs: key = u"引渡時期"
        return specs[key]['value'] if key in specs else ""

    def _parseGenkyo(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"現況"
        if key not in specs: key = u"建物現況"
        return specs[key]['value'] if key in specs else ""

    def _parseTochikenri(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"土地権利"
        return specs[key]['value'] if key in specs else ""

    def _parseSonotaHiyouStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"その他費用"
        return specs[key]['value'] if key in specs else ""

    def _parseTorihiki(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"取引態様"
        return specs[key]['value'] if key in specs else ""

    def _parseBiko(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"備考"
        return specs[key]['value'] if key in specs else ""

    def _parseMadori(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"間取り"
        return specs[key]['value'] if key in specs else ""

    def _parseKouzou(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"建物構造"
        return specs[key]['value'] if key in specs else ""

    def _parseChikunengetsuStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"築年月"
        return specs[key]['value'] if key in specs else ""

    def _parseChikunengetsu(self, response: BeautifulSoup):
        val = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(val)

    def _parseTochiMensekiStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"土地面積"
        return specs[key]['value'] if key in specs else ""

    def _parseTochiMenseki(self, response: BeautifulSoup) -> Decimal:
        val = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(val)

    def _parseTatemonoMensekiStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"建物面積"
        if key not in specs: key = u"延床面積"
        return specs[key]['value'] if key in specs else ""

    def _parseTatemonoMenseki(self, response: BeautifulSoup) -> Decimal:
        val = self._parseTatemonoMensekiStr(response)
        return converter.parse_menseki(val)

    def _parseYoutoChiiki(self, response: BeautifulSoup) -> str:
        val = self._parseChiikiChiku(response)
        if "/" in val:
            return val.split("/")[-1].strip()
        return val

    def _parseKenpeiStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"建ぺい率"
        return specs[key]['value'] if key in specs else ""

    def _parseYousekiStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"容積率"
        return specs[key]['value'] if key in specs else ""

    def _parseKenpei(self, response: BeautifulSoup) -> int:
        val = self._parseKenpeiStr(response)
        match = re.search(r'(\d+)', val)
        return int(match.group(1)) if match else 0

    def _parseYouseki(self, response: BeautifulSoup) -> int:
        val = self._parseYousekiStr(response)
        match = re.search(r'(\d+)', val)
        return int(match.group(1)) if match else 0

    def _parseKenpeiYousekiStr(self, response: BeautifulSoup) -> str:
        kenpei = self._parseKenpeiStr(response)
        youseki = self._parseYousekiStr(response)
        res = []
        if kenpei: res.append(f"建ぺい率:{kenpei}")
        if youseki: res.append(f"容積率:{youseki}")
        return " ".join(res)

    def _parseSetsudou(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"接道状況"
        if key in specs: return specs[key]['value']
        key = u"接道"
        return specs[key]['value'] if key in specs else "-"

    def _parseDouro(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"接道方向／幅員"
        return specs[key]['value'] if key in specs else ""

    def _parseDouroMuki(self, response: BeautifulSoup) -> str:
        val = self._parseDouro(response)
        match = re.search(u"(北|南|東|西)+", val)
        return match.group(0) if match else "-"

    def _parseDouroHaba(self, response: BeautifulSoup) -> Decimal:
        val = self._parseDouro(response)
        match = re.search(r'(\d+(\.\d+)?)\s*m', val)
        if match: return Decimal(match.group(1))
        return None

    def _parseDouroKubun(self, response: BeautifulSoup) -> str:
        val = self._parseDouro(response)
        if u"公道" in val: return u"公道"
        if u"私道" in val: return u"私道"
        return "-"

    def _parseSetsumen(self, response: BeautifulSoup) -> Decimal:
        # If setsumen not found in label, return 0 if mandatory
        return Decimal(0)

    def _parseChimokuChisei(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"地目（現況）"
        if key not in specs: key = u"地目"
        return specs[key]['value'] if key in specs else ""

    def _parseChimoku(self, response: BeautifulSoup) -> str:
        val = self._parseChimokuChisei(response)
        return val.split("（")[0].strip() if "（" in val else val

    def _parseChisei(self, response: BeautifulSoup) -> str:
        val = self._parseChimokuChisei(response)
        if "（" in val:
            match = re.search(u"（(.*?)）", val)
            if match: return match.group(1)
        return "-"

    def _parseChiikiChiku(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"用途地域等"
        return specs[key]['value'] if key in specs else ""

    def _parseKuiki(self, response: BeautifulSoup) -> str:
        val = self._parseChiikiChiku(response)
        if "/" in val:
            return val.split("/")[0].strip()
        # Fallback to separate label
        specs = self._scrape_specs(response)
        key = u"都市計画"
        return specs[key]['value'] if key in specs else ""

    def _parseBoukaChiiki(self, response: BeautifulSoup) -> str:
        # Check in specs, or remarks
        val = self._parseBiko(response)
        if u"防火" in val: return u"防火地域級等あり" 
        return "-"

    def _parseSaikenchiku(self, response: BeautifulSoup) -> str:
        val = self._parseBiko(response)
        if u"再建築不可" in val: return u"不可"
        return u"可"

    def _parseSonotaChiiki(self, response: BeautifulSoup) -> str:
        return "-"

    def _parseKenchikuJoken(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"建築条件"
        return specs[key]['value'] if key in specs else "-"

    def _parseKokudoHou(self, response: BeautifulSoup) -> str:
        val = self._parseBiko(response)
        if u"国土法" in val: return u"届出要"
        return u"不要"

    def _parseSaikou(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"向き"
        if key not in specs: key = u"開口向き"
        if key in specs: return specs[key]['value']
        # Fallback to douro
        return self._parseDouroMuki(response)

    def _parseParking(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"駐車場"
        return specs[key]['value'] if key in specs else ""

    def _parseShidoMensekiStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"私道面積"
        return specs[key]['value'] if key in specs else "0"

    def _parseShidoMenseki(self, response: BeautifulSoup) -> Decimal:
        return converter.parse_menseki(self._parseShidoMensekiStr(response)) or 0

    def _parseKaisuStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"建物構造"
        return specs[key]['value'] if key in specs else ""

class TokyuMansionParser(TokyuParser):
    property_type = 'mansion'

    def getRootXpath(self): return self.selectors.get('root_xpath')
    def getAreaXpath(self): return self.selectors.get('area_xpath')
    def getPropertyListXpath(self): return self.selectors.get('property_links_xpath')

    def createEntity(self):
        return TokyuMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item: TokyuMansion = super()._parsePropertyDetailPage(item, response)
        
        item.madori = self._parseMadori(response)
        item.senyuMensekiStr = self._parseSenyuMensekiStr(response)
        item.senyuMenseki = self._parseSenyuMenseki(response)
        
        item.kaisu = self._parseKaisu(response)
        item.kaisuStr = self._parseKaisuStr(response)
        item.tatemonoKaisu = self._parseTatemonoKaisu(response)
        item.kouzou = self._parseKouzou(response)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        
        item.balconyMensekiStr = self._parseBalconyMensekiStr(response)
        item.balconyMenseki = self._parseBalconyMenseki(response)
        item.saikou = self._parseSaikou(response)
        item.soukosu = self._parseSoukosu(response)
        
        item.kanriKaisya = self._parseKanriKaisya(response)
        item.kanriKeitai = self._parseKanriKeitai(response)
        item.kanrihiStr = self._parseKanrihiStr(response)
        item.kanrihi = self._parseKanrihi(response)
        item.syuzenTsumitateStr = self._parseSyuzenTsumitateStr(response)
        item.syuzenTsumitate = self._parseSyuzenTsumitate(response)
        
        item.tyusyajo = self._parseParking(response)
        item.bunjoKaisya = self._parseBunjoKaisya(response)
        item.sekouKaisya = self._parseSekouKaisya(response)

        self._calculateDerivedFields(item)
        return item

    def _parseSenyuMensekiStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"専有面積"
        return specs[key]['value'] if key in specs else ""

    def _parseSenyuMenseki(self, response: BeautifulSoup) -> Decimal:
        return converter.parse_menseki(self._parseSenyuMensekiStr(response))

    def _parseKaisu(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"所在階"
        return specs[key]['value'] if key in specs else ""

    def _parseTatemonoKaisu(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"建物構造"
        val = specs[key]['value'] if key in specs else ""
        match = re.search(r'地上(\d+)階', val)
        return match.group(0) if match else val

    def _parseBalconyMensekiStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"バルコニー面積"
        return specs[key]['value'] if key in specs else ""

    def _parseBalconyMenseki(self, response: BeautifulSoup) -> Decimal:
        return converter.parse_menseki(self._parseBalconyMensekiStr(response))

    def _parseSoukosu(self, response: BeautifulSoup) -> int:
        specs = self._scrape_specs(response)
        key = u"総戸数"
        if key in specs:
            match = re.search(r'(\d+)', specs[key]['value'])
            if match: return int(match.group(1))
        return None

    def _parseKanriKaisya(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"管理会社"
        return specs[key]['value'] if key in specs else ""

    def _parseKanriKeitai(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"管理員の勤務形態"
        if key not in specs: key = u"管理形態"
        return specs[key]['value'] if key in specs else ""

    def _parseKanrihiStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"管理費"
        return specs[key]['value'] if key in specs else ""

    def _parseKanrihi(self, response: BeautifulSoup) -> int:
        return converter.parse_price(self._parseKanrihiStr(response))

    def _parseSyuzenTsumitateStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"修繕積立金"
        return specs[key]['value'] if key in specs else ""

    def _parseSyuzenTsumitate(self, response: BeautifulSoup) -> int:
        return converter.parse_price(self._parseSyuzenTsumitateStr(response))

    def _parseBunjoKaisya(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"分譲会社"
        if key not in specs: key = u"分譲主"
        return specs[key]['value'] if key in specs else ""

    def _parseSekouKaisya(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        key = u"施工会社"
        return specs[key]['value'] if key in specs else ""

    def _calculateDerivedFields(self, item):
        item.floorType_kouzou = ""
        if "鉄筋コンクリート" in item.kouzou: item.floorType_kouzou = "ＲＣ造"
        elif "鉄骨鉄筋" in item.kouzou: item.floorType_kouzou = "ＳＲＣ造"
        elif "鉄骨" in item.kouzou: item.floorType_kouzou = "Ｓ造"
        elif "木" in item.kouzou: item.floorType_kouzou = "木造"
        item.kyutaishin = 0
        if item.chikunengetsu and item.chikunengetsu < datetime.date(1982, 1, 1):
            item.kyutaishin = 1
        if item.senyuMenseki and item.senyuMenseki > 0:
            item.kanrihi_p_heibei = (item.kanrihi or 0) / item.senyuMenseki
            item.syuzenTsumitate_p_heibei = (item.syuzenTsumitate or 0) / item.senyuMenseki

class TokyuTochiParser(TokyuParser):
    property_type = 'tochi'

    def getRootXpath(self): return self.selectors.get('root_xpath')
    def getAreaXpath(self): return self.selectors.get('area_xpath')
    def getPropertyListXpath(self): return self.selectors.get('property_links_xpath')

    def createEntity(self):
        return TokyuTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item: TokyuTochi = super()._parsePropertyDetailPage(item, response)
        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.chimokuChisei = self._parseChimokuChisei(response)
        item.chimoku = self._parseChimoku(response)
        item.chisei = self._parseChisei(response)
        item.setsudou = self._parseSetsudou(response)
        item.douro = self._parseDouro(response)
        item.douroMuki = self._parseDouroMuki(response)
        item.douroHaba = self._parseDouroHaba(response)
        item.douroKubun = self._parseDouroKubun(response)
        item.setsumen = self._parseSetsumen(response)
        item.kenpei = self._parseKenpei(response)
        item.youseki = self._parseYouseki(response)
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.yousekiStr = self._parseYousekiStr(response)
        item.kenpeiYousekiStr = self._parseKenpeiYousekiStr(response)
        item.chiikiChiku = self._parseChiikiChiku(response)
        item.kuiki = self._parseKuiki(response)
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.boukaChiiki = self._parseBoukaChiiki(response)
        item.saikenchiku = self._parseSaikenchiku(response)
        item.sonotaChiiki = self._parseSonotaChiiki(response)
        item.kenchikuJoken = self._parseKenchikuJoken(response)
        item.kokudoHou = self._parseKokudoHou(response)
        return item

class TokyuKodateParser(TokyuParser):
    property_type = 'kodate'

    def getRootXpath(self): return self.selectors.get('root_xpath')
    def getAreaXpath(self): return self.selectors.get('area_xpath')
    def getPropertyListXpath(self): return self.selectors.get('property_links_xpath')

    def createEntity(self):
        return TokyuKodate()

class TokyuKodateParser(TokyuParser):
    property_type = 'kodate'

    def getRootXpath(self): return self.selectors.get('root_xpath')
    def getAreaXpath(self): return self.selectors.get('area_xpath')
    def getPropertyListXpath(self): return self.selectors.get('property_links_xpath')

    def createEntity(self):
        return TokyuKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item: TokyuKodate = super()._parsePropertyDetailPage(item, response)
        item.madori = self._parseMadori(response)
        item.tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        item.tatemonoMenseki = self._parseTatemonoMenseki(response)
        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.shidoMensekiStr = self._parseShidoMensekiStr(response)
        item.shidoMenseki = self._parseShidoMenseki(response)
        item.kouzou = self._parseKouzou(response)
        item.kaisuStr = self._parseKaisuStr(response)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.setsudou = self._parseSetsudou(response)
        item.setsumen = self._parseSetsumen_Str(response)
        item.douroHaba = self._parseDouroHaba_Str(response)
        item.saikou = self._parseSaikou(response)
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.yousekiStr = self._parseYousekiStr(response)
        item.kenpeiYousekiStr = self._parseKenpeiYousekiStr(response)
        item.kenpei = Decimal(self._parseKenpei(response))
        item.youseki = Decimal(self._parseYouseki(response))
        item.kuiki = self._parseKuiki(response)
        return item

    def _parseSetsumen_Str(self, response: BeautifulSoup) -> str:
        return self._parseDouro(response)
    def _parseDouroHaba_Str(self, response: BeautifulSoup) -> str:
        return self._parseDouro(response)

class TokyuInvestmentParser(InvestmentParser):
    property_type = 'investment'
    BASE_URL = 'https://www.livable.co.jp'

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('tokyu', self.property_type)

    async def parsePropertyListPage(self, response):
        # Try Next.js data first
        script = response.find('script', id='__NEXT_DATA__')
        if script:
            try:
                import json
                data = json.loads(script.string)
                pageProps = data.get('props', {}).get('pageProps', {})
                propertyList = pageProps.get('propertyList', [])
                if propertyList:
                    for item in propertyList:
                        detailUrl = item.get('detailUrl')
                        if detailUrl:
                            yield self.BASE_URL + detailUrl
                    return
            except Exception as e:
                logging.error(f"Error parsing __NEXT_DATA__: {e}")

        # Fallback to selectors
        selector = self.selectors.get('property_links')
        for link in response.select(selector):
            href = link.get('href')
            if href:
                yield self.BASE_URL + href

    async def parsePropertyListPage(self, response):
        # Try Next.js data first
        script = response.find('script', id='__NEXT_DATA__')
        if script:
            try:
                import json
                data = json.loads(script.string)
                pageProps = data.get('props', {}).get('pageProps', {})
                propertyList = pageProps.get('propertyList', [])
                if propertyList:
                    for item in propertyList:
                        detailUrl = item.get('detailUrl')
                        if detailUrl:
                            yield self.BASE_URL + detailUrl
                    return
            except Exception as e:
                logging.error(f"Error parsing __NEXT_DATA__: {e}")

        # Fallback to selectors
        selector = self.selectors.get('property_links')
        for link in response.select(selector):
            href = link.get('href')
            if href:
                yield self.BASE_URL + href

    def _getNextJsData(self, response):
        if hasattr(response, '_next_data_json'):
            return response._next_data_json
        
        script = response.find('script', id='__NEXT_DATA__')
        if script:
            try:
                import json
                data = json.loads(script.string)
                response._next_data_json = data
                return data
            except:
                pass
        return None

    def _get_item_data(self, response, title):
        data = self._getNextJsData(response)
        if not data: return None
        pageProps = data.get('props', {}).get('pageProps', {})
        summary = pageProps.get('summary', {})
        tableItems = summary.get('tableItems', [])
        for t_item in tableItems:
            if t_item.get('title') == title:
                return t_item.get('data')
        return None

    def _get_text_value(self, data):
        if not data: return ""
        if isinstance(data, dict):
            if 'text' in data: return data['text']
            if 'html' in data:
                from bs4 import BeautifulSoup 
                return BeautifulSoup(data['html'], "html.parser").get_text()
        return str(data)

    def _parsePropertyName(self, response):
        data = self._getNextJsData(response)
        if not data: return "" # Original implementation in InvestmentParser is not visible but we can fallback or raise
        # Actually InvestmentParser doesn't have _parsePropertyName?
        # Let's check ParserBase?
        
        pageProps = data.get('props', {}).get('pageProps', {})
        viewingProperty = pageProps.get('viewingProperty', {})
        name = viewingProperty.get('propertyName')
        if not name:
            name = self._get_text_value(self._get_item_data(response, '所在地'))
        return name

    def _parsePrice(self, response):
        data = self._getNextJsData(response)
        if not data: return None
        
        pageProps = data.get('props', {}).get('pageProps', {})
        viewingProperty = pageProps.get('viewingProperty', {})
        price = viewingProperty.get('priceModel', {}).get('price')
        
        if price is None:
            price_data = self._get_item_data(response, '価格')
            if price_data and 'price' in price_data:
                 price = price_data['price'].get('price')
        return price

    def _parseYield(self, response):
        yield_val_str = self._get_text_value(self._get_item_data(response, '予定利回り'))
        if yield_val_str:
            import re
            match = re.search(r'([\d\.]+)', yield_val_str)
            if match:
                return float(match.group(1))
        return None

    def _parseAddress(self, response):
        data = self._getNextJsData(response)
        if not data: return ""
        
        pageProps = data.get('props', {}).get('pageProps', {})
        viewingProperty = pageProps.get('viewingProperty', {})
        
        if viewingProperty.get('address'):
            return viewingProperty.get('address')
        
        addr_data = self._get_item_data(response, '所在地')
        if addr_data and 'links' in addr_data:
            return "".join([l.get('text', '') for l in addr_data['links']])
        return ""

    def _parseAccess(self, response):
        data = self._getNextJsData(response)
        if not data: return ""
        
        pageProps = data.get('props', {}).get('pageProps', {})
        viewingProperty = pageProps.get('viewingProperty', {})
        
        if viewingProperty.get('access'):
            return viewingProperty.get('access')
        
        access_data = self._get_item_data(response, '交通')
        if access_data and 'links' in access_data:
            lines = []
            for link_group in access_data['links']:
                line_str = "".join([l.get('text', '') for l in link_group])
                lines.append(line_str)
            return " ".join(lines)
        return ""

    def _parseMonthlyRent(self, response):
        annual_income_str = self._get_text_value(self._get_item_data(response, '年間予定賃料収入'))
        if annual_income_str:
            import re
            # Normalize full-width
            width_kanji = re.sub(r'[０-９]', lambda x: chr(ord(x.group(0)) - 0xFEE0), annual_income_str)
            match = re.search(r'([\d,]+)', width_kanji)
            if match:
                annual_income = int(match.group(1).replace(',', ''))
                if '万' in annual_income_str:
                    annual_income *= 10000
                return int(annual_income / 12)
        return None

    def _parseMenseki(self, response, key):
        val_str = self._get_text_value(self._get_item_data(response, key))
        import re
        if val_str:
             match = re.search(r'([\d\.]+)', val_str)
             if match: return Decimal(match.group(1))
        return None

    def _parseDetailString(self, response, key):
        return self._get_text_value(self._get_item_data(response, key))

    def _parseKenpeiYouseki(self, response, key):
        val_str = self._get_text_value(self._get_item_data(response, key))
        import re
        if val_str:
             match = re.search(r'(\d+)', val_str)
             if match: return int(match.group(1))
        return None

    def _parsePropertyDetailPage(self, item, response):
        # Override to support Next.js JSON data extraction
        # Must be sync
        
        next_data = self._getNextJsData(response)
        if not next_data:
            # Fallback to base implementation if no Next.js data
            return super()._parsePropertyDetailPage(item, response)

        item.propertyName = self._parsePropertyName(response)
        item.price = self._parsePrice(response)
        item.yield_rate = self._parseYield(response)
        item.address = self._parseAddress(response)
        item.transport1 = self._parseAccess(response)
        item.monthlyRent = self._parseMonthlyRent(response)
        
        if hasattr(item, 'tochiMensekiStr'):
            item.tochiMensekiStr = self._parseDetailString(response, '土地面積')
        if hasattr(item, 'tochiMenseki'):
            item.tochiMenseki = self._parseMenseki(response, '土地面積')
        
        if hasattr(item, 'tatemonoMensekiStr'):
            item.tatemonoMensekiStr = self._parseDetailString(response, '建物面積')
        if hasattr(item, 'tatemonoMenseki'):
            item.tatemonoMenseki = self._parseMenseki(response, '建物面積')
        
        if hasattr(item, 'madori'):
            item.madori = self._parseDetailString(response, '間取り')
        if hasattr(item, 'soukosuStr'):
            item.soukosuStr = self._parseDetailString(response, '総戸数')
        if hasattr(item, 'chikunengetsuStr'):
            item.chikunengetsuStr = self._parseDetailString(response, '築年月')
        
        if hasattr(item, 'kenpei'):
            item.kenpei = self._parseKenpeiYouseki(response, '建ぺい率')
        if hasattr(item, 'youseki'):
            item.youseki = self._parseKenpeiYouseki(response, '容積率')
        
        if hasattr(item, 'youtoChiiki'):
            item.youtoChiiki = self._parseDetailString(response, '用途地域等')
        
        setsudou_val = self._parseDetailString(response, '接道状況') + " " + self._parseDetailString(response, '接道方向／幅員')
        if hasattr(item, 'setsudou'):
            item.setsudou = setsudou_val
        elif hasattr(item, 'startRoad'):
            item.startRoad = setsudou_val
            
        if hasattr(item, 'chimoku'):
            item.chimoku = self._parseDetailString(response, '地目')
        if hasattr(item, 'genkyo'):
            item.genkyo = self._parseDetailString(response, '現況')
        if hasattr(item, 'hikiwatashi'):
            item.hikiwatashi = self._parseDetailString(response, '引渡可能年月')
        if hasattr(item, 'torihiki'):
            item.torihiki = self._parseDetailString(response, '取引態様')
        if hasattr(item, 'biko'):
            item.biko = self._parseDetailString(response, '備考')
        if hasattr(item, 'tochikenri'):
            item.tochikenri = self._parseDetailString(response, '土地権利')
        if hasattr(item, 'kanriKeitai'):
            item.kanriKeitai = self._parseDetailString(response, '管理形態')

        return item

    async def parseNextPage(self, response):
        next_page_text = self.selectors.get('next_page', u"次へ")
        next_link = response.find('a', string=re.compile(next_page_text))
        if next_link and next_link.get('href'):
            return self.BASE_URL + next_link.get('href')
        return ""

    def getCharset(self): return "utf-8"

    def _parsePropertyDetailPage(self, item: models.Model, response: BeautifulSoup) -> models.Model:
        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)
        item.traffic = self._parseTraffic(response)
        item.kouzou = self._parseStructure(response)
        item.chikunengetsuStr = self._parseYearBuilt(response)
        item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)
        item.tochiMensekiStr = self._parseLandArea(response)
        item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr) or 0
        item.tatemonoMensekiStr = self._parseBuildingArea(response)
        item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr) or 0
        item.grossYield = self._parseGrossYield(response)
        if hasattr(item, 'annualRent'): item.annualRent = self._parseAnnualRent(response) or 0
        if hasattr(item, 'currentStatus'): item.currentStatus = self._parseCurrentStatus(response)
        if hasattr(item, 'soukosu'): item.soukosu = self._parseSoukosu(response)
        if hasattr(item, 'kenpeiStr'): item.kenpeiStr = self._parseKenpeiStr(response)
        if hasattr(item, 'yousekiStr'): item.yousekiStr = self._parseYousekiStr(response)
        if hasattr(item, 'youtoChiiki'): item.youtoChiiki = self._parseYoutoChiiki(response)
        return item

    def _scrape_specs(self, response: BeautifulSoup) -> dict:
        specs = {}
        for dl in response.select('#propertySummarySection dl, div.m-status-table__wrapper, dl'):
            for dt in dl.find_all('dt'):
                dd = dt.find_next_sibling('dd')
                if dd: specs[dt.get_text(strip=True).rstrip("：")] = dd.get_text(strip=True)
        return specs

    def _parsePropertyName(self, response: BeautifulSoup) -> str:
        el = response.select_one(self.selectors.get('title', 'h1'))
        if el: return el.get_text().strip().split("｜")[0].strip()
        return ""

    def _parsePriceStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        return specs.get(u"価格", "")

    def _parsePrice(self, response: BeautifulSoup) -> int:
        return converter.parse_price(self._parsePriceStr(response))

    def _parseAddress(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        return specs.get(u"所在地", "")

    def _parseTraffic(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        return specs.get(u"交通", "")

    def _parseStructure(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        return specs.get(u"建物構造", "")

    def _parseYearBuilt(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        return specs.get(u"築年月", "")

    def _parseLandArea(self, response: BeautifulSoup):
        specs = self._scrape_specs(response)
        return specs.get(u"土地面積", "")

    def _parseBuildingArea(self, response: BeautifulSoup):
        specs = self._scrape_specs(response)
        return specs.get(u"建物面積", "") or specs.get(u"延床面積", "") or specs.get(u"専有面積", "")

    def _parseGrossYield(self, response: BeautifulSoup) -> Decimal:
        specs = self._scrape_specs(response)
        val_str = specs.get(u"利回り", "") or specs.get(u"表面利回り", "")
        match = re.search(r'(\d+(\.\d+)?)', val_str)
        return Decimal(match.group(1)) if match else 0

    def _parseAnnualRent(self, response: BeautifulSoup) -> int:
        specs = self._scrape_specs(response)
        return converter.parse_price(specs.get(u"年間予定賃料収入", ""))

    def _parseCurrentStatus(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        return specs.get(u"現況", "")

    def _parseSoukosu(self, response: BeautifulSoup) -> int:
        specs = self._scrape_specs(response)
        return converter.parse_numeric(specs.get(u"総戸数", ""))

    def _parseKenpeiStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        return specs.get(u"建ぺい率", "")

    def _parseYousekiStr(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        return specs.get(u"容積率", "")

    def _parseYoutoChiiki(self, response: BeautifulSoup) -> str:
        specs = self._scrape_specs(response)
        return specs.get(u"用途地域", "")

class TokyuInvestmentApartmentParser(TokyuInvestmentParser):
    def createEntity(self):
        from package.models.tokyu import TokyuInvestmentApartment
        return TokyuInvestmentApartment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        item.propertyType = "Apartment"
        return item


class TokyuInvestmentKodateParser(TokyuInvestmentParser):
    def createEntity(self):
        from package.models.tokyu import TokyuInvestmentKodate
        return TokyuInvestmentKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        item.propertyType = "Kodate"
        
        # shidoMenseki
        item.shidoMensekiStr = self._parseDetailString(response, '私道面積')
        item.shidoMenseki = self._parseMenseki(response, '私道面積') or 0
        
        return item

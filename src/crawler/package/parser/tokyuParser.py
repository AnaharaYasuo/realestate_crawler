# -*- coding: utf-8 -*-
import datetime
from decimal import Decimal
import importlib
import json
import logging
import re
import sys

from bs4 import BeautifulSoup
from package.models.tokyu import TokyuKodate, TokyuMansion, TokyuTochi
from package.parser.baseParser import (
    InvestmentParserBase,
    KodateParserBase,
    ListingEndedException,
    MansionParserBase,
    ParserBase,
    TochiParserBase,
)
from package.parser.investmentParser import InvestmentParser
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

importlib.reload(sys)

logger = logging.getLogger(__name__)

def check_tokyu_listing_ended(response, page_url: str = "unknown"):
    title_text = response.title.get_text().strip() if response.title else ""
    body_text = response.body.get_text() if response.body else ""
    h1_el = response.find("h1")
    h1_text = h1_el.get_text().strip() if h1_el else ""
    all_text = f"{title_text} {h1_text} {body_text}"
    if any(msg in all_text for msg in ["掲載終了しました", "掲載を終了いたしました", "掲載を終了しました", "お探しの物件は見つかりませんでした", "指定された物件は掲載を終了", "掲載終了物件"]):
        raise ListingEndedException(f"Tokyu listing ended: {page_url}")


class TokyuParser(ParserBase):

    def _get_spec_val(self, specs, key, default=""):
        if not specs or key not in specs:
            return default
        val = specs[key]
        return val.get('value', default) if isinstance(val, dict) else str(val)


    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    BASE_URL = 'https://www.livable.co.jp'
    property_type = ""

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('tokyu', self.property_type)
        
    def getCharset(self):
        return "utf-8"

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        return super()._parseTransport1(response, specs)

    def createEntity(self):
        pass

    def getRootXpath(self):
        return ''

    def getRootDestUrl(self, linkUrl):
        return self.BASE_URL + linkUrl

    async def parseRootPage(self, response):
        async for destUrl in self._parsePageCore(response, self.getRootXpath, self.getRootDestUrl):
            yield destUrl

    def getAreaXpath(self):
        return ''

    def getAreaDestUrl(self, linkUrl):
        return self.BASE_URL + linkUrl

    async def parseAreaPage(self, response):        
        async for destUrl in self._parsePageCore(response, self.getAreaXpath, self.getAreaDestUrl):
            yield destUrl

    def getPropertyListXpath(self):
        return ''

    def getPropertyListDestUrl(self, linkUrl):
        return self.BASE_URL + linkUrl

    async def parsePropertyListPage(self, response):
        async for destUrl in self._parsePageCore(response, self.getPropertyListXpath, self.getPropertyListDestUrl):
            yield destUrl

    async def getPropertyListNextPageUrl(self, response):
        logger.info("getPropertyListNextPageUrl")
        try:
            if hasattr(response, 'select_one'):
                next_css = self.selectors.get('next_page_css', 'a.pagination-next, a.is-next, a[rel="next"]')
                next_el = response.select_one(next_css)
                if not next_el:
                    next_el = response.find('a', string=re.compile("次へ|次"))
                if next_el and next_el.get('href'):
                    href = next_el.get('href')
                    return href if href.startswith('http') else self.BASE_URL + href
        except Exception as e:
            logger.warning("getPropertyListNextPageUrl exception: %s", e)
        return ""

    def _scrape_dl_direct_children(self, target_wrapper, specs: dict) -> None:
        dts = target_wrapper.find_all('dt', recursive=False)
        for dt in dts:
            dd = dt.find_next_sibling('dd')
            if not dd:
                continue
            title = dt.get_text(strip=True).rstrip("：").rstrip(":")
            if title and title not in specs:
                specs[title] = {
                    'value': dd.get_text(strip=True),
                    'element': dd,
                    'links': [a.text for a in dd.select('a')],
                    'row_element': target_wrapper,
                }

    def _scrape_row_dt_dd(self, rows, header_selector, value_selector, specs: dict) -> None:
        for tr in rows:
            dds = tr.select(value_selector)
            dts = tr.select(header_selector)
            for j, th in enumerate(dts):
                thTitle = th.get_text(strip=True) if len(th.contents) > 0 else "Unknown"
                if not thTitle:
                    thTitle = "Unknown"
                thTitle = thTitle.rstrip("：").rstrip(":")
                if len(dds) <= j:
                    continue
                if thTitle not in specs or specs[thTitle]['value'] == "":
                    specs[thTitle] = {
                        'value': dds[j].get_text(strip=True),
                        'element': dds[j],
                        'links': [a.text for a in dds[j].select('a')],
                        'row_element': tr,
                    }

    def _scrape_specs(self, response: BeautifulSoup) -> dict:
        """
        Extracts key-value pairs from the property detail table.
        Returns a dictionary where keys are the header text (th/dt)
        and values are a dict containing 'value' (text) and 'element' (dd tag).
        Cached per response instance to eliminate redundant DOM traversals.
        """
        resp_id = id(response)
        if not hasattr(self, '_scrape_specs_cache'):
            self._scrape_specs_cache = {}
        if resp_id in self._scrape_specs_cache:
            return self._scrape_specs_cache[resp_id]

        specs = {}
        table_config = self.selectors.get('table', {})
        table_selector = table_config.get(
            'selector', 'div.m-status-table__wrapper, #propertySummarySection dl'
        )
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
                self._scrape_dl_direct_children(target_wrapper, specs)
            # Case 2: rows (div/dl) contain dt/dd
            self._scrape_row_dt_dd(rows, header_selector, value_selector, specs)

        self._scrape_specs_cache[resp_id] = specs
        return specs


    def _clean_text(self, text):
        if text:
            return text.strip()
        return ""

    async def parsePropertyListPage(self, response):
        async for destUrl in self._parsePageCore(response, self.getPropertyListXpath, self.getPropertyListDestUrl):
            yield destUrl

    def _parsePropertyDetailPage(self, item, response):
        # 0. 掲載終了・物件不在の早期検知
        check_tokyu_listing_ended(response, getattr(item, 'pageUrl', 'unknown'))

        # Pre-fetch specs dictionary once per detail page
        specs = self._scrape_specs(response)
        
        item.propertyName = self._parsePropertyName(response, specs)
        item.priceStr = self._parsePriceStr(response, specs)
        item.price = self._parsePrice(response, specs)
        
        item.address = self._parseAddress(response, specs)
        item.address1 = self._parseAddress1(response, specs)
        item.address2 = self._parseAddress2(response, specs)
        item.address3 = self._parseAddress3(response, specs)
        item.addressKyoto = ""
        
        item.transport1 = self._parseTransport1(response, specs)
        self._populateTraffic(item, item.transport1)
        
        item.hikiwatashi = self._parseHikiwatashi(response, specs)
        item.genkyo = self._parseGenkyo(response, specs)
        item.tochikenri = self._parseTochikenri(response, specs)
        item.sonotaHiyouStr = self._parseSonotaHiyouStr(response, specs)
        item.torihiki = self._parseTorihiki(response, specs)
        item.biko = self._parseBiko(response, specs)
        
        return item


    # --- Common Extraction Methods ---
    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = self.selectors.get('price_key', "価格")
        if key in specs:
             return specs[key]['value']
        # Header/hero/table price element fallback
        for sel in ['p.price', 'span.price', 'div.price', 'td.price', '.p-detail-hero__price', '.price-text', '.detail-header__price', '.m-status-table__price', '.p-detail-summary__price', 'span.num']:
            el = response.select_one(sel)
            if el is None:
                continue
            el_text = el.get_text()
            if '万円' in el_text or '円' in el_text:
                return el_text.strip()
        # Search elements containing '万円' with price-like structure
        for tag in response.find_all(['span', 'p', 'div', 'td', 'dd']):
            txt = tag.get_text().strip()
            if '万円' in txt and len(txt) < 30 and re.search(r'\d+', txt):
                return txt
        return ""

    def _parsePrice(self, response: BeautifulSoup, specs=None) -> int | None:
        return converter.parse_price(self._parsePriceStr(response, specs))

    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = self.selectors.get('address_key', "所在地")
        val = self._get_spec_val(specs, key) or self._get_spec_val(specs, "所在地")
        if val:
            if "Googleマップ" in val:
                val = val.split("Googleマップ")[0].strip()
            return val
        return super()._parseAddress(response, specs)

    def _parseAddress1(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = self.selectors.get('address_key', "所在地")
        if key in specs and isinstance(specs[key], dict):
            links = specs[key].get('links', [])
            if len(links) >= 1: return links[0]
        addr = self._parseAddress(response, specs)
        pref, _, _ = self._split_address(addr)
        return pref

    def _parseAddress2(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = self.selectors.get('address_key', "所在地")
        if key in specs and isinstance(specs[key], dict):
            links = specs[key].get('links', [])
            if len(links) >= 2: return links[1]
        addr = self._parseAddress(response, specs)
        _, city, _ = self._split_address(addr)
        return city

    def _parseAddress3(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = self.selectors.get('address_key', "所在地")
        if key in specs and isinstance(specs[key], dict):
            links = specs[key].get('links', [])
            if len(links) >= 3: return links[2]
        addr = self._parseAddress(response, specs)
        _, _, town = self._split_address(addr)
        return town

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = self.selectors.get('transport_key', "交通")
        return self._get_spec_val(specs, key)


    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = self.selectors.get('hikiwatashi_key', "引渡時")
        if key not in specs: key = "引渡"
        if key not in specs: key = "引渡時期"
        return self._get_spec_val(specs, key)

    def _parseGenkyo(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "現況"
        if key not in specs: key = "建物現況"
        return self._get_spec_val(specs, key)

    def _parseTochikenri(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "土地権利"
        return self._get_spec_val(specs, key)

    def _parseSonotaHiyouStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "その他費用"
        return self._get_spec_val(specs, key)

    def _parseTorihiki(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "取引態様"
        return self._get_spec_val(specs, key)

    def _parseBiko(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "備考"
        return self._get_spec_val(specs, key)



    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "間取り"
        return self._get_spec_val(specs, key)

    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "建物構造"
        return self._get_spec_val(specs, key)

    def _parseChikunengetsuStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "築年月"
        return self._get_spec_val(specs, key)

    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        val = self._parseChikunengetsuStr(response, specs)
        return converter.parse_chikunengetsu(val)

    def _parseTochiMensekiStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "土地面積"
        return self._get_spec_val(specs, key)

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        val = self._parseTochiMensekiStr(response, specs)
        return converter.parse_menseki(val)

    def _parseTatemonoMensekiStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "建物面積"
        if key not in specs: key = "延床面積"
        return self._get_spec_val(specs, key)

    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        val = self._parseTatemonoMensekiStr(response, specs)
        return converter.parse_menseki(val)

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        val = self._parseChiikiChiku(response, specs)
        if "/" in val:
            return val.split("/")[-1].strip()
        return val

    def _parseKenpeiStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "建ぺい率"
        return self._get_spec_val(specs, key)

    def _parseYousekiStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "容積率"
        return self._get_spec_val(specs, key)

    def _parseKenpei(self, response: BeautifulSoup, specs=None) -> int:
        val = self._parseKenpeiStr(response, specs)
        match = re.search(r'(\d+)', val)
        return int(match.group(1)) if match else 0

    def _parseYouseki(self, response: BeautifulSoup, specs=None) -> int:
        val = self._parseYousekiStr(response, specs)
        match = re.search(r'(\d+)', val)
        return int(match.group(1)) if match else 0

    def _parseKenpeiYousekiStr(self, response: BeautifulSoup, specs=None) -> str:
        kenpei = self._parseKenpeiStr(response, specs)
        youseki = self._parseYousekiStr(response, specs)
        res = []
        if kenpei: res.append(f"建ぺい率:{kenpei}")
        if youseki: res.append(f"容積率:{youseki}")
        return " ".join(res)

    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "接道状況"
        if key in specs: return specs[key]['value']
        key = "接道"
        return specs[key]['value'] if key in specs else "-"

    def _parseDouro(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "接道方向／幅員"
        return self._get_spec_val(specs, key)

    def _parseDouroMuki(self, response: BeautifulSoup, specs=None) -> str:
        val = self._parseDouro(response, specs)
        match = re.search("(北|南|東|西)+", val)
        return match.group(0) if match else "-"

    def _parseDouroHaba(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        val = self._parseDouro(response, specs)
        match = re.search(r'(\d+(\.\d+)?)\s*m', val)
        if match: return Decimal(match.group(1))
        return None

    def _parseDouroKubun(self, response: BeautifulSoup, specs=None) -> str:
        val = self._parseDouro(response, specs)
        if "公道" in val: return "公道"
        if "私道" in val: return "私道"
        return "-"

    def _parseSetsumen(self, response: BeautifulSoup, specs=None) -> Decimal:
        return Decimal(0)

    def _parseChimokuChisei(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "地目（現況）"
        if key not in specs: key = "地目"
        return self._get_spec_val(specs, key)

    def _parseChimoku(self, response: BeautifulSoup, specs=None) -> str:
        val = self._parseChimokuChisei(response, specs)
        return val.split("（")[0].strip() if "（" in val else val

    def _parseChisei(self, response: BeautifulSoup, specs=None) -> str:
        val = self._parseChimokuChisei(response, specs)
        if "（" in val:
            match = re.search("（(.*?)）", val)
            if match: return match.group(1)
        return "-"

    def _parseChiikiChiku(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "用途地域等"
        return self._get_spec_val(specs, key)

    def _parseKuiki(self, response: BeautifulSoup, specs=None) -> str:
        val = self._parseChiikiChiku(response, specs)
        if "/" in val:
            return val.split("/")[0].strip()
        if specs is None: specs = self._scrape_specs(response)
        key = "都市計画"
        return self._get_spec_val(specs, key)

    def _parseBoukaChiiki(self, response: BeautifulSoup, specs=None) -> str:
        val = self._parseBiko(response, specs)
        if "防火" in val: return "防火地域級等あり" 
        return "-"

    def _parseSaikenchiku(self, response: BeautifulSoup, specs=None) -> str:
        val = self._parseBiko(response, specs)
        if "再建築不可" in val: return "不可"
        return "可"

    def _parseSonotaChiiki(self, response: BeautifulSoup, specs=None) -> str:
        return "-"

    def _parseKenchikuJoken(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "建築条件"
        return specs[key]['value'] if key in specs else "-"


    def _parseKokudoHou(self, response: BeautifulSoup, specs=None) -> str:
        val = self._parseBiko(response, specs)
        if "国土法" in val: return "届出要"
        return "不要"

    def _parseSaikou(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "向き"
        if key not in specs: key = "開口向き"
        if key in specs: return specs[key]['value']
        # Fallback to douro
        return self._parseDouroMuki(response, specs)


    def _parseParking(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "駐車場"
        return self._get_spec_val(specs, key)

    def _parseShidoMensekiStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "私道面積"
        return specs[key]['value'] if key in specs else "0"

    def _parseShidoMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        return converter.parse_menseki(self._parseShidoMensekiStr(response, specs))

    def _parseKaisuStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "建物構造"
        return self._get_spec_val(specs, key)


class TokyuMansionParser(TokyuParser, MansionParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseMadori(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "") or super()._parseMadori(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("構造", "") or super()._parseKouzou(response, specs)

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

    def getRootXpath(self): return self.selectors.get('root_xpath')
    def getAreaXpath(self): return self.selectors.get('area_xpath')
    def getPropertyListXpath(self): return self.selectors.get('property_links_xpath')

    def createEntity(self):
        return TokyuMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item: TokyuMansion = super()._parsePropertyDetailPage(item, response)
        specs = self._scrape_specs(response)
        
        item.madori = self._parseMadori(response, specs)
        item.senyuMensekiStr = self._parseSenyuMensekiStr(response, specs)
        item.senyuMenseki = self._parseSenyuMenseki(response, specs)
        
        item.kaisu = self._parseKaisu(response, specs)
        item.kaisuStr = self._parseKaisuStr(response, specs)
        item.tatemonoKaisu = self._parseTatemonoKaisu(response, specs)
        item.kouzou = self._parseKouzou(response, specs)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        
        item.balconyMensekiStr = self._parseBalconyMensekiStr(response, specs)
        item.balconyMenseki = self._parseBalconyMenseki(response, specs)
        item.saikou = self._parseSaikou(response, specs)
        item.soukosu = self._parseSoukosu(response, specs)
        
        item.kanriKaisya = self._parseKanriKaisya(response, specs)
        item.kanriKeitai = self._parseKanriKeitai(response, specs)
        item.kanrihiStr = self._parseKanrihiStr(response, specs)
        item.kanrihi = self._parseKanrihi(response, specs)
        item.syuzenTsumitateStr = self._parseSyuzenTsumitateStr(response, specs)
        item.syuzenTsumitate = self._parseSyuzenTsumitate(response, specs)
        
        item.tyusyajo = self._parseParking(response, specs)
        item.bunjoKaisya = self._parseBunjoKaisya(response, specs)
        item.sekouKaisya = self._parseSekouKaisya(response, specs)

        self._calculateDerivedFields(item)
        return item


    def _parseSenyuMensekiStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "専有面積"
        return self._get_spec_val(specs, key)

    def _parseSenyuMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        return converter.parse_menseki(self._parseSenyuMensekiStr(response, specs))

    def _parseKaisu(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "所在階"
        return self._get_spec_val(specs, key)

    def _parseTatemonoKaisu(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "建物構造"
        val = self._get_spec_val(specs, key)
        match = re.search(r'地上(\d+)階', val)
        return match.group(0) if match else val

    def _parseBalconyMensekiStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "バルコニー面積"
        return self._get_spec_val(specs, key)

    def _parseBalconyMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        return converter.parse_menseki(self._parseBalconyMensekiStr(response, specs))

    def _parseSoukosu(self, response: BeautifulSoup, specs=None) -> int | None:
        if specs is None: specs = self._scrape_specs(response)
        key = "総戸数"
        if key in specs:
            match = re.search(r'(\d+)', specs[key]['value'])
            if match: return int(match.group(1))
        return None

    def _parseKanriKaisya(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "管理会社"
        return self._get_spec_val(specs, key)

    def _parseKanriKeitai(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "管理員の勤務形態"
        if key not in specs: key = "管理形態"
        return self._get_spec_val(specs, key)

    def _parseKanrihiStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "管理費"
        return self._get_spec_val(specs, key)

    def _parseKanrihi(self, response: BeautifulSoup, specs=None) -> int | None:
        return converter.parse_price(self._parseKanrihiStr(response, specs))

    def _parseSyuzenTsumitateStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "修繕積立金"
        return self._get_spec_val(specs, key)

    def _parseSyuzenTsumitate(self, response: BeautifulSoup, specs=None) -> int | None:
        return converter.parse_price(self._parseSyuzenTsumitateStr(response, specs))

    def _parseBunjoKaisya(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "分譲会社"
        if key not in specs: key = "分譲主"
        return self._get_spec_val(specs, key)

    def _parseSekouKaisya(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        key = "施工会社"
        return self._get_spec_val(specs, key)


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

class TokyuTochiParser(TokyuParser, TochiParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseMaguchi(self, response, specs=None):
        return super()._parseMaguchi(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseKenpei(self, response, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseYouseki(self, response, specs=None):
        return super()._parseYouseki(response, specs)

    def _parseChimoku(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("地目", "") or super()._parseChimoku(response, specs)

    def _parseSetsudou(self, response, specs=None) -> str:
        return super()._parseSetsudou(response, specs)

    def _parseRights(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "") or super()._parseYoutoChiiki(response, specs)

    property_type = 'tochi'

    def getRootXpath(self): return self.selectors.get('root_xpath')
    def getAreaXpath(self): return self.selectors.get('area_xpath')
    def getPropertyListXpath(self): return self.selectors.get('property_links_xpath')

    def createEntity(self):
        return TokyuTochi()

    def _apply_maguchi_from_setsumen(self, item) -> None:
        if item.setsumen is None:
            return
        item.maguchiStr = str(item.setsumen)
        m = re.search(r'([0-9]+(?:\.[0-9]+)?)', item.maguchiStr)
        if m:
            item.maguchi = Decimal(m.group(1))

    def _apply_road_width_from_douro(self, item) -> None:
        if item.douroHaba is None:
            return
        item.roadWidthStr = str(item.douroHaba)
        m = re.search(r'([0-9]+(?:\.[0-9]+)?)', item.roadWidthStr)
        if m:
            item.roadWidth = Decimal(m.group(1))

    def _apply_maguchi_from_setsudou(self, item) -> None:
        if item.maguchi and item.maguchi != 0:
            return
        if not item.setsudou:
            return
        mag_match = re.search(
            r'(?:間口|接面|接す|接道)\s*[：:]?\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?',
            item.setsudou,
        )
        if mag_match:
            item.maguchi = Decimal(mag_match.group(1))
            item.maguchiStr = mag_match.group(0)

    def _apply_tochi_road_fields(self, item) -> None:
        self._apply_maguchi_from_setsumen(item)
        self._apply_road_width_from_douro(item)
        if item.douroMuki:
            item.roadDirection = item.douroMuki
        if item.douroKubun:
            item.roadType = item.douroKubun
        if item.setsudou:
            structure_match = re.search(
                r'(角地|二方|三方|四方|敷延|袋小路|中間地|両面道路)', item.setsudou
            )
            item.roadStructure = structure_match.group(1) if structure_match else "中間地"
        else:
            item.roadStructure = "中間地"
        self._apply_maguchi_from_setsudou(item)
        if item.tochiMenseki and item.maguchi and item.maguchi > 0:
            item.okuyuki = round(item.tochiMenseki / item.maguchi, 2)
            item.okuyukiStr = f"{item.okuyuki}m"
        else:
            item.okuyuki = None
            item.okuyukiStr = ""

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
        self._apply_tochi_road_fields(item)
        return item

class TokyuKodateParser(TokyuParser, KodateParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    def _parseMadori(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "") or super()._parseMadori(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("構造", "") or super()._parseKouzou(response, specs)

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
        
        # 統一土地評価フィールドのパース ＆ 代入
        import re
        if item.setsumen is not None:
            item.maguchiStr = item.setsumen
            m = re.search(r'([0-9]+(?:\.[0-9]+)?)', item.maguchiStr)
            if m:
                item.maguchi = Decimal(m.group(1))
                
        if item.douroHaba is not None:
            item.roadWidthStr = item.douroHaba
            m = re.search(r'([0-9]+(?:\.[0-9]+)?)', item.roadWidthStr)
            if m:
                item.roadWidth = Decimal(m.group(1))
                
        if item.tochiMenseki and getattr(item, 'maguchi', None) and item.maguchi > 0:
            item.okuyuki = round(item.tochiMenseki / item.maguchi, 2)
            item.okuyukiStr = f"{item.okuyuki}m"
            
        return item

    def _parseSetsumen_Str(self, response: BeautifulSoup) -> str:
        return self._parseDouro(response)
    def _parseDouroHaba_Str(self, response: BeautifulSoup) -> str:
        return self._parseDouro(response)

class TokyuInvestmentParser(InvestmentParser, InvestmentParserBase):

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        return super()._parseKouzou(response, specs)

    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    property_type = 'investment'
    BASE_URL = 'https://www.livable.co.jp'

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('tokyu', self.property_type)

    async def parsePropertyListPage(self, response):
        # Try Next.js data first
        script = response.find('script', id='__NEXT_DATA__')
        if script:
            try:
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
                logger.error("Error parsing __NEXT_DATA__: %s", e)

        # Fallback to selectors
        selector = self.selectors.get('property_links')
        for link in response.select(selector):
            href = link.get('href')
            if href:
                yield self.BASE_URL + href
    def _getNextJsData(self, response):
        check_tokyu_listing_ended(response)
        if hasattr(response, '_next_data_json'):
            return response._next_data_json
        
        script = response.find('script', id='__NEXT_DATA__')
        if script:
            try:
                data = json.loads(script.string)
                response._next_data_json = data
                return data
            except (json.JSONDecodeError, TypeError, ValueError, AttributeError) as exc:
                logger.debug("Tokyu __NEXT_DATA__ parse skipped: %s", exc)
        return None

    def _get_item_data(self, response, title):
        data = self._getNextJsData(response)
        if not data: return None
        pageProps = data.get('props', {}).get('pageProps', {})
        summary = pageProps.get('summary', {})
        tableItems = summary.get('tableItems', [])
        
        # 表記揺れのフォールバック定義
        fallback_titles = {
            '価格': ['価格', '販売価格'],
            '所在地': ['所在地', '住所'],
            '交通': ['交通', '最寄り駅', '最寄駅'],
            '年間予定賃料収入': ['年間予定賃料収入', '満室時想定年収', '満室想定年収', '想定年収', '年間想定賃料'],
            '予定利回り': ['予定利回り', '表面利回り', '利回り', '想定利回り', '実質利回り'],
            '土地面積': ['土地面積', '敷地面積'],
            '建物面積': ['建物面積', '延床面積', '専有面積'],
            '間取り': ['間取り'],
            '総戸数': ['総戸数', '戸数'],
            '築年月': ['築年月', '築年'],
            '建ぺい率': ['建ぺい率', '建ペイ率'],
            '容積率': ['容積率'],
            '用途地域等': ['用途地域等', '用途地域'],
            '接道状況': ['接道状況', '接道'],
            '接道方向／幅員': ['接道方向／幅員', '接道状況', '前面道路'],
            '地目': ['地目'],
            '現況': ['現況', '建物現況'],
            '引渡可能年月': ['引渡可能年月', '引渡時期', '引渡', '引渡可能時期'],
            '取引態様': ['取引態様'],
            '備考': ['備考'],
            '土地権利': ['土地権利', '権利'],
            '管理形態': ['管理形態']
        }
        
        target_titles = fallback_titles.get(title, [title])
        for t_item in tableItems:
            if t_item.get('title') in target_titles:
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

    def _parsePropertyName(self, response, specs=None):
        data = self._getNextJsData(response)
        if not data:
            return super()._parsePropertyName(response, specs)

        
        pageProps = data.get('props', {}).get('pageProps', {})
        viewingProperty = pageProps.get('viewingProperty', {})
        name = viewingProperty.get('propertyName')
        if not name:
            # tableItemsからもフォールバックで物件名を探す
            name = self._get_text_value(self._get_item_data(response, '物件名'))
        if not name:
            return super()._parsePropertyName(response)
        return name

    def _parsePrice(self, response, specs=None):
        data = self._getNextJsData(response)
        if not data: return None
        
        pageProps = data.get('props', {}).get('pageProps', {})
        viewingProperty = pageProps.get('viewingProperty', {})
        price = viewingProperty.get('priceModel', {}).get('price')
        
        if price is None:
            price_data = self._get_item_data(response, '価格')
            if price_data:
                if 'price' in price_data:
                    price = price_data['price'].get('price')
                elif isinstance(price_data, dict) and 'value' in price_data:
                    price = converter.parse_price(str(price_data['value']))
        return price

    def _parseYield(self, response, specs=None):
        yield_val_str = self._get_text_value(self._get_item_data(response, '予定利回り'))
        if yield_val_str:
            import re
            match = re.search(r'([\d\.]+)', yield_val_str)
            if match:
                return float(match.group(1))
        return None

    def _parseAddress(self, response, specs=None):
        data = self._getNextJsData(response)
        if not data: return ""
        
        pageProps = data.get('props', {}).get('pageProps', {})
        viewingProperty = pageProps.get('viewingProperty', {})
        
        if viewingProperty.get('address'):
            return viewingProperty.get('address')
        
        addr_data = self._get_item_data(response, '所在地')
        if addr_data:
            if isinstance(addr_data, dict) and 'links' in addr_data:
                return "".join([l.get('text', '') for l in addr_data['links']])
            return self._get_text_value(addr_data)
        return ""

    def _parseAccess(self, response, specs=None):
        data = self._getNextJsData(response)
        if not data: return ""
        
        pageProps = data.get('props', {}).get('pageProps', {})
        viewingProperty = pageProps.get('viewingProperty', {})
        
        if viewingProperty.get('access'):
            return viewingProperty.get('access')
        
        access_data = self._get_item_data(response, '交通')
        if access_data:
            if isinstance(access_data, dict) and 'links' in access_data:
                lines = []
                for link_group in access_data['links']:
                    if isinstance(link_group, list):
                        line_str = "".join([l.get('text', '') for l in link_group])
                        lines.append(line_str)
                    else:
                        lines.append(link_group.get('text', ''))
                return " ".join(lines)
            return self._get_text_value(access_data)
        return ""

    def _parseMonthlyRent(self, response, specs=None):
        annual_income_str = self._get_text_value(self._get_item_data(response, '年間予定賃料収入'))
        if not annual_income_str:
            annual_income_str = self._scrape_specs(response).get("年間予定賃料収入", "")
        if annual_income_str:
            annual_income = converter.parse_price(annual_income_str)
            if annual_income:
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

    def _set_attr_detail(self, item, attr: str, response, label: str, *, menseki=False, ratio=False) -> None:
        if not hasattr(item, attr):
            return
        if menseki:
            setattr(item, attr, self._parseMenseki(response, label))
        elif ratio:
            setattr(item, attr, self._parseKenpeiYouseki(response, label))
        else:
            setattr(item, attr, self._parseDetailString(response, label))

    def _fill_invest_nextjs_core(self, item, response) -> None:
        sel = self.selectors.get('property_name_clean')
        name_from_sel = (
            response.select_one(sel).get_text(strip=True)
            if sel and response.select_one(sel)
            else ""
        )
        item.propertyName = self._parsePropertyName(response) or name_from_sel
        if not item.propertyName:
            h1 = response.find("h1")
            item.propertyName = h1.get_text(strip=True) if h1 else ""

        item.price = self._parsePrice(response)
        if not item.price:
            item.price = converter.parse_price(
                self._get_text_value(self._get_item_data(response, '価格'))
                or self._parsePriceStr(response)
            )
        item.yield_rate = self._parseYield(response)
        item.address = self._parseAddress(response)
        if not item.address:
            item.address = self._parseAddress(response)
        item.transport1 = self._parseAccess(response)
        item.monthlyRent = self._parseMonthlyRent(response)
        item.annualRent = self._parseAnnualRent(response)
        item.grossYield = self._parseGrossYield(response)

    def _fill_invest_nextjs_areas(self, item, response) -> None:
        self._set_attr_detail(item, 'tochiMensekiStr', response, '土地面積')
        self._set_attr_detail(item, 'tochiMenseki', response, '土地面積', menseki=True)
        self._set_attr_detail(item, 'tatemonoMensekiStr', response, '建物面積')
        self._set_attr_detail(item, 'tatemonoMenseki', response, '建物面積', menseki=True)
        self._set_attr_detail(item, 'madori', response, '間取り')
        self._set_attr_detail(item, 'soukosuStr', response, '総戸数')
        self._set_attr_detail(item, 'chikunengetsuStr', response, '築年月')
        self._set_attr_detail(item, 'kenpei', response, '建ぺい率', ratio=True)
        self._set_attr_detail(item, 'youseki', response, '容積率', ratio=True)
        self._set_attr_detail(item, 'kenpeiStr', response, '建ぺい率')
        self._set_attr_detail(item, 'yousekiStr', response, '容積率')
        self._set_attr_detail(item, 'youtoChiiki', response, '用途地域等')

    def _fill_invest_nextjs_meta(self, item, response) -> None:
        setsudou_val = (
            self._parseDetailString(response, '接道状況')
            + " "
            + self._parseDetailString(response, '接道方向／幅員')
        )
        if hasattr(item, 'setsudou'):
            item.setsudou = setsudou_val
        elif hasattr(item, 'startRoad'):
            item.startRoad = setsudou_val
        for attr, label in (
            ('chimoku', '地目'),
            ('genkyo', '現況'),
            ('hikiwatashi', '引渡可能年月'),
            ('torihiki', '取引態様'),
            ('biko', '備考'),
            ('tochikenri', '土地権利'),
            ('kanriKeitai', '管理形態'),
        ):
            self._set_attr_detail(item, attr, response, label)
        if hasattr(item, 'transport1') and item.transport1:
            self._populateTraffic(item, item.transport1)
        elif hasattr(item, 'traffic') and getattr(item, 'traffic', None):
            self._populateTraffic(item, item.traffic)

    def _fill_invest_html_core(self, item, response) -> None:
        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)
        item.traffic = self._parseTraffic(response)
        self._populateTraffic(item, item.traffic)
        item.kouzou = self._parseStructure(response)
        item.chikunengetsuStr = self._parseYearBuilt(response)
        item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)
        item.tochiMensekiStr = self._parseLandArea(response)
        item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr) or 0
        item.tatemonoMensekiStr = self._parseBuildingArea(response)
        item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr) or 0
        item.grossYield = self._parseGrossYield(response)
        if hasattr(item, 'annualRent'):
            item.annualRent = self._parseAnnualRent(response) or 0
        if hasattr(item, 'currentStatus'):
            item.currentStatus = self._parseCurrentStatus(response)
        if hasattr(item, 'soukosu'):
            item.soukosu = self._parseSoukosu(response)
        if hasattr(item, 'kenpeiStr'):
            item.kenpeiStr = self._parseKenpeiStr(response)
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        if hasattr(item, 'yousekiStr'):
            item.yousekiStr = self._parseYousekiStr(response)
            item.youseki = converter.parse_ratio(item.yousekiStr)
        if hasattr(item, 'youtoChiiki'):
            item.youtoChiiki = self._parseYoutoChiiki(response)

    def _apply_invest_road_width(self, item, specs) -> None:
        douro_haba_str = (
            specs.get("道路幅員", "")
            or specs.get("前面道路幅員", "")
            or specs.get("道路幅", "")
        )
        if douro_haba_str:
            item.roadWidthStr = str(douro_haba_str)
            m = re.search(r'([0-9]+(?:\.[0-9]+)?)', item.roadWidthStr)
            if m:
                item.roadWidth = Decimal(m.group(1))
            return
        if not item.setsudou:
            return
        width_match = re.search(
            r'(?:幅員|幅|道路|前面)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?',
            item.setsudou,
        )
        if width_match:
            item.roadWidth = Decimal(width_match.group(1))
            return
        dir_width_match = re.search(
            r'(?:北東|北西|南東|南西|北|南|東|西)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)',
            item.setsudou,
        )
        if dir_width_match:
            item.roadWidth = Decimal(dir_width_match.group(1))

    def _fill_invest_html_setsudou(self, item, response) -> None:
        try:
            specs = self._scrape_specs(response)
            item.setsudou = self._parseSetsudou(response, specs)
            item.setsumen = specs.get("接道方向／幅員", specs.get("接道", ""))
            if item.setsumen:
                item.maguchiStr = str(item.setsumen)
                m = re.search(r'([0-9]+(?:\.[0-9]+)?)', item.maguchiStr)
                if m:
                    item.maguchi = Decimal(m.group(1))
            self._apply_invest_road_width(item, specs)
            if getattr(item, 'tochiMenseki', None) and getattr(item, 'maguchi', None) and item.maguchi > 0:
                item.okuyuki = round(Decimal(item.tochiMenseki) / item.maguchi, 2)
                item.okuyukiStr = f"{item.okuyuki}m"
        except (TypeError, ValueError, AttributeError, KeyError) as e:
            logger.error("Error parsing setsudou fields: %s", e)

    def _parsePropertyDetailPage(self, item, response):
        # Override to support Next.js JSON data extraction with fallback
        if self._getNextJsData(response):
            self._fill_invest_nextjs_core(item, response)
            self._fill_invest_nextjs_areas(item, response)
            self._fill_invest_nextjs_meta(item, response)
            return item
        self._fill_invest_html_core(item, response)
        self._fill_invest_html_setsudou(item, response)
        return item

    async def parseNextPage(self, response):
        next_page_text = self.selectors.get('next_page', "次へ")
        next_link = response.find('a', string=re.compile(next_page_text))
        if next_link and next_link.get('href'):
            return self.BASE_URL + next_link.get('href')
        return ""

    def _scrape_specs(self, response: BeautifulSoup) -> dict:
        resp_id = id(response)
        if not hasattr(self, '_scrape_specs_cache'):
            self._scrape_specs_cache = {}
        if resp_id in self._scrape_specs_cache:
            return self._scrape_specs_cache[resp_id]

        specs = super()._scrape_specs(response)
        for dl in response.select('#propertySummarySection dl, div.m-status-table__wrapper'):
            for dt in dl.find_all('dt'):
                dd = dt.find_next_sibling('dd')
                if dd: specs[dt.get_text(strip=True).rstrip("：")] = dd.get_text(strip=True)

        self._scrape_specs_cache[resp_id] = specs
        return specs

    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        return specs.get("価格", "")

    def _parsePrice(self, response: BeautifulSoup, specs=None) -> int | None:
        return converter.parse_price(self._parsePriceStr(response, specs))

    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        return specs.get("所在地", "")

    def _parseTraffic(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        return specs.get("交通", "")

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        return self._parseTraffic(response, specs)

    def _parseStructure(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        return specs.get("建物構造", "")

    def _parseYearBuilt(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        return specs.get("築年月", "")

    def _parseLandArea(self, response: BeautifulSoup, specs=None):
        if specs is None: specs = self._scrape_specs(response)
        return specs.get("土地面積", "")

    def _parseBuildingArea(self, response: BeautifulSoup, specs=None):
        if specs is None: specs = self._scrape_specs(response)
        return specs.get("建物面積", "") or specs.get("延床面積", "") or specs.get("専有面積", "")

    def _gross_yield_from_item_data(self, response: BeautifulSoup):
        try:
            parsed = self._parseYield(response)
            if parsed is not None:
                return Decimal(str(parsed))
        except (TypeError, ValueError, AttributeError):
            pass
        try:
            raw = self._get_text_value(self._get_item_data(response, "予定利回り"))
            if raw:
                return raw
        except (TypeError, ValueError, AttributeError):
            pass
        return None

    def _parseGrossYield(self, response: BeautifulSoup, specs=None) -> Decimal:
        if specs is None:
            specs = self._scrape_specs(response)
        val_str = (
            specs.get("利回り", "")
            or specs.get("表面利回り", "")
            or specs.get("予定利回り", "")
            or specs.get("想定利回り", "")
            or specs.get("実質利回り", "")
        )
        if not val_str:
            # Next.js / item-data path used by apartment invest pages.
            fallback = self._gross_yield_from_item_data(response)
            if isinstance(fallback, Decimal):
                return fallback
            if fallback:
                val_str = fallback
        match = re.search(r"(\d+(\.\d+)?)", val_str or "")
        return Decimal(match.group(1)) if match else Decimal(0)

    def _parseAnnualRent(self, response: BeautifulSoup, specs=None) -> int | None:
        if specs is None:
            specs = self._scrape_specs(response)
        for key in (
            "年間予定賃料収入",
            "満室時想定年収",
            "満室想定年収",
            "想定年収",
            "年間想定賃料",
            "年間収入",
        ):
            raw = specs.get(key, "")
            if raw:
                return converter.parse_price(raw)
        try:
            raw = self._get_text_value(self._get_item_data(response, "年間予定賃料収入"))
            if raw:
                return converter.parse_price(raw)
        except (TypeError, ValueError, AttributeError):
            pass
        return None

    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        return specs.get("現況", "")

    def _parseSoukosu(self, response: BeautifulSoup, specs=None) -> int | None:
        if specs is None: specs = self._scrape_specs(response)
        return converter.parse_numeric(specs.get("総戸数", ""))

    def _parseKenpeiStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        return specs.get("建ぺい率", "")

    def _parseYousekiStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        return specs.get("容積率", "")

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        if specs is None: specs = self._scrape_specs(response)
        return specs.get("用途地域", "")


class TokyuInvestmentApartmentParser(TokyuInvestmentParser, InvestmentParserBase):

    def _parseGrossYield(self, response, specs=None):
        return super()._parseGrossYield(response, specs)

    def _parseAnnualRent(self, response, specs=None):
        return super()._parseAnnualRent(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        return super()._parseKouzou(response, specs)

    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    def createEntity(self):
        from package.models.tokyu import TokyuInvestmentApartment
        return TokyuInvestmentApartment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        item.propertyType = "Apartment"
        return item


class TokyuInvestmentKodateParser(TokyuInvestmentParser, KodateParserBase):

    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    def _parseMadori(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "") or super()._parseMadori(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("構造", "") or super()._parseKouzou(response, specs)

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
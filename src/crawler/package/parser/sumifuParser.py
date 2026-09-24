# -*- coding: utf-8 -*-
import sys
import asyncio


from bs4 import BeautifulSoup
from package.models.sumifu import SumifuMansion, SumifuTochi, SumifuKodate, SumifuInvestmentKodate, SumifuInvestmentApartment
from package.parser.investmentParser import InvestmentParser
from django.db import models
import importlib
importlib.reload(sys)
from decimal import Decimal
import datetime
import re
from package.utils import converter
from package.parser.baseParser import InvestmentParserBase, KodateParserBase, MansionParserBase, ParserBase, TochiParserBase
import logging
from package.utils.selector_loader import SelectorLoader
import lxml.html
import urllib.parse

JAVASCRIPT_PREFIX = "javascript:"
VOID_0 = "void(0)"
DIGIT_REGEX = re.compile(r'(\d+)')
LABEL_KENPEI_YOUSEKI = "建ぺい率・容積率"
LABEL_SAIKENCHIKU_FUKA = "再建築不可"


class SumifuParser(ParserBase):

    def _parseCurrentStatus(self, response, specs=None):
        target_specs = specs or self._get_specs(response)
        return target_specs.get("現況", "") or target_specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        target_specs = specs or self._get_specs(response)
        return target_specs.get("権利", "") or target_specs.get("土地権利", "")

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    property_type = ""
    BASE_URL='https://www.stepon.co.jp'

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('sumifu', self.property_type)

    
    def getCharset(self):
        # Live pages declare charset=shift_jis; cp932 is the practical decoder.
        return "cp932"

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        return super()._parseTransport1(response, specs)

    async def getResponse(self, session, url, charset=None):
        """
        Override getResponse to add robust encoding handling.
        Sumifu sometimes sends UTF-8 despite Shift_JIS meta tag.
        """
        # First try default behavior (chardet or meta)
        try:
            response = await super().getResponse(session, url, charset)
            # Basic validation: check if tree is not empty/garbled
            # For Shift_JIS/UTF-8 mismatch, lxml might return empty tree or garbage title
            if response is not None:
                # Check for signs of bad parsing (e.g. extremely short content for a full page)
                # Area pages are usually large. 458 bytes (from debug) is suspicious.
                content_len = len(str(response))
                if content_len < 1000: # Threshold for suspicion
                    logging.warning(f"Suspiciously small content ({content_len} bytes) for {url}. Retrying with UTF-8.")
                    # Force UTF-8
                    return await super().getResponse(session, url, charset='utf-8')
            return response
        except Exception as e:
            logging.warning(f"Error in default getResponse for {url}: {e}. Retrying with UTF-8.")
            return await super().getResponse(session, url, charset='utf-8')


    def createEntity(self):
        # Base implementation, overridden in concrete parser subclasses
        return None

    def getRegionXpath(self):
        return u''

    def getRegionDestUrl(self, link_url):
        if not link_url:
            return ""
        return urllib.parse.urljoin(self.BASE_URL, link_url)

    async def parseRegionPage(self, response):
        async for dest_url in self._parsePageCore(response, self.getRegionXpath, self.getRegionDestUrl):
            yield dest_url

    def getAreaXpath(self):
        return u''

    def getAreaDestUrl(self, link_url):
        if not link_url:
            return ""
        full_url = urllib.parse.urljoin(self.BASE_URL, link_url)
        sep = "&" if "?" in full_url else "?"
        if "limit=1000" not in full_url:
            full_url += f"{sep}limit=1000&mode=2"
        return full_url

    async def parseAreaPage(self, response):       
        async for dest_url in self._parsePageCore(response, self.getAreaXpath, self.getAreaDestUrl):
            yield dest_url

    def getPropertyListXpath(self):
        xpath = self.selectors.get('property_list_xpath', u'')
        logging.info(f"[{self.property_type}] property_list_xpath: {xpath}")
        return xpath

    def getPropertyListDestUrl(self, link_url):
        return self.getRegionDestUrl(link_url)

    async def parsePropertyListPage(self, response):
        async for dest_url in self._parsePageCore(response, self.getPropertyListXpath, self.getPropertyListDestUrl):
            yield dest_url

    async def getPropertyListNextPageUrl(self, response):
        await asyncio.sleep(0)
        logging.info("getPropertyListNextPageUrl")
        next_page_selector = self.selectors.get('next_page')
        next_link = response.select_one(next_page_selector) if next_page_selector else None
        # Or simpler search for text "次へ"
        if not next_link:
             # Try finding by text "次へ"
             next_link = response.find('a', string=re.compile("次へ"))

        if not next_link:
            return None
            
        href = next_link.get("href", "")
        if not href or href == "#" or href.startswith(JAVASCRIPT_PREFIX):
            return None
        next_page_url = urllib.parse.urljoin(self.BASE_URL, href)
        if JAVASCRIPT_PREFIX in next_page_url or VOID_0 in next_page_url:
            return None
        logging.info("getPropertyListNextPageUrl next_page_url:" + next_page_url)
        return next_page_url




    def _kenpei_youseki_from_labels(self, text):
        kenpei = youseki = None
        k_match = re.search(r'建ぺい率(\d+)%', text)
        if k_match:
            kenpei = int(k_match.group(1))
        y_match = re.search(r'容積率(\d+)%', text)
        if y_match:
            youseki = int(y_match.group(1))
        return kenpei, youseki

    def _kenpei_youseki_from_parts(self, text):
        kenpei = youseki = None
        parts = re.split(r'[・/]', text)
        if len(parts) < 2:
            return kenpei, youseki
        k_part = parts[0].strip()
        y_part = parts[1].strip()
        if "%" in k_part:
            k_m = DIGIT_REGEX.search(k_part)
            if k_m:
                kenpei = int(k_m.group(1))
        if "%" in y_part:
            y_m = DIGIT_REGEX.search(y_part)
            if y_m:
                youseki = int(y_m.group(1))
        return kenpei, youseki

    def _parseKenpeiYousekiText(self, text):
        # Example: 建ぺい率60% 容積率200%  OR  60%・200%  OR  60%/200%
        if not text:
            return None, None
        try:
            if "建ぺい率" in text or "容積率" in text:
                return self._kenpei_youseki_from_labels(text)
            return self._kenpei_youseki_from_parts(text)
        except (ValueError, TypeError, AttributeError):
            return None, None

    def _parseChimoku(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("地目", target_specs.get("地勢", ""))
        return val if val else ""

    def _parseChisei(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("地勢", target_specs.get("地目", ""))
        return val if val else ""

    def _parseSetsudou(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("接道状況", "")
        return val if val else ""

    def _parseDouroInfo(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("接道状況", "")
        return self._parseDouroText(val) if val else {}

    def _parseDouro(self, response, _specs=None):
        return self._parseDouroInfo(response).get('douro', '')

    def _parseDouroMuki(self, response, _specs=None):
        return self._parseDouroInfo(response).get('douroMuki', '')

    def _parseDouroHaba(self, response, _specs=None):
        return self._parseDouroInfo(response).get('douroHaba', None)

    def _parseDouroKubun(self, response, _specs=None):
        return self._parseDouroInfo(response).get('douroKubun', '')

    def _parseSetsumen(self, response, _specs=None):
        return self._parseDouroInfo(response).get('setsumen', None)

    def _parseChiikiChiku(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("地域地区", "")

    def _parseBoukaChiiki(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        text = target_specs.get("地域地区", "")
        if text and '/' in text:
            return text.split('/')[0].strip()
        elif text and '｜' in text:
            return text.split('｜')[0].strip()
        else:
            return text if text else ""

    def _parseSonotaChiiki(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        text = target_specs.get("地域地区", "")
        if text and '/' in text:
            return text.split('/')[1].strip()
        elif text and '｜' in text:
            return text.split('｜')[1].strip()
        else:
            return ""

    def _parseDouroText(self, text):
        # Example: "東4m(公道)接面5.1m" or "一方道路・南西17.2m(公道)接面2m"
        result = {}
        if not text: return result
        
        # Direction
        muki_match = re.search(r'([東西南北]{1,2})', text)
        if muki_match:
            result['douroMuki'] = muki_match.group(1)
        
        # Width
        haba_match = re.search(r'(\d+(\.\d+)?)m', text)
        if haba_match:
            try: result['douroHaba'] = Decimal(haba_match.group(1))
            except Exception: pass
        
        # Type (Public/Private)
        if "公道" in text:
            result['douroKubun'] = "公道"
        elif "私道" in text:
            result['douroKubun'] = "私道"
        
        # Road name/info
        result['douro'] = text
        
        # Setsumen
        setsumen_match = re.search(r'接面(\d+(\.\d+)?)m', text)
        if setsumen_match:
            try: result['setsumen'] = Decimal(setsumen_match.group(1))
            except Exception: pass
            
        return result

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)
        item.madori = self._parseMadori(response)
        item.tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        item.tatemonoMenseki = self._parseTatemonoMenseki(response)
        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        item.kouzou = self._parseKouzou(response)
        item.kaisu = self._parseKaisu(response)
        
        # Address components
        item.address1 = self._parseAddress1(response)
        item.address2 = self._parseAddress2(response)
        item.address3 = self._parseAddress3(response)

        # Traffic
        traffic_lines = self._parseTrafficLines(response)
        item.railwayCount = len(traffic_lines)
        traffic_str = "  ".join(traffic_lines)
        self._populateTraffic(item, traffic_str)

        item.biko = self._parseBiko(response)

        return item

    def _getText(self, val):
        if not val:
            return ""
        if isinstance(val, str):
            return val.strip()
        if hasattr(val, "get_text"):
            return val.get_text(strip=True)
        return str(val).strip()

    def _parsePriceStr(self, response, _specs=None):
        price_key = self.selectors.get('price_key', "価格")
        price_td = self._getValueFromTable(response, price_key)
        if price_td:
            price_text = self._getText(price_td)
            return re.split(r"\(", price_text)[0]
        
        price_selector = self.selectors.get('price')
        if price_selector:
            for sel in str(price_selector).split(","):
                em = response.select_one(sel.strip())
                if not em:
                    continue
                text = em.get_text(" ", strip=True)
                if not text:
                    continue
                if not any(u in text for u in ("万", "億", "円")) and re.search(r"\d", text):
                    # span.price__number is digits only; unit sits outside the tag.
                    text = f"{text}万円"
                return text
        return ""

    def _parsePrice(self, response, _specs=None):
        price_str = self._parsePriceStr(response)
        return converter.parse_price(price_str)

    def _address_from_table_td(self, response):
        address_key = self.selectors.get('address_key', "所在地")
        address_td = self._getValueFromTable(response, address_key)
        if not address_td:
            return None
        if hasattr(address_td, 'find_all'):
            for btn in address_td.find_all("button"):
                btn.decompose()
            for br in address_td.find_all("br"):
                br.replace_with(" ")
        addr = self._getText(address_td)
        return re.sub(r'地図を開く$', '', addr).strip()

    def _address_from_selectors(self, response):
        address_selector = self.selectors.get('address')
        if not address_selector:
            return ""
        for sel in str(address_selector).split(","):
            addr_el = response.select_one(sel.strip())
            if not addr_el:
                continue
            if getattr(addr_el, "name", "") == "input":
                val = (addr_el.get("value") or "").strip()
                if val:
                    return val
            text = addr_el.get_text(strip=True)
            if text:
                return text
        return ""

    def _parseAddress(self, response, _specs=None):
        from_table = self._address_from_table_td(response)
        if from_table:
            return from_table
        return self._address_from_selectors(response)

    def _parseAddressComponents(self, response, _specs=None):
        addr = self._parseAddress(response)
        components = {'address1': '', 'address2': '', 'address3': ''}
        if not addr: return components
        pref, city, town = self._split_address(addr)
        components['address1'] = pref
        components['address2'] = city
        components['address3'] = town
        return components


    def _parseAddress1(self, response, _specs=None):
        return self._parseAddressComponents(response).get('address1', '')
    
    def _parseAddress2(self, response, _specs=None):
        return self._parseAddressComponents(response).get('address2', '')
        
    def _parseAddress3(self, response, _specs=None):
        return self._parseAddressComponents(response).get('address3', '')

    def _getValueFromTable(self, response: BeautifulSoup, title: str, partial_match: bool = False):
        """
        Overridden for Sumifu: use _scrape_to_dict and search with normalized keys.
        Handles labels with <br>, spaces, or extra characters.
        """
        def normalize(s):
            if not s:
                return ""
            return str(s).replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "").rstrip("：").rstrip(":")

        specs_tags = self._get_specs(response)
        target_norm = normalize(title)
        
        for key, tag in specs_tags.items():
            key_norm = normalize(key)
            if target_norm == key_norm or (partial_match and target_norm in key_norm):
                return tag
            # Additional check for common Sumifu labels that might be subset of title or vice versa
            if key_norm in target_norm:
                return tag
                
        return None

    def _parseHikiwatashi(self, response, _specs=None):
        td = self._getValueFromTable(response, "引渡時期")
        return self._getText(td)

    def _parseGenkyo(self, response, _specs=None):
        td = self._getValueFromTable(response, "現況")
        return self._getText(td)

    def _parseTochikenri(self, response, _specs=None):
        td = self._getValueFromTable(response, "土地権利")
        return self._getText(td)

    def _parseTorihiki(self, response, _specs=None):
        td = self._getValueFromTable(response, "取引態様")
        return self._getText(td)

    def _parseChikunengetsuStr(self, response, _specs=None):
        return self._getText(self._getValueFromTable(response, "築年月", True))

    def _parseChikunengetsu(self, response, _specs=None):
        chikunengetsu_str = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(chikunengetsu_str) if chikunengetsu_str else None

    def _parseBiko(self, response, _specs=None):
        td = self._getValueFromTable(response, "備考")
        if td:
            val = self._getText(td)
            return converter.truncate_str(val, 2000).strip()
        return ""

    def _parseMadori(self, response, _specs=None):
        td = self._getValueFromTable(response, "間取り")
        return self._getText(td) or ""

    def _parseTatemonoMensekiStr(self, response, _specs=None):
        td = self._getValueFromTable(response, "建物面積") or self._getValueFromTable(response, "専有面積")
        return self._getText(td)

    def _parseTatemonoMenseki(self, response, _specs=None):
        tatemono_menseki_str = self._parseTatemonoMensekiStr(response)
        return converter.parse_menseki(tatemono_menseki_str)

    def _parseTochiMensekiStr(self, response, _specs=None):
        td = self._getValueFromTable(response, "土地面積")
        return self._getText(td)

    def _parseTochiMenseki(self, response, _specs=None):
        tochi_menseki_str = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(tochi_menseki_str)

    def _parseKouzou(self, response, _specs=None):
        td = self._getValueFromTable(response, "構造", partial_match=True)
        if td:
            val = self._getText(td)
            if val and "・" in val: return val.split("・")[-1].strip()
            return val or ""
        return ""

    def _parseKaisuRaw(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("階数", target_specs.get("所在階", target_specs.get("所在階構造", "")))

    def _parseKaisuStr(self, response, _specs=None):
        val = self._parseKaisuRaw(response)
        if val and "・" in val:
            return val.split("・")[0].strip()
        return val or ""

    def _parseKaisu(self, response, _specs=None):
        k_str = self._parseKaisuStr(response)
        if k_str:
             m = DIGIT_REGEX.search(k_str)
             if m: return int(m.group(1))
        return None

    def _parseTrafficLines(self, response, _specs=None):
        transport_key = self.selectors.get('transport_key', "交通")
        transport_td = self._getValueFromTable(response, transport_key)
        if not transport_td: return []
        if hasattr(transport_td, 'select'):
            for br in transport_td.select("br"): br.replace_with("\n")
            full_text = transport_td.get_text().strip()
        else:
            full_text = str(transport_td).strip()
        return [line.strip() for line in full_text.split("\n") if line.strip()]

    def _parseRailwayCount(self, response, _specs=None):
        return len(self._parseTrafficLines(response))


        
class SumifuInvestmentParserBase(SumifuParser, InvestmentParser, InvestmentParserBase):
    """Base class for Sumifu investment property parsers"""
    property_type = 'investment'
    
    def __init__(self, params=None):
        super().__init__(params)
        
    def getCharset(self):
        return "cp932"

    def getRegionXpath(self):
        return self.selectors.get('region_xpath')

    def getAreaXpath(self):
        return self.selectors.get('area_xpath')

    def getPropertyListXpath(self):
        return self.selectors.get('property_list_xpath')

    def _href_matches_property_type(self, href: str) -> bool:
        if href.startswith(JAVASCRIPT_PREFIX) or href == "#" or "/inquiry" in href or "/contact" in href:
            return False
        if "/chintai/" in href or "/rent/" in href:
            return False
        if self.property_type in ("mansion", "kodate", "tochi"):
            return f"/{self.property_type}/" in href and "/detail_" in href
        if self.property_type in ("investment", "invest_apartment", "invest_kodate"):
            return "/pro/detail_" in href
        return "/pro/detail_" in href or "/detail_" in href

    async def parsePropertyListPage(self, response: BeautifulSoup):
        property_links_selector = self.selectors.get('property_links')
        links = response.select(property_links_selector) if property_links_selector else []
        if not links:
            fallback_selector = self.selectors.get('property_links_fallback')
            if fallback_selector:
                links = response.select(fallback_selector)

        for link in links:
            href = link.get("href")
            if not href or not self._href_matches_property_type(href):
                continue
            joined_url = urllib.parse.urljoin(self.BASE_URL, href)
            if JAVASCRIPT_PREFIX not in joined_url and VOID_0 not in joined_url:
                yield joined_url

    async def parseNextPage(self, response: BeautifulSoup):
        # Text search for '次へ'
        next_text = self.selectors.get('next_page')
        next_link = None
        
        if hasattr(response, 'xpath') and callable(response.xpath):
             # LXML support
             links = response.xpath(f"//a[contains(text(), '{next_text}')]")
             if isinstance(links, list) and len(links) > 0:
                 next_link = links[0]
        else:
             # BS4 support
             next_link = response.find("a", string=lambda t: t and next_text in t)

        if next_link:
            href = getattr(next_link, "get", lambda k: None)("href")
            # For Sumifu, pagination might be javascript post or URL part
            # Based on docs: /pro/ca_0_001/30_2/
            if href and href != "#" and not href.startswith(JAVASCRIPT_PREFIX):
                joined_url = urllib.parse.urljoin(self.BASE_URL, href)
                if JAVASCRIPT_PREFIX not in joined_url and VOID_0 not in joined_url:
                    return joined_url
        return ""


    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # 1. Scraping basic labels
        
        item.propertyName = self._parsePropertyName(response)
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
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.tochikenri = self._parseTochikenri(response)
        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        item.tatemonoMenseki = self._parseTatemonoMenseki(response)
        
        # Specific fields in subclasses
        self._set_type_specific_fields(item, response)
            
        # Common fields from base (already refactored to return values in base)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)
        
        item.address1 = self._parseAddress1(response)
        item.address2 = self._parseAddress2(response)
        item.address3 = self._parseAddress3(response)
        
        item.hikiwatashi = self._parseHikiwatashi(response)
        item.genkyo = self._parseGenkyo(response)
        item.torihiki = self._parseTorihiki(response)
        item.biko = self._parseBiko(response)
        
        # Traffic
        traffic_lines = self._parseTrafficLines(response)
        item.railwayCount = len(traffic_lines)
        traffic_str = "  ".join(traffic_lines)
        self._populateTraffic(item, traffic_str)

        return item

    def _yield_val_from_specs(self, specs):
        return (
            specs.get("表面利回り")
            or specs.get("利回り")
            or specs.get("想定利回り")
            or specs.get("予定利回り")
            or specs.get("実質利回り")
            or specs.get("満室想定利回り")
            or ""
        )

    def _yield_val_from_dom(self, response):
        # Sumifu invest details put yield in dt/dd + span.info-text-yield.
        for dt in response.find_all("dt"):
            key = dt.get_text(" ", strip=True)
            if "利回り" not in key:
                continue
            dd = dt.find_next_sibling("dd")
            if dd:
                return dd.get_text(" ", strip=True)
        span = response.select_one("span.info-text-yield")
        if span:
            return span.get_text(" ", strip=True)
        return ""

    def _decimal_from_yield_str(self, yield_val):
        if not yield_val or not isinstance(yield_val, str):
            return Decimal(0)
        try:
            m = re.search(r"([\d\.]+)", yield_val.replace("%", ""))
            if m:
                return Decimal(m.group(1))
        except (ValueError, TypeError, ArithmeticError):
            pass
        return Decimal(0)

    def _parseGrossYield(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        yield_val = self._yield_val_from_specs(target_specs)
        if not yield_val and response is not None:
            yield_val = self._yield_val_from_dom(response)
        return self._decimal_from_yield_str(yield_val)

    def _rent_val_from_specs(self, specs):
        return (
            specs.get("想定年商")
            or specs.get("想定年間収入")
            or specs.get("年間想定賃料")
            or specs.get("満室時想定年収")
            or specs.get("年間予定賃料収入")
            or specs.get("満室想定年額賃料")
            or specs.get("年収")
            or ""
        )

    def _rent_val_from_dom(self, response):
        for dt in response.find_all("dt"):
            key = dt.get_text(" ", strip=True)
            if any(tok in key for tok in ("年間想定", "想定年", "年額賃料", "年間収入")):
                dd = dt.find_next_sibling("dd")
                if dd:
                    return dd.get_text(" ", strip=True)
        for p in response.find_all("p"):
            t = p.get_text(" ", strip=True)
            if "満室想定年額" in t or "想定年額賃料" in t:
                return t
        return ""

    def _parseAnnualRent(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        rent_val = self._rent_val_from_specs(target_specs)
        if not rent_val and response is not None:
            rent_val = self._rent_val_from_dom(response)
        return converter.parse_price(rent_val) if rent_val else 0

    def _parseMonthlyRent(self, response, _specs=None):
        annual_rent = self._parseAnnualRent(response)
        return (annual_rent // 12) if annual_rent else 0

    def _parseCurrentStatus(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("現況", "")

    def _kouzou_from_spans(self, spans):
        if len(spans) >= 2:
            return spans[1].get_text(strip=True)
        if len(spans) == 1:
            text = spans[0].get_text(strip=True)
            m = re.search(r'建て(.+)$', text)
            if m:
                return m.group(1).strip()
        return None

    def _kouzou_from_combined_tag(self, combined_tag):
        if hasattr(combined_tag, "find_all"):
            spans = combined_tag.find_all("span")
            from_spans = self._kouzou_from_spans(spans)
            if from_spans:
                return from_spans
            combined = combined_tag.get_text(separator='\n', strip=True)
            lines = combined.split('\n')
            if len(lines) >= 2:
                return lines[1].strip()
            return None
        text = str(combined_tag).strip()
        m = re.search(r'建て(.+)$', text)
        if m:
            return m.group(1).strip()
        lines = [line.strip() for line in text.split() if line.strip()]
        if len(lines) >= 2:
            return lines[1]
        return text

    def _parseKouzou(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        kouzou = target_specs.get("構造", "")
        if kouzou:
            return kouzou

        # Compatibility with old specialized extraction
        specs_tags = self._get_specs(response)
        combined_tag = specs_tags.get(
            "所在階構造",
            specs_tags.get("所在階\n構造", specs_tags.get("階数構造", specs_tags.get("階数\n構造"))),
        )
        if combined_tag:
            parsed = self._kouzou_from_combined_tag(combined_tag)
            if parsed:
                return parsed
        return ""



    def _parseChikunengetsuStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("築年月", "")

    def _parseChikunengetsu(self, response, _specs=None):
        chikunengetsu_str = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(chikunengetsu_str) if chikunengetsu_str else None

    def _parseKenpeiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get(LABEL_KENPEI_YOUSEKI, target_specs.get("建ぺい率", ""))

    def _parseKenpei(self, response, _specs=None):
        kenpei_str = self._parseKenpeiStr(response)
        if kenpei_str: 
            k, _ = self._parseKenpeiYousekiText(kenpei_str)
            if k is not None: return k
            m = DIGIT_REGEX.search(kenpei_str)
            if m: return int(m.group(1))
        return None

    def _parseYousekiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get(LABEL_KENPEI_YOUSEKI, target_specs.get("容積率", ""))

    def _parseYouseki(self, response, _specs=None):
        youseki_str = self._parseYousekiStr(response)
        if youseki_str: 
            _, y = self._parseKenpeiYousekiText(youseki_str)
            if y is not None: return y
            m = DIGIT_REGEX.search(youseki_str)
            if m: return int(m.group(1))
        return None

    def _parseYoutoChiiki(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("用途地域", "") 

    def _parseTochikenri(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("土地権利", "")

    def _parseTochiMensekiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("土地面積", "")

    def _parseTochiMenseki(self, response, _specs=None):
        land_area = self._parseTochiMensekiStr(response)
        if land_area:
             try: return Decimal(str(converter.parse_menseki(land_area)))
             except Exception: pass
        return Decimal(0)

    def _parseTatemonoMensekiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("建物面積", target_specs.get("専有面積", target_specs.get("延床面積", "")))

    def _parseTatemonoMenseki(self, response, _specs=None):
        bldg_area = self._parseTatemonoMensekiStr(response)
        if bldg_area:
             try: return Decimal(str(converter.parse_menseki(bldg_area)))
             except Exception: pass
        return Decimal(0)
    
    def _parse_type_specific_fields(self, item, response):
        """Override in subclass"""
        pass

    def _set_type_specific_fields(self, item, response):
        """Override in subclass for type-specific field parsing"""
        self._parse_type_specific_fields(item, response)


class SumifuInvestmentKodateParser(SumifuInvestmentParserBase, KodateParserBase):

    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    def _parseMadori(self, response, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        return target_specs.get("間取り", "") or target_specs.get("間取", "") or super()._parseMadori(response, target_specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        return target_specs.get("構造", "") or super()._parseKouzou(response, target_specs)

    def _parseKenpei(self, response, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseYouseki(self, response, specs=None):
        return super()._parseYouseki(response, specs)

    def _parseRights(self, response, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        return target_specs.get("権利", "") or target_specs.get("土地権利", "") or super()._parseRights(response, target_specs)

    def _parseYoutoChiiki(self, response, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        return target_specs.get("用途地域", "") or super()._parseYoutoChiiki(response, target_specs)

    """Parser for Sumifu investment kodate (戸建て) properties"""
    
    def createEntity(self) -> models.Model:
        return SumifuInvestmentKodate()
    
    def _parse_type_specific_fields(self, item, response):
        """Kodate-specific fields"""
        item.propertyType = "Kodate"
        # Kodate-specific fields can be added here if needed


class SumifuInvestmentApartmentParser(SumifuInvestmentParserBase, InvestmentParserBase):

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

    """Parser for Sumifu investment apartment (アパート) properties"""
    
    def createEntity(self) -> models.Model:
        return SumifuInvestmentApartment()
    
    def _parse_type_specific_fields(self, item, response):
        """Apartment-specific fields"""
        item.propertyType = "Apartment"
        
        item.soukosuStr = self._parseSoukosuStr(response)
        item.soukosu = self._parseSouKosu(response)
            
        item.setsudou = self._parseSetsudou(response)
        item.chimoku = self._parseChimoku(response)
    
    def _parseSoukosuStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("総戸数", "")

    def _parseSouKosu(self, response, _specs=None):
        u_val = self._parseSoukosuStr(response)
        if u_val:
            try:
                m = DIGIT_REGEX.search(u_val)
                if m:
                    return int(m.group(1))
            except Exception:
                pass
        return 0

    _parseSoukosu = _parseSouKosu


    def _getChimokuChiseiText(self, item, value):
        item.chimokuChisei = value
        item.chimoku = item.chimokuChisei.split("/")[0]
        item.chisei=""
        if (len(item.chimokuChisei.split("/"))>=2):
            item.chisei = item.chimokuChisei.split("/")[len(item.chimokuChisei.split("/"))-1]




    # Combined into definition at line 110






class SumifuMansionParser(SumifuParser, MansionParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseKouzou(self, response, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        return target_specs.get("構造", "") or super()._parseKouzou(response, target_specs)

    def _parseFloor(self, response, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        return target_specs.get("階数", "") or target_specs.get("所在階", "") or super()._parseFloor(response, target_specs)

    def _parseSouKosu(self, response, specs=None):
        target_specs = specs or self._get_specs(response)
        val = target_specs.get("総戸数", "")
        if val:
            m = DIGIT_REGEX.search(val)
            return int(m.group(1)) if m else None
        return super()._parseSouKosu(response, target_specs)

    def _parseManagementFee(self, response, specs=None):
        target_specs = specs or self._get_specs(response)
        val = target_specs.get("管理費", "") or target_specs.get("管理費等", "")
        return converter.parse_yen(val) if val and 'converter' in globals() else super()._parseManagementFee(response, target_specs)

    def _parseReserveFund(self, response, specs=None):
        target_specs = specs or self._get_specs(response)
        val = target_specs.get("修繕積立金", "")
        return converter.parse_yen(val) if val and 'converter' in globals() else super()._parseReserveFund(response, target_specs)

    def _parseKenpei(self, response, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseYouseki(self, response, specs=None):
        return super()._parseYouseki(response, specs)

    property_type = 'mansion'

    def createEntity(self):
        return SumifuMansion()

    def getRegionXpath(self):
        return self.selectors.get('region_xpath')

    def getAreaXpath(self):
        return self.selectors.get('area_xpath')

    # Removed MAPPING to follow 1-item-per-method rule

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        item.madori = self._parseMadori(response)
        item.senyuMensekiStr = self._parseSenyuMensekiStr(response)
        item.senyuMenseki = self._parseSenyuMenseki(response)
        item.kaisu = self._parseKaisu(response)
        item.kouzou = self._parseKouzou(response)
        
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        item.kyutaishin = self._parseKyutaishin(response)

        item.balconyMensekiStr = self._parseBalconyMensekiStr(response)
        item.balconyMenseki = self._parseBalconyMenseki(response)
        item.senyouNiwaMenseki = self._parseSenyouNiwaMenseki(response)
        item.roofBalconyMenseki = self._parseRoofBalconyMenseki(response)
        
        item.saikou = self._parseSaikou(response)
        item.kadobeya = self._parseKadobeya(response)
        
        item.soukosuStr = self._parseSoukosuStr(response)
        item.soukosu = self._parseSouKosu(response)
        
        item.kanriKeitai = self._parseKanriKeitai(response)
        item.kanriKaisya = self._parseKanriKaisya(response)
        item.kanriKeitaiKaisya = self._parseKanriKeitaiKaisya(response)
        
        item.kanrihiStr = self._parseKanrihiStr(response)
        item.kanrihi = self._parseKanrihi(response)
        
        item.syuzenTsumitateStr = self._parseSyuzenTsumitateStr(response)
        item.syuzenTsumitate = self._parseSyuzenTsumitate(response)

        item.bunjoKaisya = self._parseBunjoKaisya(response)
        item.sekouKaisya = self._parseSekouKaisya(response)
        
        # Floor derived
        item.kaisuStr = self._parseKaisuStr(response)
        item.floorType_kai = self._parseFloorTypeKai(response)
        item.floorType_chijo = self._parseFloorTypeChijo(response)
        item.floorType_chika = self._parseFloorTypeChika(response)
        
        # Structure derived
        item.floorType_kouzou = self._parseFloorTypeKouzou(response)
        
        # Metrics
        item.kanrihi_p_heibei = self._calculateKanrihiPerHeibei(response)
        item.syuzenTsumitate_p_heibei = self._calculateSyuzenTsumitatePerHeibei(response)

        # Universal fields from base (hikiwatashi, genkyo, tochikenri, torihiki etc.)
        item.hikiwatashi = self._parseHikiwatashi(response)
        item.genkyo = self._parseGenkyo(response)
        item.tochikenri = self._parseTochikenri(response)
        item.torihiki = self._parseTorihiki(response)
        item.biko = self._parseBiko(response)
        
        # Mansion specific assignments to ensure they are set
        item.saikouKadobeya = f"{self._parseSaikou(response) or ''} / {self._parseKadobeya(response) or ''}"
        item.kanriKeitaiKaisya = (self._parseKanriKeitaiKaisya(response) or "").replace("\n", " / ")

        return item

    def _parseMadori(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("間取り", "")
        if not val and self.selectors:
            sel = self.selectors.get('madori')
            if sel:
                m_tag = response.select_one(sel)
                if m_tag:
                    val = m_tag.get_text(strip=True)
        return val

    def _senyu_from_specs(self, specs):
        val = specs.get("専有面積", "") or ""
        if val:
            return val
        for key, value in specs.items():
            if "専有面積" in str(key):
                return value
        return ""

    def _senyu_from_selector(self, response):
        if not self.selectors:
            return ""
        sel = self.selectors.get('senyuMenseki')
        if not sel:
            return ""
        s_tag = response.select_one(sel)
        if s_tag:
            return s_tag.get_text(strip=True)
        return ""

    def _senyu_from_summary_chip(self, response):
        # 2021+ detail layout: summary chips like "専有面積66.51m² （壁芯)"
        for span in response.select("span.text"):
            text = span.get_text(" ", strip=True)
            if "専有面積" in text:
                return text
        return ""

    def _parseSenyuMensekiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return (
            self._senyu_from_specs(target_specs)
            or self._senyu_from_selector(response)
            or self._senyu_from_summary_chip(response)
        )

    def _parseSenyuMenseki(self, response, _specs=None):
        senyu_menseki_str = self._parseSenyuMensekiStr(response)
        if senyu_menseki_str:
            return converter.parse_menseki(senyu_menseki_str)
        return Decimal(0)

    # Kaisu/Kouzou logic inherited from base is now robust enough.
    # Removed redundant overrides here to use base implementation.

    def _parseChikunengetsuStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("築年月", "")

    def _parseChikunengetsu(self, response, _specs=None):
        chikunengetsu_str = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(chikunengetsu_str) if chikunengetsu_str else None

    def _parseKyutaishin(self, response, _specs=None):
        chikunengetsu = self._parseChikunengetsu(response)
        if chikunengetsu and chikunengetsu < datetime.date(1982, 1, 1):
            return 1
        return 0

    def _parseBalconyMensekiStr(self, response, _specs=None):
        td = self._getValueFromTable(response, "バルコニー", partial_match=True)
        return self._getText(td)

    def _parseBalconyMenseki(self, response, _specs=None):
        balcony_menseki_str = self._parseBalconyMensekiStr(response)
        if balcony_menseki_str and balcony_menseki_str != "-":
            # Just take the first area if multiple
            m = re.search(r'(\d+(\.\d+)?)', balcony_menseki_str)
            if m: return Decimal(m.group(1))
        return Decimal(0)

    def _parseSenyouNiwaMenseki(self, response, _specs=None):
        balcony_menseki_str = self._parseBalconyMensekiStr(response)
        if balcony_menseki_str and "専用庭面積" in balcony_menseki_str:
            try:
                return converter.parse_menseki(balcony_menseki_str.split("専用庭面積")[1])
            except Exception:
                pass
        return Decimal(0)

    def _parseRoofBalconyMenseki(self, response, _specs=None):
        balcony_menseki_str = self._parseBalconyMensekiStr(response)
        if balcony_menseki_str and "ルーフバルコニー面積" in balcony_menseki_str:
            try:
                return converter.parse_menseki(balcony_menseki_str.split("ルーフバルコニー面積")[1])
            except Exception:
                pass
        return Decimal(0)

    def _parseSaikou(self, response, _specs=None):
        td = self._getValueFromTable(response, "採光") or self._getValueFromTable(response, "向き")
        if td:
             val = self._getText(td)
             temp = re.split(u'/|／|\n', val)
             return temp[0].strip()
        return ""

    def _parseKadobeya(self, response, _specs=None):
        td = self._getValueFromTable(response, "採光") or self._getValueFromTable(response, "向き")
        if td:
             val = self._getText(td)
             temp = re.split(u'/|／|\n', val)
             if len(temp) >= 2: return temp[1].strip()
        return ""

    def _parseSoukosuStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("総戸数", "")

    def _parseSouKosu(self, response, _specs=None):
        soukosu_str = self._parseSoukosuStr(response)
        return converter.parse_numeric(soukosu_str) if soukosu_str else 0

    _parseSoukosu = _parseSouKosu

    def _parseKanriKeitaiKaisya(self, response, _specs=None):
        td = self._getValueFromTable(response, "管理方式", partial_match=True) or \
             self._getValueFromTable(response, "管理形態", partial_match=True) or \
             self._getValueFromTable(response, "管理会社", partial_match=True)
        return self._getText(td)

    def _parseKanriKeitai(self, response, _specs=None):
        val = self._parseKanriKeitaiKaisya(response)
        if val:
             temp = val.split("\n")
             return temp[0].strip()
        return ""

    def _parseKanriKaisya(self, response, _specs=None):
        val = self._parseKanriKeitaiKaisya(response)
        if val:
             temp = val.split("\n")
             return temp[-1].strip()
        return ""

    # _parseKaisuStr is inherited from SumifuParser (base) which extracts location floor.
    # However, for Mansion, we might want to ensure we get the floor number correctly.
    # Base _parseKaisuStr:
    #     val = self._parseKaisuRaw(response)
    #     if "・" in val: return val.split("・")[0].strip()
    #     return val
    # This works for "3階・RC造" -> "3階".
    # But Sumifu site often has "42階部分／地上49階地下3階建て鉄筋コンクリート造"
    # Base _parseKaisuStr would return the whole thing or fail to split if delimiter is different.
    
    def _parseKaisuStr(self, response, _specs=None):
        # Override to handle Sumifu Mansion specifics if base is insufficient
        # But let's check base implementation again.
        # It splits on "・". Sumifu often uses "／" or "建て".
        val = self._parseKaisuRaw(response)
        if not val: return ""
        
        # Clean up common patterns
        # Pattern: "X階部分／地上Y階..."
        if "／" in val:
            val = val.split("／")[0].strip()
        
        # Pattern: "X階・..."
        if "・" in val:
            val = val.split("・")[0].strip()
            
        return val

    def _parseKanrihiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("管理費(月額)", target_specs.get("管理費", ""))
        return val if val and val != "￥" else ""

    def _parseKanrihi(self, response, _specs=None):
        kanrihi_str = self._parseKanrihiStr(response)
        if not kanrihi_str: return 0
        if "万" in kanrihi_str: return converter.parse_price(kanrihi_str)
        return converter.parse_yen(kanrihi_str)

    def _parseSyuzenTsumitateStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("修繕積立金(月額)", target_specs.get("修繕積立金", ""))
        return val if val and val != "￥" else ""

    def _parseSyuzenTsumitate(self, response, _specs=None):
        syuzen_tsumitate_str = self._parseSyuzenTsumitateStr(response)
        if not syuzen_tsumitate_str: return 0
        if "万" in syuzen_tsumitate_str: return converter.parse_price(syuzen_tsumitate_str)
        return converter.parse_yen(syuzen_tsumitate_str)

    def _parseBunjoKaisya(self, response, _specs=None):
        td = self._getValueFromTable(response, "新築時売主")
        return self._getText(td)

    def _parseSekouKaisya(self, response, _specs=None):
        td = self._getValueFromTable(response, "施工会社")
        return self._getText(td)

    # _parseKaisuStr is now defined above to return Location Text.
    # Previous implementation returned Building Height. 
    # If we need Building Height, we should parse it separately, but schema doesn't seem to imply kaisuStr is building height anymore for Mansion?
    # Actually SumifuMansion has floorType_chijo/chika which capture building height.
    
    def _parseFloorTypeKai(self, response, _specs=None):
        return self._parseKaisu(response) # Now returns Int

    def _parseFloorTypeChijo(self, response, _specs=None):
        raw = self._parseKaisuRaw(response)
        if raw:
             m = re.search(r'地上(\d+)階', raw)
             if m: return int(m.group(1))
        return None

    def _parseFloorTypeChika(self, response, _specs=None):
        raw = self._parseKaisuRaw(response)
        if raw:
             m = re.search(r'地下(\d+)階', raw)
             if m: return int(m.group(1))
        return None

    def _parseFloorTypeKouzou(self, response, _specs=None):
        kouzou = self._parseKouzou(response)
        return kouzou if kouzou else ""

    def _calculateKanrihiPerHeibei(self, response):
        kanrihi = self._parseKanrihi(response)
        senyu_menseki = self._parseSenyuMenseki(response)
        if not kanrihi or not senyu_menseki: return 0
        from decimal import ROUND_HALF_UP
        val = (Decimal(str(kanrihi)) / Decimal(str(senyu_menseki))).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        return min(val, Decimal('9999.999'))

    def _calculateSyuzenTsumitatePerHeibei(self, response):
        syuzen_tsumitate = self._parseSyuzenTsumitate(response)
        senyu_menseki = self._parseSenyuMenseki(response)
        if not syuzen_tsumitate or not senyu_menseki: return 0
        from decimal import ROUND_HALF_UP
        val = (Decimal(str(syuzen_tsumitate)) / Decimal(str(senyu_menseki))).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        return min(val, Decimal('9999.999'))

class SumifuTochiParser(SumifuParser, TochiParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseMaguchi(self, response, specs=None):
        return super()._parseMaguchi(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseRights(self, response, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        return target_specs.get("権利", "") or target_specs.get("土地権利", "") or super()._parseRights(response, target_specs)

    property_type = 'tochi'
    
    def getRegionXpath(self):
        return self.selectors.get('region_xpath')

    def getAreaXpath(self):
        return self.selectors.get('area_xpath')

    def getPropertyListXpath(self):
        return self.selectors.get('property_list_xpath')

    def createEntity(self):
        return  SumifuTochi()

    # Removed MAPPING to follow 1-item-per-method rule

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.kenchikuJoken = self._parseKenchikuJoken(response)
        
        item.hikiwatashi = self._parseHikiwatashi(response)
        item.genkyo = self._parseGenkyo(response)
        item.tochikenri = self._parseTochikenri(response)
        item.torihiki = self._parseTorihiki(response)

        item.chimoku = self._parseChimoku(response)
        item.chisei = self._parseChisei(response)
        item.chimokuChisei = self._parseChimokuChisei(response)
        
        item.setsudou = self._parseSetsudou(response)
        
        item.douro = self._parseDouro(response)
        item.douroMuki = self._parseDouroMuki(response)
        item.douroHaba = self._parseDouroHaba(response)
        item.douroKubun = self._parseDouroKubun(response)
        item.setsumen = self._parseSetsumen(response)
        
        item.kenpei = self._parseKenpei(response)
        item.youseki = self._parseYouseki(response)
        item.kenpeiYousekiStr = self._parseKenpeiYousekiStr(response)
        
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.chiikiChiku = self._parseChiikiChiku(response)
        item.boukaChiiki = self._parseBoukaChiiki(response)
        item.sonotaChiiki = self._parseSonotaChiiki(response)
        
        item.kuiki = self._parseKuiki(response)
        item.saikenchiku = self._parseSaikenchiku(response)
        item.kokudoHou = self._parseKokudoHou(response)

        # 統一土地評価フィールドのパース ＆ 代入
        import re
        if item.setsumen is not None:
            item.maguchiStr = str(item.setsumen)
            m = re.search(r'(\d+(?:\.\d+)?)', item.maguchiStr)
            if m:
                item.maguchi = Decimal(m.group(1))
                
        if item.douroHaba is not None:
            item.roadWidthStr = str(item.douroHaba)
            m = re.search(r'(\d+(?:\.\d+)?)', item.roadWidthStr)
            if m:
                item.roadWidth = Decimal(m.group(1))
                
        if item.douroMuki:
            item.roadDirection = item.douroMuki
            
        if item.douroKubun:
            item.roadType = item.douroKubun
            
        if item.setsudou:
            structure_match = re.search(r'(角地|二方|三方|四方|敷延|袋小路|中間地|両面道路)', str(item.setsudou))
            item.roadStructure = structure_match.group(1) if structure_match else "中間地"
        else:
            item.roadStructure = "中間地"
            
        if item.tochiMenseki and item.maguchi and item.maguchi > 0:
            item.okuyuki = round(item.tochiMenseki / item.maguchi, 2)
            item.okuyukiStr = f"{item.okuyuki}m"

        return item

    def _parseTochiMensekiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("土地面積", "")
        if not val or val == "-":
            res = self._getValueByLabel(response, "土地面積")
            if res: val = res.get_text(strip=True).replace("土地面積", "")
        return val

    def _parseTochiMenseki(self, response, _specs=None):
        tochi_menseki_str = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(tochi_menseki_str) if tochi_menseki_str else Decimal(0)

    def _parseKenchikuJoken(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("建築条件", "")

    def _parseChimoku(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("地目", target_specs.get("地勢", target_specs.get("地目地勢", "")))
        if not val or val == "-":
            return ""
        # If combined like "宅地平坦", it's hard to split strictly without a list.
        # But usually the first few chars are chimoku.
        potential = ["宅地", "田", "畑", "山林", "雑種地", "原野"]
        for p in potential:
            if val.startswith(p):
                return p
        return val # Fallback

    def _parseSetsudou(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("接道状況", "")

    def _parseKenpei(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        ky_str = target_specs.get(LABEL_KENPEI_YOUSEKI, target_specs.get("建ぺい率", ""))
        k, _ = self._parseKenpeiYousekiText(ky_str)
        if k is not None:
            return k
        # Fallback to direct number search in string
        if ky_str:
            m = DIGIT_REGEX.search(ky_str)
            if m: return int(m.group(1))
        return None

    def _parseYouseki(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        ky_str = target_specs.get(LABEL_KENPEI_YOUSEKI, target_specs.get("容積率", ""))
        _, y = self._parseKenpeiYousekiText(ky_str)
        if y is not None:
            return y
        # Fallback to direct number search in string
        if ky_str:
            m = re.search(r'容積率\D*(\d+)', ky_str) or DIGIT_REGEX.search(ky_str)
            if m: return int(m.group(len(m.groups())))
        return None

    def _parseYoutoChiiki(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("用途地域", "")

    def _parseKokudoHou(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("国土法", "")
    
    def _parseChisei(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("地勢", target_specs.get("地目地勢", ""))
        if not val or val == "-":
            return ""
        
        # If extracted from combined "地目地勢", try to remove chimoku
        if "地目地勢" in target_specs:
            chimoku = self._parseChimoku(response)
            if val and isinstance(val, str) and chimoku and isinstance(chimoku, str) and chimoku != "-" and chimoku in val:
                val = val.replace(chimoku, "").strip()
        
        return val if val else ""

    def _parseChimokuChisei(self, response, _specs=None):
        # Fallback or combination
        c = self._parseChimoku(response)
        s = self._parseChisei(response)
        return f"{c}・{s}" if c and s else (c or s or "")

    def _parseKenpeiYousekiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get(LABEL_KENPEI_YOUSEKI, "")
        if not val:
            k = target_specs.get("建ぺい率", "")
            y = target_specs.get("容積率", "")
            if k and y: val = f"建ぺい率{k} 容積率{y}"
            elif k or y: val = k or y
        return val if val else ""

    def _parseKuiki(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("都市計画", "")

    def _parseSaikenchiku(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get(LABEL_SAIKENCHIKU_FUKA, target_specs.get("再建築", ""))
        if not val:
            # Check other likely fields where this info might hide
            region = target_specs.get("地域・地区", target_specs.get("地域地区", target_specs.get("用途地域", "")))
            if region and LABEL_SAIKENCHIKU_FUKA in region:
                val = LABEL_SAIKENCHIKU_FUKA
        return val if val else ""

class SumifuKodateParser(SumifuParser, KodateParserBase):
    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseRights(self, response, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        return target_specs.get("権利", "") or target_specs.get("土地権利", "") or super()._parseRights(response, target_specs)

    property_type = 'kodate'
    
    def getRegionXpath(self):
        return self.selectors.get('region_xpath')

    def getAreaXpath(self):
        return self.selectors.get('area_xpath')

    def getPropertyListXpath(self):
        return self.selectors.get('property_list_xpath')

    def createEntity(self):
        return  SumifuKodate()

    # Removed MAPPING to follow 1-item-per-method rule

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        
        item.tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        item.tatemonoMenseki = self._parseTatemonoMenseki(response)
        
        item.madori = self._parseMadori(response)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        
        item.kenpei = self._parseKenpei(response)
        item.youseki = self._parseYouseki(response)
        item.kenpeiYousekiStr = self._parseKenpeiYousekiStr(response)
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.yousekiStr = self._parseYousekiStr(response)
        
        item.kaisuKouzou = self._parseKaisuKouzou(response)
        item.kaisu = self._parseKaisu(response)
        item.kouzou = self._parseKouzou(response)
        item.kaisuStr = self._parseKaisuStr(response)
        
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.chiikiChiku = self._parseChiikiChiku(response)
        item.boukaChiiki = self._parseBoukaChiiki(response)
        item.sonotaChiiki = self._parseSonotaChiiki(response)
        
        item.tyusyajo = self._parseTyusyajo(response)
        item.kenchikuJoken = self._parseKenchikuJoken(response)
        item.kokudoHou = self._parseKokudoHou(response)
        
        item.chimoku = self._parseChimoku(response)
        item.chisei = self._parseChisei(response)
        item.chimokuChisei = self._parseChimokuChisei(response)
        
        item.setsudou = self._parseSetsudou(response)
        item.douro = self._parseDouro(response)
        item.douroMuki = self._parseDouroMuki(response)
        item.douroHaba = self._parseDouroHaba(response)
        item.douroKubun = self._parseDouroKubun(response)
        item.setsumen = self._parseSetsumen(response)

        item.hikiwatashi = self._parseHikiwatashi(response)
        item.genkyo = self._parseGenkyo(response)
        item.tochikenri = self._parseTochikenri(response)
        item.torihiki = self._parseTorihiki(response)
        item.kuiki = self._parseKuiki(response)
        item.saikenchiku = self._parseSaikenchiku(response)

        return item

    def _parseTochiMensekiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("土地面積", "")
        if not val or val == "-":
            res = self._getValueByLabel(response, "土地面積")
            if res: val = res.get_text(strip=True).replace("土地面積", "")
        return val

    def _parseTochiMenseki(self, response, _specs=None):
        tochi_menseki_str = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(tochi_menseki_str) if tochi_menseki_str else Decimal(0)

    def _parseTatemonoMensekiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("建物面積", "")
        if not val or val == "-":
            res = self._getValueByLabel(response, "建物面積")
            if res: val = res.get_text(strip=True).replace("建物面積", "")
        return val

    def _parseTatemonoMenseki(self, response, _specs=None):
        tatemono_menseki_str = self._parseTatemonoMensekiStr(response)
        return converter.parse_menseki(tatemono_menseki_str) if tatemono_menseki_str else Decimal(0)

    def _parseMadori(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        val = target_specs.get("間取り", "")
        if not val or val == "-":
            res = self._getValueByLabel(response, "間取り")
            if res: val = res.get_text(strip=True).replace("間取り", "")
        return val

    def _parseChikunengetsuStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("築年月", "")

    def _parseHikiwatashi(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("引渡時期", "")

    def _parseGenkyo(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("現況", "")

    def _parseTochikenri(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("土地権利", "")

    def _parseTorihiki(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("取引態様", "")

    def _parseKokudoHou(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("国土法", "")

    def _parseSetsudou(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("接道状況", "")

    def _parseKenpeiYousekiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        k = target_specs.get("建ぺい率", "")
        y = target_specs.get("容積率", "")
        if k and y:
            return f"建ぺい率{k} 容積率{y}"
        return k or y

    def _parseKenpeiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("建ぺい率", "")
    
    def _parseYousekiStr(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("容積率", "")

    def _parseKuiki(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("都市計画", "")

    def _parseSaikenchiku(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        # Check '地域・地区' for '再建築不可' as seen in Error HTML
        val = target_specs.get(LABEL_SAIKENCHIKU_FUKA, "")
        if not val:
            region = target_specs.get("地域・地区", "") or target_specs.get("地域地区", "")
            if LABEL_SAIKENCHIKU_FUKA in region:
                val = LABEL_SAIKENCHIKU_FUKA
        return val if val else ""

    def _parseSpecsCombined(self, response, key_start):
        """Helper to find values where keys are concatenated like '階数構造'"""
        specs = self._get_specs(response)
        for key, val in specs.items():
            if key.startswith(key_start) or key_start in key:
                  return val
        return ""

    def _parseKaisuKouzou(self, response, _specs=None):
        return self._parseSpecsCombined(response, "階数") or ""

    def _parseKaisu(self, response, _specs=None):
        # Key is '階数構造' -> "地上2階建て木造"
        val = self._parseSpecsCombined(response, "階数")
        if not val: return None
        # Extract number "2" from "地上2階建て"
        match = re.search(r'(\d+)階', val)
        return int(match.group(1)) if match else None

    def _parseKouzou(self, response, _specs=None):
        # Key '階数構造' -> "地上2階建て木造"
        val = self._parseSpecsCombined(response, "階数")
        if not val: return ""
        # Structure usually comes after floor or "木造" etc is distinct
        # Simple extraction logic: remove floor info?
        # Or simply return the whole string as kouzou if strict extraction isn't possible?
        # Model requires TextField. "木造" is what we want.
        # "地上2階建て木造" -> "木造"
        # Known structures
        structures = ["木造", "鉄骨", "RC", "SRC", "鉄筋コンクリート"]
        for s in structures:
            if s in val:
                return s
        return val # Fallback

    def _parseChimoku(self, response, _specs=None):
        # Key '地目地勢' -> "宅地平坦"
        val = self._parseSpecsCombined(response, "地目")
        if not val: return ""
        # Hard to split without delimiter.
        # But usually '宅地' is chimoku.
        potential_chimoku = ["宅地", "田", "畑", "山林", "雑種地"]
        for c in potential_chimoku:
            if val.startswith(c):
                return c
        return val

    def _parseChisei(self, response, _specs=None):
         # Key '地目地勢' -> "宅地平坦"
        val = self._parseSpecsCombined(response, "地目")
        if not val: return ""
        # If extracts chimoku, remove it
        chimoku = self._parseChimoku(response)
        if val and isinstance(val, str) and chimoku and isinstance(chimoku, str) and chimoku != "-" and chimoku in val:
            val = val.replace(chimoku, "").strip()
        return val if val else ""

    def _parseChimokuChisei(self, response, _specs=None):
        c = self._parseChimoku(response)
        s = self._parseChisei(response)
        return f"{c}・{s}"

    def _parseChikunengetsu(self, response, _specs=None):
        chikunengetsu_str = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(chikunengetsu_str) if chikunengetsu_str else None

    def _parseKenpei(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        # Use simple key for Kodate
        k_str = target_specs.get("建ぺい率", "")
        if k_str:
            m = DIGIT_REGEX.search(k_str)
            return int(m.group(1)) if m else None
        return None

    def _parseYouseki(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        y_str = target_specs.get("容積率", "")
        if not y_str:
             return None
        m = DIGIT_REGEX.search(y_str)
        return int(m.group(1)) if m else None

    def _parseTyusyajo(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("駐車場", "")

    def _parseYoutoChiiki(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("用途地域", "")

    def _parseKenchikuJoken(self, response, specs=None):
        target_specs = specs if specs is not None else self._get_specs(response)
        return target_specs.get("建築条件", "")

    def _parseKaisuStr(self, response, _specs=None):
        # Use the kaisu (int) we parsed
        k = self._parseKaisu(response)
        return str(k) if k is not None else ""
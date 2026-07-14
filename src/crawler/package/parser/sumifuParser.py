# -*- coding: utf-8 -*-
from abc import abstractmethod
import sys
import unicodedata


from bs4 import BeautifulSoup
from package.models.sumifu import SumifuMansion, SumifuModel, SumifuTochi, SumifuKodate, SumifuInvestmentKodate, SumifuInvestmentApartment
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
    ReadPropertyNameException, SkipPropertyException
import logging
from package.utils.selector_loader import SelectorLoader
import lxml.html


class SumifuParser(ParserBase):
    property_type = ""
    BASE_URL='https://www.stepon.co.jp'

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('sumifu', self.property_type)

    
    def getCharset(self):
        return None  # Let BeautifulSoup/lxml detect or use chardet

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
                content_len = len(lxml.html.tostring(response))
                if content_len < 1000: # Threshold for suspicion
                    logging.warning(f"Suspiciously small content ({content_len} bytes) for {url}. Retrying with UTF-8.")
                    # Force UTF-8
                    return await super().getResponse(session, url, charset='utf-8')
            return response
        except Exception as e:
            logging.warning(f"Error in default getResponse for {url}: {e}. Retrying with UTF-8.")
            return await super().getResponse(session, url, charset='utf-8')


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
        xpath = self.selectors.get('property_list_xpath', u'')
        logging.info(f"[{self.property_type}] property_list_xpath: {xpath}")
        return xpath

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




    def _parseKenpeiYousekiText(self, text):
        # Example: 建ぺい率60% 容積率200%  OR  60%・200%  OR  60%/200%
        kenpei = None
        youseki = None
        if not text:
             return kenpei, youseki
             
        try:
            # Format 1: Explicit labels
            if "建ぺい率" in text or "容積率" in text:
                k_match = re.search(r'建ぺい率(\d+)%', text)
                if k_match:
                    kenpei = int(k_match.group(1))
                y_match = re.search(r'容積率(\d+)%', text)
                if y_match:
                    youseki = int(y_match.group(1))
            
            # Format 2: Split by delimiter (Investment style)
            # "60%・200%" or "60%/200%"
            else:
                 # Try splitting by common delimiters
                 parts = re.split(r'[・/]', text)
                 if len(parts) >= 2:
                      k_part = parts[0].strip()
                      y_part = parts[1].strip()
                      if "%" in k_part:
                           k_m = re.search(r'(\d+)', k_part)
                           if k_m: kenpei = int(k_m.group(1))
                      if "%" in y_part:
                           y_m = re.search(r'(\d+)', y_part)
                           if y_m: youseki = int(y_m.group(1))
        except:
            pass
        return kenpei, youseki

    def _parseChimoku(self, response):
        specs = self._get_specs(response)
        val = specs.get("地目", specs.get("地勢", ""))
        return val if val else "-"

    def _parseChisei(self, response):
        specs = self._get_specs(response)
        val = specs.get("地目", specs.get("地勢", ""))
        return val if val else "-"

    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        val = specs.get("接道状況", "")
        return val if val else "-"

    def _parseDouroInfo(self, response):
        specs = self._get_specs(response)
        val = specs.get("接道状況", "")
        return self._parseDouroText(val) if val else {}

    def _parseDouro(self, response):
        return self._parseDouroInfo(response).get('douro', '')

    def _parseDouroMuki(self, response):
        return self._parseDouroInfo(response).get('douroMuki', '')

    def _parseDouroHaba(self, response):
        return self._parseDouroInfo(response).get('douroHaba', None)

    def _parseDouroKubun(self, response):
        return self._parseDouroInfo(response).get('douroKubun', '')

    def _parseSetsumen(self, response):
        return self._parseDouroInfo(response).get('setsumen', None)

    def _parseChiikiChiku(self, response):
        specs = self._get_specs(response)
        return specs.get("地域地区", "-")

    def _parseBoukaChiiki(self, response):
        specs = self._get_specs(response)
        text = specs.get("地域地区", "")
        if text and '/' in text:
            return text.split('/')[0].strip()
        elif text and '｜' in text:
            return text.split('｜')[0].strip()
        else:
            return text if text else "-"

    def _parseSonotaChiiki(self, response):
        specs = self._get_specs(response)
        text = specs.get("地域地区", "")
        if text and '/' in text:
            return text.split('/')[1].strip()
        elif text and '｜' in text:
            return text.split('｜')[1].strip()
        else:
            return "-"

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
            except: pass
        
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
            except: pass
            
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
        # Traffic
        traffic_lines = self._parseTrafficLines(response)
        item.railwayCount = len(traffic_lines)
        traffic_str = "  ".join(traffic_lines)
        self._populateTraffic(item, traffic_str)

        item.biko = self._parseBiko(response)

        return item

    def _parsePriceStr(self, response):
        price_key = self.selectors.get('price_key', "価格")
        price_td = self._getValueFromTable(response, price_key)
        if price_td:
            price_text = price_td.get_text(strip=True)
            return re.split(r"\(", price_text)[0]
        
        price_selector = self.selectors.get('price')
        if price_selector:
            em = response.select_one(price_selector)
            if em: return em.get_text(strip=True)
        return ""

    def _parsePrice(self, response):
        price_str = self._parsePriceStr(response)
        return converter.parse_price(price_str)

    def _parseAddress(self, response):
        address_key = self.selectors.get('address_key', "所在地")
        address_td = self._getValueFromTable(response, address_key)
        if address_td:
            for btn in address_td.find_all("button"): btn.decompose()
            for br in address_td.find_all("br"): br.replace_with(" ")
            addr = address_td.get_text(strip=True)
            return re.sub(r'地図を開く$', '', addr).strip()
        
        address_selector = self.selectors.get('address')
        if address_selector:
            addr_el = response.select_one(address_selector)
            if addr_el: return addr_el.get_text(strip=True)
        return ""

    def _parseAddressComponents(self, response):
        addr = self._parseAddress(response)
        components = {'address1': '', 'address2': '', 'address3': ''}
        if not addr: return components
        pref, city, town = self._split_address(addr)
        components['address1'] = pref
        components['address2'] = city
        components['address3'] = town
        return components


    def _parseAddress1(self, response):
        return self._parseAddressComponents(response).get('address1', '')
    
    def _parseAddress2(self, response):
        return self._parseAddressComponents(response).get('address2', '')
        
    def _parseAddress3(self, response):
        return self._parseAddressComponents(response).get('address3', '')

    def _getValueFromTable(self, response: BeautifulSoup, title: str, partial_match: bool = False):
        """
        Overridden for Sumifu: use _scrape_to_dict and search with normalized keys.
        Handles labels with <br>, spaces, or extra characters.
        """
        def normalize(s):
            return s.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "").rstrip("：").rstrip(":")

        specs_tags = self._scrape_to_dict(response)
        target_norm = normalize(title)
        
        for key, tag in specs_tags.items():
            key_norm = normalize(key)
            if target_norm == key_norm or (partial_match and target_norm in key_norm):
                return tag
            # Additional check for common Sumifu labels that might be subset of title or vice versa
            if key_norm in target_norm:
                return tag
                
        return None

    def _parseHikiwatashi(self, response):
        td = self._getValueFromTable(response, "引渡時期")
        return td.get_text(strip=True) if td else ""

    def _parseGenkyo(self, response):
        td = self._getValueFromTable(response, "現況")
        return td.get_text(strip=True) if td else ""

    def _parseTochikenri(self, response):
        td = self._getValueFromTable(response, "土地権利")
        return td.get_text(strip=True) if td else ""

    def _parseTorihiki(self, response):
        td = self._getValueFromTable(response, "取引態様")
        return td.get_text(strip=True) if td else ""

    def _parseChikunengetsuStr(self, response):
        return self._getValueFromTable(response, "築年月", True)

    def _parseChikunengetsu(self, response):
        chikunengetsuStr = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(chikunengetsuStr) if chikunengetsuStr else None

    def _parseBiko(self, response):
        td = self._getValueFromTable(response, "備考")
        if td:
            val = td.get_text(strip=True)
            return converter.truncate_str(val, 2000).strip()
        return ""

    def _parseMadori(self, response):
        td = self._getValueFromTable(response, "間取り")
        return td.get_text(strip=True) if td else "-"

    def _parseTatemonoMensekiStr(self, response):
        td = self._getValueFromTable(response, "建物面積") or self._getValueFromTable(response, "専有面積")
        return td.get_text(strip=True) if td else ""

    def _parseTatemonoMenseki(self, response):
        tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        return converter.parse_menseki(tatemonoMensekiStr)

    def _parseTochiMensekiStr(self, response):
        td = self._getValueFromTable(response, "土地面積")
        return td.get_text(strip=True) if td else ""

    def _parseTochiMenseki(self, response):
        tochiMensekiStr = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(tochiMensekiStr)

    def _parseKouzou(self, response):
        td = self._getValueFromTable(response, "構造", partial_match=True)
        if td:
            val = td.get_text(strip=True)
            if "・" in val: return val.split("・")[-1].strip()
            return val
        return ""

    def _parseKaisuRaw(self, response):
        specs = self._get_specs(response)
        return specs.get("階数", specs.get("所在階", specs.get("所在階構造", "")))

    def _parseKaisuStr(self, response):
        val = self._parseKaisuRaw(response)
        if "・" in val:
            return val.split("・")[0].strip()
        return val

    def _parseKaisu(self, response):
        k_str = self._parseKaisuStr(response)
        if k_str:
             m = re.search(r'(\d+)', k_str)
             if m: return int(m.group(1))
        return None

    def _parseTrafficLines(self, response):
        transport_key = self.selectors.get('transport_key', "交通")
        transport_td = self._getValueFromTable(response, transport_key)
        if not transport_td: return []
        for br in transport_td.select("br"): br.replace_with("\n")
        full_text = transport_td.get_text().strip()
        return [line.strip() for line in full_text.split("\n") if line.strip()]

    def _parseRailwayCount(self, response):
        return len(self._parseTrafficLines(response))


        
class SumifuInvestmentParserBase(SumifuParser, InvestmentParser):
    """Base class for Sumifu investment property parsers"""
    property_type = 'investment'
    
    def __init__(self, params=None):
        super().__init__(params)
        
    def getCharset(self):
        return "utf-8"

    def getRegionXpath(self):
        return self.selectors.get('region_xpath')

    def getAreaXpath(self):
        return self.selectors.get('area_xpath')

    def getPropertyListXpath(self):
        return self.selectors.get('property_list_xpath')

    async def parsePropertyListPage(self, response: BeautifulSoup):
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
            if href and href != "#":
                if href.startswith("/"):
                    return "https://www.stepon.co.jp" + href
                return href
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

    def _parseGrossYield(self, response):
        specs = self._get_specs(response)
        yield_val = specs.get("表面利回り", specs.get("利回り", ""))
        if yield_val:
            try: return Decimal(yield_val.replace("%", "").strip())
            except: pass
        return Decimal(0)

    def _parseAnnualRent(self, response):
        specs = self._get_specs(response)
        rent_val = specs.get("想定年商", specs.get("想定年間収入", specs.get("年間想定賃料", "")))
        return converter.parse_price(rent_val) if rent_val else 0

    def _parseMonthlyRent(self, response):
        annualRent = self._parseAnnualRent(response)
        return (annualRent // 12) if annualRent else 0

    def _parseCurrentStatus(self, response):
        specs = self._get_specs(response)
        return specs.get("現況", "-")

    def _parseKouzou(self, response):
        specs = self._get_specs(response)
        kouzou = specs.get("構造", "")
        if kouzou: return kouzou
        
        # Compatibility with old specialized extraction
        specs_tags = self._scrape_to_dict(response)
        combined_tag = specs_tags.get("所在階構造", specs_tags.get("所在階\n構造", specs_tags.get("階数構造", specs_tags.get("階数\n構造"))))
        if combined_tag:
            spans = combined_tag.find_all("span")
            if len(spans) >= 2: return spans[1].get_text(strip=True)
            elif len(spans) == 1:
                text = spans[0].get_text(strip=True)
                m = re.search(r'建て(.+)$', text)
                if m: return m.group(1).strip()
            else:
                combined = combined_tag.get_text(separator='\n', strip=True)
                lines = combined.split('\n')
                if len(lines) >= 2: return lines[1].strip()
        return "-"

    def _parseChikunengetsuStr(self, response):
        specs = self._get_specs(response)
        return specs.get("築年月", "-")

    def _parseChikunengetsu(self, response):
        chikunengetsuStr = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(chikunengetsuStr) if chikunengetsuStr else None

    def _parseKenpeiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建ぺい率・容積率", specs.get("建ぺい率", ""))

    def _parseKenpei(self, response):
        kenpeiStr = self._parseKenpeiStr(response)
        if kenpeiStr: 
            k, _ = self._parseKenpeiYousekiText(kenpeiStr)
            if k is not None: return k
            m = re.search(r'(\d+)', kenpeiStr)
            if m: return int(m.group(1))
        return None

    def _parseYousekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建ぺい率・容積率", specs.get("容積率", ""))

    def _parseYouseki(self, response):
        yousekiStr = self._parseYousekiStr(response)
        if yousekiStr: 
            _, y = self._parseKenpeiYousekiText(yousekiStr)
            if y is not None: return y
            m = re.search(r'(\d+)', yousekiStr)
            if m: return int(m.group(1))
        return None

    def _parseYoutoChiiki(self, response):
        specs = self._get_specs(response)
        return specs.get("用途地域", "") 

    def _parseTochikenri(self, response):
        specs = self._get_specs(response)
        return specs.get("土地権利", "-")

    def _parseTochiMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("土地面積", "-")

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
    
    def _parse_type_specific_fields(self, item, response):
        """Override in subclass"""
        pass

    def _set_type_specific_fields(self, item, response):
        """Override in subclass for type-specific field parsing"""
        self._parse_type_specific_fields(item, response)


class SumifuInvestmentKodateParser(SumifuInvestmentParserBase):
    """Parser for Sumifu investment kodate (戸建て) properties"""
    
    def createEntity(self) -> models.Model:
        return SumifuInvestmentKodate()
    
    def _parse_type_specific_fields(self, item, response):
        """Kodate-specific fields"""
        item.propertyType = "Kodate"
        # Kodate-specific fields can be added here if needed


class SumifuInvestmentApartmentParser(SumifuInvestmentParserBase):
    """Parser for Sumifu investment apartment (アパート) properties"""
    
    def createEntity(self) -> models.Model:
        return SumifuInvestmentApartment()
    
    def _parse_type_specific_fields(self, item, response):
        """Apartment-specific fields"""
        item.propertyType = "Apartment"
        
        item.soukosuStr = self._parseSoukosuStr(response)
        item.soukosu = self._parseSoukosu(response)
            
        item.setsudou = self._parseSetsudou(response)
        item.chimoku = self._parseChimoku(response)
    
    def _parseSoukosuStr(self, response):
        specs = self._get_specs(response)
        return specs.get("総戸数", "")

    def _parseSoukosu(self, response):
        u_val = self._parseSoukosuStr(response)
        if u_val:
            try:
                m = re.search(r'(\d+)', u_val)
                if m:
                    return int(m.group(1))
            except: pass
        return 0

    def _getChimokuChiseiText(self, item, value):
        item.chimokuChisei = value
        item.chimoku = item.chimokuChisei.split("/")[0]
        item.chisei=""
        if (len(item.chimokuChisei.split("/"))>=2):
            item.chisei = item.chimokuChisei.split("/")[len(item.chimokuChisei.split("/"))-1]




    # Combined into definition at line 110






class SumifuMansionParser(SumifuParser):
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
        item.soukosu = self._parseSoukosu(response)
        
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
        item.saikouKadobeya = self._parseSaikou(response) + " / " + self._parseKadobeya(response)
        item.kanriKeitaiKaisya = self._parseKanriKeitaiKaisya(response).replace("\n", " / ")

        return item

    def _parseMadori(self, response):
        specs = self._get_specs(response)
        val = specs.get("間取り", "")
        if not val:
             m_tag = response.select_one(self.selectors.get('madori'))
             if m_tag: val = m_tag.get_text(strip=True)
        return val

    def _parseSenyuMensekiStr(self, response):
        specs = self._get_specs(response)
        val = specs.get("専有面積", "")
        if not val:
             s_tag = response.select_one(self.selectors.get('senyuMenseki'))
             if s_tag: val = s_tag.get_text(strip=True)
        return val

    def _parseSenyuMenseki(self, response):
        senyuMensekiStr = self._parseSenyuMensekiStr(response)
        if senyuMensekiStr:
            return converter.parse_menseki(senyuMensekiStr)
        return Decimal(0)

    # Kaisu/Kouzou logic inherited from base is now robust enough.
    # Removed redundant overrides here to use base implementation.

    def _parseChikunengetsuStr(self, response):
        specs = self._get_specs(response)
        return specs.get("築年月", "-")

    def _parseChikunengetsu(self, response):
        chikunengetsuStr = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(chikunengetsuStr) if chikunengetsuStr else None

    def _parseKyutaishin(self, response):
        chikunengetsu = self._parseChikunengetsu(response)
        if chikunengetsu and chikunengetsu < datetime.date(1982, 1, 1):
            return 1
        return 0

    def _parseBalconyMensekiStr(self, response):
        td = self._getValueFromTable(response, "バルコニー", partial_match=True)
        return td.get_text(strip=True) if td else ""

    def _parseBalconyMenseki(self, response):
        balconyMensekiStr = self._parseBalconyMensekiStr(response)
        if balconyMensekiStr and balconyMensekiStr != "-":
            # Just take the first area if multiple
            m = re.search(r'(\d+(\.\d+)?)', balconyMensekiStr)
            if m: return Decimal(m.group(1))
        return Decimal(0)

    def _parseSenyouNiwaMenseki(self, response):
        balconyMensekiStr = self._parseBalconyMensekiStr(response)
        if balconyMensekiStr and u"専用庭面積" in balconyMensekiStr:
             try: return converter.parse_menseki(balconyMensekiStr.split(u"専用庭面積")[1])
             except: pass
        return Decimal(0)

    def _parseRoofBalconyMenseki(self, response):
        balconyMensekiStr = self._parseBalconyMensekiStr(response)
        if balconyMensekiStr and u"ルーフバルコニー面積" in balconyMensekiStr:
             try: return converter.parse_menseki(balconyMensekiStr.split(u"ルーフバルコニー面積")[1])
             except: pass
        return Decimal(0)

    def _parseSaikou(self, response):
        td = self._getValueFromTable(response, "採光") or self._getValueFromTable(response, "向き")
        if td:
             val = td.get_text(strip=True)
             temp = re.split(u'/|／|\n', val)
             return temp[0].strip()
        return "-"

    def _parseKadobeya(self, response):
        td = self._getValueFromTable(response, "採光") or self._getValueFromTable(response, "向き")
        if td:
             val = td.get_text(strip=True)
             temp = re.split(u'/|／|\n', val)
             if len(temp) >= 2: return temp[1].strip()
        return "-"

    def _parseSoukosuStr(self, response):
        specs = self._get_specs(response)
        return specs.get("総戸数", "")

    def _parseSoukosu(self, response):
        soukosuStr = self._parseSoukosuStr(response)
        return converter.parse_numeric(soukosuStr) if soukosuStr else 0

    def _parseKanriKeitaiKaisya(self, response):
        td = self._getValueFromTable(response, "管理方式", partial_match=True) or \
             self._getValueFromTable(response, "管理形態", partial_match=True) or \
             self._getValueFromTable(response, "管理会社", partial_match=True)
        return td.get_text(separator="\n", strip=True) if td else ""

    def _parseKanriKeitai(self, response):
        val = self._parseKanriKeitaiKaisya(response)
        if val:
             temp = val.split("\n")
             return temp[0].strip()
        return "-"

    def _parseKanriKaisya(self, response):
        val = self._parseKanriKeitaiKaisya(response)
        if val:
             temp = val.split("\n")
             return temp[-1].strip()
        return "-"

    # _parseKaisuStr is inherited from SumifuParser (base) which extracts location floor.
    # However, for Mansion, we might want to ensure we get the floor number correctly.
    # Base _parseKaisuStr:
    #     val = self._parseKaisuRaw(response)
    #     if "・" in val: return val.split("・")[0].strip()
    #     return val
    # This works for "3階・RC造" -> "3階".
    # But Sumifu site often has "42階部分／地上49階地下3階建て鉄筋コンクリート造"
    # Base _parseKaisuStr would return the whole thing or fail to split if delimiter is different.
    
    def _parseKaisuStr(self, response):
        # Override to handle Sumifu Mansion specifics if base is insufficient
        # But let's check base implementation again.
        # It splits on "・". Sumifu often uses "／" or "建て".
        val = self._parseKaisuRaw(response)
        if not val: return "-"
        
        # Clean up common patterns
        # Pattern: "X階部分／地上Y階..."
        if "／" in val:
            val = val.split("／")[0].strip()
        
        # Pattern: "X階・..."
        if "・" in val:
            val = val.split("・")[0].strip()
            
        return val

    def _parseKanrihiStr(self, response):
        specs = self._get_specs(response)
        val = specs.get("管理費(月額)", specs.get("管理費", ""))
        return val if val and val != "￥" else "-"

    def _parseKanrihi(self, response):
        kanrihiStr = self._parseKanrihiStr(response)
        if not kanrihiStr: return 0
        if "万" in kanrihiStr: return converter.parse_price(kanrihiStr)
        return converter.parse_yen(kanrihiStr)

    def _parseSyuzenTsumitateStr(self, response):
        specs = self._get_specs(response)
        val = specs.get("修繕積立金(月額)", specs.get("修繕積立金", ""))
        return val if val and val != "￥" else "-"

    def _parseSyuzenTsumitate(self, response):
        syuzenTsumitateStr = self._parseSyuzenTsumitateStr(response)
        if not syuzenTsumitateStr: return 0
        if "万" in syuzenTsumitateStr: return converter.parse_price(syuzenTsumitateStr)
        return converter.parse_yen(syuzenTsumitateStr)

    def _parseBunjoKaisya(self, response):
        td = self._getValueFromTable(response, "新築時売主")
        return td.get_text(strip=True) if td else ""

    def _parseSekouKaisya(self, response):
        td = self._getValueFromTable(response, "施工会社")
        return td.get_text(strip=True) if td else ""

    # _parseKaisuStr is now defined above to return Location Text.
    # Previous implementation returned Building Height. 
    # If we need Building Height, we should parse it separately, but schema doesn't seem to imply kaisuStr is building height anymore for Mansion?
    # Actually SumifuMansion has floorType_chijo/chika which capture building height.
    
    def _parseFloorTypeKai(self, response):
        return self._parseKaisu(response) # Now returns Int

    def _parseFloorTypeChijo(self, response):
        raw = self._parseKaisuRaw(response)
        if raw:
             m = re.search(r'地上(\d+)階', raw)
             if m: return int(m.group(1))
        return None

    def _parseFloorTypeChika(self, response):
        raw = self._parseKaisuRaw(response)
        if raw:
             m = re.search(r'地下(\d+)階', raw)
             if m: return int(m.group(1))
        return None

    def _parseFloorTypeKouzou(self, response):
        kouzou = self._parseKouzou(response)
        return kouzou if kouzou else "-"

    def _calculateKanrihiPerHeibei(self, response):
        kanrihi = self._parseKanrihi(response)
        senyuMenseki = self._parseSenyuMenseki(response)
        if not kanrihi or not senyuMenseki: return 0
        from decimal import ROUND_HALF_UP
        val = (Decimal(str(kanrihi)) / Decimal(str(senyuMenseki))).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        return min(val, Decimal('9999.999'))

    def _calculateSyuzenTsumitatePerHeibei(self, response):
        syuzenTsumitate = self._parseSyuzenTsumitate(response)
        senyuMenseki = self._parseSenyuMenseki(response)
        if not syuzenTsumitate or not senyuMenseki: return 0
        from decimal import ROUND_HALF_UP
        val = (Decimal(str(syuzenTsumitate)) / Decimal(str(senyuMenseki))).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        return min(val, Decimal('9999.999'))

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
            m = re.search(r'([0-9]+(?:\.[0-9]+)?)', item.maguchiStr)
            if m:
                item.maguchi = Decimal(m.group(1))
                
        if item.douroHaba is not None:
            item.roadWidthStr = str(item.douroHaba)
            m = re.search(r'([0-9]+(?:\.[0-9]+)?)', item.roadWidthStr)
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

    def _parseTochiMensekiStr(self, response):
        specs = self._get_specs(response)
        val = specs.get("土地面積", "")
        if not val or val == "-":
            res = self._getValueByLabel(response, "土地面積")
            if res: val = res.get_text(strip=True).replace("土地面積", "")
        return val

    def _parseTochiMenseki(self, response):
        tochiMensekiStr = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(tochiMensekiStr) if tochiMensekiStr else Decimal(0)

    def _parseKenchikuJoken(self, response):
        specs = self._get_specs(response)
        return specs.get("建築条件", "-")

    def _parseChimoku(self, response):
        specs = self._get_specs(response)
        val = specs.get("地目", specs.get("地勢", specs.get("地目地勢", "")))
        if not val or val == "-":
            return "-"
        # If combined like "宅地平坦", it's hard to split strictly without a list.
        # But usually the first few chars are chimoku.
        potential = ["宅地", "田", "畑", "山林", "雑種地", "原野"]
        for p in potential:
            if val.startswith(p):
                return p
        return val # Fallback

    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get("接道状況", "-")

    def _parseKenpei(self, response):
        specs = self._get_specs(response)
        ky_str = specs.get("建ぺい率・容積率", specs.get("建ぺい率", ""))
        k, _ = self._parseKenpeiYousekiText(ky_str)
        if k is not None:
            return k
        # Fallback to direct number search in string
        if ky_str:
            m = re.search(r'(\d+)', ky_str)
            if m: return int(m.group(1))
        return None

    def _parseYouseki(self, response):
        specs = self._get_specs(response)
        ky_str = specs.get("建ぺい率・容積率", specs.get("容積率", ""))
        _, y = self._parseKenpeiYousekiText(ky_str)
        if y is not None:
            return y
        # Fallback to direct number search in string
        if ky_str:
            m = re.search(r'容積率.*?(\d+)', ky_str) or re.search(r'(\d+)', ky_str)
            if m: return int(m.group(len(m.groups())))
        return None

    def _parseYoutoChiiki(self, response):
        specs = self._get_specs(response)
        return specs.get("用途地域", "-")

    def _parseKokudoHou(self, response):
        specs = self._get_specs(response)
        return specs.get("国土法", "-")
    
    def _parseChisei(self, response):
        specs = self._get_specs(response)
        val = specs.get("地勢", specs.get("地目地勢", ""))
        if not val or val == "-":
            return "-"
        
        # If extracted from combined "地目地勢", try to remove chimoku
        if "地目地勢" in specs:
            chimoku = self._parseChimoku(response)
            if chimoku and chimoku != "-" and chimoku in val:
                val = val.replace(chimoku, "").strip()
        
        return val if val else "-"

    def _parseChimokuChisei(self, response):
        # Fallback or combination
        c = self._parseChimoku(response)
        s = self._parseChisei(response)
        return f"{c}・{s}" if c and s else (c or s or "-")

    def _parseKenpeiYousekiStr(self, response):
        specs = self._get_specs(response)
        val = specs.get("建ぺい率・容積率", "")
        if not val:
            k = specs.get("建ぺい率", "")
            y = specs.get("容積率", "")
            if k and y: val = f"建ぺい率{k} 容積率{y}"
            elif k or y: val = k or y
        return val if val else "-"

    def _parseKuiki(self, response):
        specs = self._get_specs(response)
        return specs.get("都市計画", "")

    def _parseSaikenchiku(self, response):
        specs = self._get_specs(response)
        val = specs.get("再建築不可", specs.get("再建築", ""))
        if not val:
            # Check other likely fields where this info might hide
            region = specs.get("地域・地区", specs.get("地域地区", specs.get("用途地域", "")))
            if "再建築不可" in region:
                val = "再建築不可"
        return val if val else "-"

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

    def _parseTochiMensekiStr(self, response):
        specs = self._get_specs(response)
        val = specs.get("土地面積", "")
        if not val or val == "-":
            res = self._getValueByLabel(response, "土地面積")
            if res: val = res.get_text(strip=True).replace("土地面積", "")
        return val

    def _parseTochiMenseki(self, response):
        tochiMensekiStr = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(tochiMensekiStr) if tochiMensekiStr else Decimal(0)

    def _parseTatemonoMensekiStr(self, response):
        specs = self._get_specs(response)
        val = specs.get("建物面積", "")
        if not val or val == "-":
            res = self._getValueByLabel(response, "建物面積")
            if res: val = res.get_text(strip=True).replace("建物面積", "")
        return val

    def _parseTatemonoMenseki(self, response):
        tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        return converter.parse_menseki(tatemonoMensekiStr) if tatemonoMensekiStr else Decimal(0)

    def _parseMadori(self, response):
        specs = self._get_specs(response)
        val = specs.get("間取り", "")
        if not val or val == "-":
            res = self._getValueByLabel(response, "間取り")
            if res: val = res.get_text(strip=True).replace("間取り", "")
        return val

    def _parseChikunengetsuStr(self, response):
        specs = self._get_specs(response)
        return specs.get("築年月", "-")

    def _parseHikiwatashi(self, response):
        specs = self._get_specs(response)
        return specs.get("引渡時期", "")

    def _parseGenkyo(self, response):
        specs = self._get_specs(response)
        return specs.get("現況", "")

    def _parseTochikenri(self, response):
        specs = self._get_specs(response)
        return specs.get("土地権利", "-")

    def _parseTorihiki(self, response):
        specs = self._get_specs(response)
        return specs.get("取引態様", "")

    def _parseKokudoHou(self, response):
        specs = self._get_specs(response)
        return specs.get("国土法", "")

    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseKenpeiYousekiStr(self, response):
        specs = self._get_specs(response)
        k = specs.get("建ぺい率", "")
        y = specs.get("容積率", "")
        if k and y:
            return f"建ぺい率{k} 容積率{y}"
        return k or y

    def _parseKenpeiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")
    
    def _parseYousekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseKuiki(self, response):
        specs = self._get_specs(response)
        return specs.get("都市計画", "")

    def _parseSaikenchiku(self, response):
        specs = self._get_specs(response)
        # Check '地域・地区' for '再建築不可' as seen in Error HTML
        val = specs.get("再建築不可", "")
        if not val:
            region = specs.get("地域・地区", "") or specs.get("地域地区", "")
            if "再建築不可" in region:
                val = "再建築不可"
        return val if val else "-"

    def _parseSpecsCombined(self, response, key_start):
        """Helper to find values where keys are concatenated like '階数構造'"""
        specs = self._get_specs(response)
        for key, val in specs.items():
            if key.startswith(key_start) or key_start in key:
                 return val
        return ""

    def _parseKaisuKouzou(self, response):
        return self._parseSpecsCombined(response, "階数") or "-"

    def _parseKaisu(self, response):
        # Key is '階数構造' -> "地上2階建て木造"
        val = self._parseSpecsCombined(response, "階数")
        if not val: return None
        # Extract number "2" from "地上2階建て"
        match = re.search(r'(\d+)階', val)
        return int(match.group(1)) if match else None

    def _parseKouzou(self, response):
        # Key '階数構造' -> "地上2階建て木造"
        val = self._parseSpecsCombined(response, "階数")
        if not val: return "-"
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

    def _parseChimoku(self, response):
        # Key '地目地勢' -> "宅地平坦"
        val = self._parseSpecsCombined(response, "地目")
        if not val: return "-"
        # Hard to split without delimiter.
        # But usually '宅地' is chimoku.
        potential_chimoku = ["宅地", "田", "畑", "山林", "雑種地"]
        for c in potential_chimoku:
            if val.startswith(c):
                return c
        return val

    def _parseChisei(self, response):
         # Key '地目地勢' -> "宅地平坦"
        val = self._parseSpecsCombined(response, "地目")
        if not val: return "-"
        # If extracts chimoku, remove it
        chimoku = self._parseChimoku(response)
        if chimoku and chimoku != "-" and chimoku in val:
            val = val.replace(chimoku, "").strip()
        return val if val else "-"

    def _parseChimokuChisei(self, response):
        c = self._parseChimoku(response)
        s = self._parseChisei(response)
        return f"{c}・{s}"

    def _parseChikunengetsu(self, response):
        chikunengetsuStr = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(chikunengetsuStr) if chikunengetsuStr else None

    def _parseKenpei(self, response):
        specs = self._get_specs(response)
        # Use simple key for Kodate
        k_str = specs.get("建ぺい率", "")
        if k_str:
            m = re.search(r'(\d+)', k_str)
            return int(m.group(1)) if m else None
        return None

    def _parseYouseki(self, response):
        specs = self._get_specs(response)
        y_str = specs.get("容積率", "")
        if not y_str:
             return None
        m = re.search(r'(\d+)', y_str)
        return int(m.group(1)) if m else None

    def _parseTyusyajo(self, response):
        specs = self._get_specs(response)
        return specs.get("駐車場", "")

    def _parseYoutoChiiki(self, response):
        specs = self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseKenchikuJoken(self, response):
        specs = self._get_specs(response)
        return specs.get("建築条件", "")

    def _parseKaisuStr(self, response):
        # Use the kaisu (int) we parsed
        k = self._parseKaisu(response)
        return str(k) if k is not None else ""

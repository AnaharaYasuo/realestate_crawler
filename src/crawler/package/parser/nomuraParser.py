import re
from abc import abstractmethod
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup, Tag

from package.models.nomura import (
    NomuraInvestmentApartment,
    NomuraInvestmentKodate,
    NomuraKodate,
    NomuraMansion,
    NomuraTochi,
)
from package.parser.baseParser import (
    InvestmentParserBase,
    KodateParserBase,
    MansionParserBase,
    SkipPropertyException,
    TochiParserBase,
)
from package.parser.investmentParser import InvestmentParser
from package.utils import converter
from package.utils.selector_loader import SelectorLoader


class NomuraParser(InvestmentParser):
    property_type = ""
    def __init__(self, token=""):
        super().__init__()
        self.selectors = SelectorLoader.load('nomura', self.property_type)

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        return super()._parseTransport1(response, specs)

    def _get_specs(self, response: BeautifulSoup):
        # We use _scrape_specs for actual implementation but override _get_specs for compatibility with InvestmentParser
        return self._scrape_specs(response)

    def _scrape_specs(self, response: BeautifulSoup) -> dict:
        specs = {}
        self._scrape_item_status_specs(response, specs)
        self._scrape_dl_specs(response, specs)
        for table in response.select("table"):
            self._parse_table_element(table, specs, force=False)
        for table in response.select("table.c_table_spec, table.col4"):
            self._parse_table_element(table, specs, force=True)
        return specs

    @staticmethod
    def _is_inside_modal(el) -> bool:
        p = getattr(el, "parent", None)
        while p and getattr(p, "name", None) != "[document]":
            classes = p.get("class") or []
            if isinstance(classes, str):
                classes = [classes]
            p_id = p.get("id") or ""
            if isinstance(p_id, list):
                p_id = " ".join(p_id)
            if (
                any("modal" in str(c).lower() for c in classes)
                or "fullModal" in classes
                or "modal" in str(p_id).lower()
            ):
                return True
            p = getattr(p, "parent", None)
        return False

    @staticmethod
    def _clean_key_text(el, tag_name="th") -> str:
        temp = BeautifulSoup(str(el), "html.parser").find(tag_name)
        if not temp:
            return ""
        for h in temp.select(
            ".item_help, .icon_help, .tooltip, .help, [class*='help'], [class*='tooltip']"
        ):
            h.decompose()
        return temp.get_text(strip=True).replace(" ", "").replace("\u3000", "").rstrip("：")

    def _scrape_item_status_specs(self, response: BeautifulSoup, specs: dict) -> None:
        for status in response.select(".item_status"):
            if self._is_inside_modal(status):
                continue
            title_el = status.select_one(".item_status_title")
            content_el = status.select_one(".item_status_content")
            if isinstance(title_el, Tag) and isinstance(content_el, Tag):
                key = (
                    self._clean_key_text(title_el, "span")
                    or self._clean_key_text(title_el, "div")
                    or title_el.get_text(strip=True)
                    .replace(" ", "")
                    .replace("\u3000", "")
                    .rstrip("：")
                )
                specs[key] = content_el.get_text(strip=True).replace("\xa0", " ")

    def _scrape_dl_specs(self, response: BeautifulSoup, specs: dict) -> None:
        for dl in response.select("dl"):
            if self._is_inside_modal(dl):
                continue
            current_key = None
            for child in dl.find_all(["dt", "dd"], recursive=False):
                if child.name == "dt":
                    current_key = self._clean_key_text(child, "dt")
                elif child.name == "dd" and current_key:
                    val = child.get_text(strip=True).replace("\xa0", " ")
                    if len(val) < 300:  # Exclude long explanation footnotes
                        specs[current_key] = val
                    current_key = None

    def _parse_table_element(self, table, specs: dict, force: bool = False) -> None:
        if self._is_inside_modal(table):
            return
        self._parse_table_th_td_rows(table, specs, force)
        self._parse_table_inner_cards(table, specs, force)

    def _parse_table_th_td_rows(self, table, specs: dict, force: bool) -> None:
        for tr in table.select("tr"):
            ths = tr.select("th")
            tds = tr.select("td")
            for th, td in zip(ths, tds):
                self._store_table_kv(
                    specs,
                    self._clean_key_text(th, "th"),
                    td.get_text(strip=True).replace("\xa0", " "),
                    force,
                )

    @staticmethod
    def _store_table_kv(specs: dict, key: str, val: str, force: bool) -> None:
        if not key:
            return
        if key == "構造" and val.startswith("#"):
            return
        if force or key not in specs or len(val) > len(specs.get(key, "")):
            specs[key] = val

    def _parse_table_inner_cards(self, table, specs: dict, force: bool) -> None:
        for inner in table.select("td > div.inner"):
            h_el = inner.select_one(".heading")
            p_el = inner.select_one("p")
            if not h_el or not p_el:
                continue
            k = self._clean_key_text(h_el, "div")
            v = p_el.get_text(strip=True).replace("\xa0", " ")
            if k and (k not in specs or force):
                specs[k] = v

    def _parsePriceStr(self, response, specs=None):
        val = self._price_from_selector(response, self.selectors.get("price", ".price, .item_price"))
        if val:
            return val
        val = self._price_from_selector(
            response, self.selectors.get("price_fallback", ".c_price_wrap, .price")
        )
        if val:
            return val
        specs = specs or self._get_specs(response)
        return specs.get("価格", "") or specs.get("販売価格", "") or super()._parsePriceStr(response, specs)

    @staticmethod
    def _price_from_selector(response, selector) -> str:
        if not selector:
            return ""
        el = response.select_one(selector)
        if not el:
            return ""
        val = el.get_text(strip=True)
        if val and ("万" in val or "億" in val or "円" in val):
            return val
        return ""

    def _parsePrice(self, response, specs=None):
        return converter.parse_price(self._parsePriceStr(response))

    def _parseAddress(self, response, specs=None):
        specs = self._get_specs(response)
        addr = specs.get("所在地", "").replace("周辺地図を見る", "").strip()
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
        return town


    def _parseTrafficFull(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("交通", "")

    def _parseTrafficLines(self, response, specs=None):
        traffic_full = self._parseTrafficFull(response)
        if not traffic_full: return []
        # Nomura often uses <br> which becomes \n in get_text()
        lines = [line.strip() for line in traffic_full.split("\n") if line.strip()]
        return lines

    def _parseRailwayCount(self, response, specs=None):
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

    def _parseTransfer1(self, response, specs=None): return self._getTrafficField(response, 1, 'transfer', "")
    def _parseRailway1(self, response, specs=None): return self._getTrafficField(response, 1, 'railway', "")
    def _parseStation1(self, response, specs=None): return self._getTrafficField(response, 1, 'station', "")
    def _parseRailwayWalkMinute1Str(self, response, specs=None): return self._getTrafficField(response, 1, 'railwayWalkMinute1Str', "")
    def _parseRailwayWalkMinute1(self, response, specs=None): return self._getTrafficField(response, 1, 'railwayWalkMinute', 0)
    def _parseBusStation1(self, response, specs=None): return self._getTrafficField(response, 1, 'busStation', "")
    def _parseBusWalkMinute1Str(self, response, specs=None): return self._getTrafficField(response, 1, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute1(self, response, specs=None): return self._getTrafficField(response, 1, 'busWalkMinute', 0)
    def _parseBusUse1(self, response, specs=None): return self._getTrafficField(response, 1, 'busUse', 0)

    def _parseTransfer2(self, response, specs=None): return self._getTrafficField(response, 2, 'transfer', "")
    def _parseRailway2(self, response, specs=None): return self._getTrafficField(response, 2, 'railway', "")
    def _parseStation2(self, response, specs=None): return self._getTrafficField(response, 2, 'station', "")
    def _parseRailwayWalkMinute2Str(self, response, specs=None): return self._getTrafficField(response, 2, 'railwayWalkMinute2Str', "")
    def _parseRailwayWalkMinute2(self, response, specs=None): return self._getTrafficField(response, 2, 'railwayWalkMinute', 0)
    def _parseBusStation2(self, response, specs=None): return self._getTrafficField(response, 2, 'busStation', "")
    def _parseBusWalkMinute2Str(self, response, specs=None): return self._getTrafficField(response, 2, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute2(self, response, specs=None): return self._getTrafficField(response, 2, 'busWalkMinute', 0)
    def _parseBusUse2(self, response, specs=None): return self._getTrafficField(response, 2, 'busUse', 0)

    def _parseTransfer3(self, response, specs=None): return self._getTrafficField(response, 3, 'transfer', "")
    def _parseRailway3(self, response, specs=None): return self._getTrafficField(response, 3, 'railway', "")
    def _parseStation3(self, response, specs=None): return self._getTrafficField(response, 3, 'station', "")
    def _parseRailwayWalkMinute3Str(self, response, specs=None): return self._getTrafficField(response, 3, 'railwayWalkMinute3Str', "")
    def _parseRailwayWalkMinute3(self, response, specs=None): return self._getTrafficField(response, 3, 'railwayWalkMinute', 0)
    def _parseBusStation3(self, response, specs=None): return self._getTrafficField(response, 3, 'busStation', "")
    def _parseBusWalkMinute3Str(self, response, specs=None): return self._getTrafficField(response, 3, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute3(self, response, specs=None): return self._getTrafficField(response, 3, 'busWalkMinute', 0)
    def _parseBusUse3(self, response, specs=None): return self._getTrafficField(response, 3, 'busUse', 0)

    def _parseTransfer4(self, response, specs=None): return self._getTrafficField(response, 4, 'transfer', "")
    def _parseRailway4(self, response, specs=None): return self._getTrafficField(response, 4, 'railway', "")
    def _parseStation4(self, response, specs=None): return self._getTrafficField(response, 4, 'station', "")
    def _parseRailwayWalkMinute4Str(self, response, specs=None): return self._getTrafficField(response, 4, 'railwayWalkMinute4Str', "")
    def _parseRailwayWalkMinute4(self, response, specs=None): return self._getTrafficField(response, 4, 'railwayWalkMinute', 0)
    def _parseBusStation4(self, response, specs=None): return self._getTrafficField(response, 4, 'busStation', "")
    def _parseBusWalkMinute4Str(self, response, specs=None): return self._getTrafficField(response, 4, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute4(self, response, specs=None): return self._getTrafficField(response, 4, 'busWalkMinute', 0)
    def _parseBusUse4(self, response, specs=None): return self._getTrafficField(response, 4, 'busUse', 0)

    def _parseTransfer5(self, response, specs=None): return self._getTrafficField(response, 5, 'transfer', "")
    def _parseRailway5(self, response, specs=None): return self._getTrafficField(response, 5, 'railway', "")
    def _parseStation5(self, response, specs=None): return self._getTrafficField(response, 5, 'station', "")
    def _parseRailwayWalkMinute5Str(self, response, specs=None): return self._getTrafficField(response, 5, 'railwayWalkMinute5Str', "")
    def _parseRailwayWalkMinute5(self, response, specs=None): return self._getTrafficField(response, 5, 'railwayWalkMinute', 0)
    def _parseBusStation5(self, response, specs=None): return self._getTrafficField(response, 5, 'busStation', "")
    def _parseBusWalkMinute5Str(self, response, specs=None): return self._getTrafficField(response, 5, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute5(self, response, specs=None): return self._getTrafficField(response, 5, 'busWalkMinute', 0)
    def _parseBusUse5(self, response, specs=None): return self._getTrafficField(response, 5, 'busUse', 0)

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


    def _parseMadori(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("間取り", "")

    def _parseSenyuMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("専有面積", "")

    def _parseSenyuMenseki(self, response, specs=None):
        value = self._parseSenyuMensekiStr(response)
        return converter.parse_menseki(value) or Decimal(0)

    def _parseBalconyMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("バルコニー面積", "")

    def _parseBalconyMenseki(self, response, specs=None):
        value = self._parseBalconyMensekiStr(response)
        return converter.parse_menseki(value) if value else None

    def _parseSaikou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("向き", "")

    def _parseOtherArea(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("その他面積", "")

    def _parseKouzou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("構造", "")

    def _parseKaisu(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("所在階", "")

    def _parseKaisuStr(self, response, specs=None):
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

    def _parseChikunengetsuStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("築年月", "")

    def _parseChikunengetsu(self, response, specs=None):
        value = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(value)

    def _parseSoukosuStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("総戸数", specs.get("住戸数", ""))

    def _parseSoukosu(self, response, specs=None):
        value = self._parseSoukosuStr(response)
        return converter.parse_numeric(value)

    def _parseTochikenri(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("土地権利", "")

    def _parseYoutoChiiki(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseKanriKaisya(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("管理会社", "")

    def _parseKanriKeitai(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("管理形態", "")

    def _parseManager(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("管理員", "")

    def _parseKanrihiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("管理費", "")

    def _parseSyuzenTsumitateStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("修繕積立金", "")

    def _parseOtherFees(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("その他費用", "")

    def _parseTyusyajo(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("駐車場", "")
    
    def _parseCurrentStatus(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("現況", "") or "不明"

    def _parseHikiwatashi(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("引渡", specs.get("引渡時期", "")) or "相談"

    def _parseTorihiki(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("取引態様", "") or "仲介"

    def _parseBiko(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("備考", "")

    def _parseUpdateDate(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("更新日", specs.get("情報更新日", ""))

    def _parseNextUpdateDate(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("次回更新予定日", "")

    @staticmethod
    def _apply_setsudou_road_fields(item) -> None:
        """Parse maguchi / road attributes from setsudou text onto item."""
        setsudou = getattr(item, "setsudou", None) or ""
        if not setsudou:
            item.roadStructure = "中間地"
            NomuraParser._apply_okuyuki(item)
            return
        NomuraParser._apply_maguchi_from_setsudou(item, setsudou)
        width_match = re.search(
            r"(?:幅員|幅|道路)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?", setsudou
        )
        if width_match:
            item.roadWidthStr = width_match.group(0)
            item.roadWidth = Decimal(width_match.group(1))
        direction_match = re.search(r"(北東|北西|南東|南西|北|南|東|西)", setsudou)
        item.roadDirection = direction_match.group(1) if direction_match else ""
        type_match = re.search(r"(公道|私道)", setsudou)
        item.roadType = type_match.group(1) if type_match else ""
        structure_match = re.search(
            r"(角地|二方|三方|四方|敷延|袋小路|中間地|両面道路)", setsudou
        )
        item.roadStructure = structure_match.group(1) if structure_match else "中間地"
        NomuraParser._apply_okuyuki(item)

    @staticmethod
    def _apply_maguchi_from_setsudou(item, setsudou: str) -> None:
        mag_match = re.search(
            r"(?:間口|接面|接す)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?", setsudou
        )
        if mag_match:
            item.maguchiStr = mag_match.group(0)
            item.maguchi = Decimal(mag_match.group(1))
            return
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)(?:接面|接す|間口)", setsudou)
        if m:
            item.maguchiStr = m.group(0)
            item.maguchi = Decimal(m.group(1))

    @staticmethod
    def _apply_okuyuki(item) -> None:
        tochi = getattr(item, "tochiMenseki", None)
        maguchi = getattr(item, "maguchi", None)
        if tochi and maguchi and maguchi > 0:
            item.okuyuki = round(tochi / maguchi, 2)
            item.okuyukiStr = f"{item.okuyuki}m"

class NomuraMansionParser(NomuraParser, MansionParserBase):

    def _parseSenyuMenseki(self, response, specs=None):
        specs = specs or self._get_specs(response)
        val = self._senyu_menseki_raw_from_specs(specs)
        parsed = self._decimal_from_menseki_text(val) if val else None
        if parsed is not None:
            return parsed
        parsed = self._senyu_menseki_from_inner_blocks(response)
        if parsed is not None:
            return parsed
        parsed = self._senyu_menseki_from_labeled_elements(response)
        if parsed is not None:
            return parsed
        return super()._parseSenyuMenseki(response, specs)

    @staticmethod
    def _senyu_menseki_raw_from_specs(specs: dict):
        val = specs.get("専有面積", "") or specs.get("壁芯面積", "")
        if val:
            return val
        for k, v in specs.items():
            if ("専有" in str(k) and "面積" in str(k)) or "壁芯" in str(k):
                return v
        return ""

    @staticmethod
    def _decimal_from_menseki_text(val):
        m = re.search(r"([\d.]+)", str(val).replace(",", ""))
        return Decimal(m.group(1)) if m else None

    @staticmethod
    def _senyu_menseki_from_inner_blocks(response):
        for inner in response.select(".inner"):
            h = inner.select_one(".heading")
            if not h:
                continue
            if "専有面積" not in h.get_text() and "壁芯面積" not in h.get_text():
                continue
            p = inner.select_one("p")
            if not p:
                continue
            m = re.search(r"([\d.]+)", p.get_text())
            if m:
                return Decimal(m.group(1))
        return None

    @staticmethod
    def _senyu_menseki_from_labeled_elements(response):
        for el in response.select("th, dt, .heading, .c_heading, span, p"):
            txt = el.get_text(" ", strip=True)
            if "専有面積" not in txt and "壁芯面積" not in txt:
                continue
            sib = el.find_next(["td", "dd", "p", "span"])
            blob = (sib.get_text(" ", strip=True) if sib else "") + " " + txt
            m = re.search(r"([\d.]+)\s*m", blob, re.IGNORECASE)
            if m:
                return Decimal(m.group(1))
        return None

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
    def createEntity(self): return NomuraMansion()
    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        name = self._safe_property_name(response)
        if any(tok in str(name) for tok in ("戸建", "一戸建", "土地")) and not any(
            tok in str(name) for tok in ("マンション", "レジデンス", "タワー", "アパート", "一棟")
        ):
            raise SkipPropertyException(f"Non-mansion Nomura listing skipped: {str(name)[:60]}")
        item.propertyName = name
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

    def _safe_property_name(self, response) -> str:
        try:
            return self._parsePropertyName(response) or ""
        except (AttributeError, TypeError, ValueError):
            h1 = response.select_one("h1") if response else None
            return h1.get_text(" ", strip=True) if h1 else ""



class NomuraKodateParser(NomuraParser, KodateParserBase):

    def _parseMadori(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "") or super()._parseMadori(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("構造", "") or super()._parseKouzou(response, specs)

    def _parseRights(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "") or super()._parseYoutoChiiki(response, specs)

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
        
        # 統一土地評価フィールドのパース ＆ 代入
        item.setsudou = self._parseSetsudou(response)
        import re
        if item.setsudou:
            mag_match = re.search(r'(?:間口|接面|接す)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', item.setsudou)
            if mag_match:
                item.maguchiStr = mag_match.group(0)
                item.maguchi = Decimal(mag_match.group(1))
            else:
                m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)(?:接面|接す|間口)', item.setsudou)
                if m:
                    item.maguchiStr = m.group(0)
                    item.maguchi = Decimal(m.group(1))
                
            width_match = re.search(r'(?:幅員|幅|道路)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', item.setsudou)
            if width_match:
                item.roadWidthStr = width_match.group(0)
                item.roadWidth = Decimal(width_match.group(1))
                
            direction_match = re.search(r'(北東|北西|南東|南西|北|南|東|西)', item.setsudou)
            item.roadDirection = direction_match.group(1) if direction_match else ""
            
            type_match = re.search(r'(公道|私道)', item.setsudou)
            item.roadType = type_match.group(1) if type_match else ""
            
            structure_match = re.search(r'(角地|二方|三方|四方|敷延|袋小路|中間地|両面道路)', item.setsudou)
            item.roadStructure = structure_match.group(1) if structure_match else "中間地"
        else:
            item.roadStructure = "中間地"
            
        if item.tochiMenseki and getattr(item, 'maguchi', None) and item.maguchi > 0:
            item.okuyuki = round(item.tochiMenseki / item.maguchi, 2)
            item.okuyukiStr = f"{item.okuyuki}m"
            
        return item

    def _parseTochiMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseTochiMenseki(self, response, specs=None):
        value = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(value) or Decimal(0)

    def _parseTatemonoMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("建物面積", specs.get("延床面積", ""))

    def _parseTatemonoMenseki(self, response, specs=None):
        value = self._parseTatemonoMensekiStr(response)
        return converter.parse_menseki(value) or Decimal(0)

    def _parseChimoku(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("地目", "")

    def _parsePrivateRoadBurden(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("私道負担", "")

    def _parseSetback(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("セットバック", "")

    def _parseCityPlanning(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("都市計画", "")

    def _parseKenpeiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response, specs=None):
        value = self._parseKenpeiStr(response)
        return converter.parse_numeric(value)

    def _parseYousekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response, specs=None):
        value = self._parseYousekiStr(response)
        return converter.parse_numeric(value)
    def _parseSetsudou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")
    def _parseFacilities(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("設備", "")

class NomuraTochiParser(NomuraParser, TochiParserBase):
    def _parseMaguchi(self, response, specs=None):
        return super()._parseMaguchi(response, specs)


    def _parseRights(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "") or super()._parseYoutoChiiki(response, specs)

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

        # 統一土地評価フィールドのパース ＆ 代入 (setsudouテキストから切り出し)
        NomuraParser._apply_setsudou_road_fields(item)

        return item

    def _parseTochiMensekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseTochiMenseki(self, response, specs=None):
        value = self._parseTochiMensekiStr(response)
        return converter.parse_menseki(value)

    def _parseChimoku(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("地目", "")

    def _parseSetsudou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseKenpeiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response, specs=None):
        value = self._parseKenpeiStr(response)
        return converter.parse_numeric(value)

    def _parseYousekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response, specs=None):
        value = self._parseYousekiStr(response)
        return converter.parse_numeric(value)

    def _parseCityPlanning(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("都市計画", "")

class NomuraInvestmentParser(NomuraParser, InvestmentParserBase):

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        return super()._parseKouzou(response, specs)

    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

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
        self._require_invest_yield_and_rent(item)
        
        item.currentStatus = self._parseCurrentStatus(response)
        item.kouzou = self._parseKouzouInvest(response)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        
        item.stories = self._parseStories(response)
        item.kaisuStr = self._parseKaisuStr(response)
        item.tochiMenseki = self._parseTochiMensekiInvest(response)
        item.tatemonoMenseki = self._parseTatemonoMensekiInvest(response)
        item.biko = self._parseBiko(response)
        
        # 統一土地評価フィールドのパース ＆ 代入
        item.setsudou = self._parseSetsudou(response)
        NomuraParser._apply_setsudou_road_fields(item)
            
        return item

    @staticmethod
    def _require_invest_yield_and_rent(item) -> None:
        try:
            gy = float(item.grossYield or 0)
        except (TypeError, ValueError):
            gy = 0.0
        ar = item.annualRent or item.monthlyRent or 0
        try:
            ar_f = float(ar)
        except (TypeError, ValueError):
            ar_f = 0.0
        if gy <= 0 or ar_f <= 0:
            raise SkipPropertyException(
                "Nomura invest listing missing published yield/rent"
            )

    def _parseHikiwatashiInvest(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("引渡", specs.get("引渡時期", "即時"))

    def _parseTorihikiInvest(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("取引態様", "仲介")
    
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
        rent_val = (
            specs.get("想定年間収入")
            or specs.get("想定年商")
            or specs.get("満室時想定年収")
            or specs.get("満室時年収")
            or specs.get("想定年収")
            or ""
        )
        if not rent_val:
            for k, v in specs.items():
                if any(x in str(k) for x in ("年間収入", "想定年収", "想定年商")) and v:
                    rent_val = v
                    break
        return converter.parse_price(str(rent_val)) if rent_val else 0

    def _parseMonthlyRent(self, response, specs=None):
        annualRent = self._parseAnnualRent(response)
        return (annualRent // 12) if annualRent else 0

    def _parseKouzouInvest(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("構造", "不明")
    
    def _parseStories(self, response, specs=None):
        specs = self._get_specs(response)
        stories_val = specs.get("階数", specs.get("階建", ""))
        m = re.search(r'(\d+)', stories_val) if stories_val else None
        return int(m.group(1)) if m else 0
        
    def _parseTochiMensekiInvest(self, response, specs=None):
        specs = self._get_specs(response)
        land_area = specs.get("土地面積", "")
        return Decimal(str(converter.parse_menseki(land_area))) if land_area else Decimal(0)

    def _parseTatemonoMensekiInvest(self, response, specs=None):
        specs = self._get_specs(response)
        bldg_area = specs.get("建物面積", specs.get("延床面積", specs.get("専有面積", "")))
        return Decimal(str(converter.parse_menseki(bldg_area))) if bldg_area else Decimal(0)

    # Missing helpers/Refactored for Investment Parsing
    def _parseSetsudou(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseChimoku(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("地目", "")

    def _parseYoutoChiiki(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseTochikenri(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("土地権利", "")

    def _parseKenpeiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response, specs=None):
        value = self._parseKenpeiStr(response)
        return converter.parse_numeric(value)

    def _parseYousekiStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response, specs=None):
        value = self._parseYousekiStr(response)
        return converter.parse_numeric(value)

    def _parseSoukosuStr(self, response, specs=None):
        specs = self._get_specs(response)
        return specs.get("総戸数", specs.get("住戸数", ""))

    def _parseSoukosu(self, response, specs=None):
        value = self._parseSoukosuStr(response)
        return converter.parse_numeric(value)

class NomuraInvestmentKodateParser(NomuraInvestmentParser, KodateParserBase):

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

class NomuraInvestmentApartmentParser(NomuraInvestmentParser, InvestmentParserBase):

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
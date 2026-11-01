from decimal import Decimal
# -*- coding: utf-8 -*-
import re
import logging
import urllib.parse
from bs4 import BeautifulSoup

from package.models.keisei import KeiseiMansion, KeiseiKodate, KeiseiTochi
from package.parser.baseParser import KodateParserBase, ListItem, MansionParserBase, ParserBase, SkipPropertyException, TochiParserBase
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

def _first_spec(specs: dict, *keys: str) -> str:
    for k in keys:
        v = specs.get(k)
        if v:
            return v
    return ""


class KeiseiParser(ParserBase):

    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parsePriceStr(self, response, specs=None):
        return super()._parsePriceStr(response, specs)

    BASE_URL = 'https://www.keisei-land.co.jp'
    property_type = ""

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('keisei', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def _parsePrice(self, response: BeautifulSoup, specs=None):
        return super()._parsePrice(response, specs)

    def _parseAddress(self, response: BeautifulSoup, specs=None):
        return super()._parseAddress(response, specs)



    def getRootDestUrl(self, link_url):
        if link_url.startswith('http'):
            return link_url
        if link_url.startswith('/'):
            return self.BASE_URL + link_url
        return self.BASE_URL + "/" + link_url

    async def getResponseBs(self, session, url, charset=None) -> BeautifulSoup:
        return await super().getResponseBs(session, url, charset)


    @staticmethod
    def _with_offset_param(current_url: str, next_offset: str) -> str:
        parsed = urllib.parse.urlparse(current_url)
        qs = urllib.parse.parse_qs(parsed.query)
        qs["offset"] = [next_offset]
        new_query = urllib.parse.urlencode(qs, doseq=True)
        return urllib.parse.urlunparse(parsed._replace(query=new_query))

    def _extract_next_paging_anchor(self, response: BeautifulSoup) -> str:
        for a in response.select(".paging a, .pager a"):
            text = a.get_text().strip()
            href = a.get("href")
            if href and ("次" in text or ">" in text or "next" in text.lower()):
                return self.getRootDestUrl(href)
        return ""

    @staticmethod
    def _extract_next_form_offset(response: BeautifulSoup) -> str | None:
        for btn in response.select("input[type='button'], button, a"):
            val = btn.get("value", "") or btn.get_text(strip=True)
            onclick = btn.get("onClick", "") or btn.get("onclick", "")
            if "次" not in val or "form1_submit" not in onclick:
                continue
            m = re.search(r"form1_submit\('(\d+)'\)", onclick)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _extract_next_select_offset(response: BeautifulSoup) -> str | None:
        offset_select = response.select_one('select[name="offset"]')
        if not offset_select:
            return None
        options = [opt.get("value") for opt in offset_select.select("option") if opt.get("value")]
        if not options:
            return None
        selected_opt = offset_select.select_one("option[selected]")
        curr_val = selected_opt.get("value") if selected_opt else options[0]
        if not curr_val or curr_val not in options:
            return None
        curr_idx = options.index(curr_val)
        return options[curr_idx + 1] if curr_idx + 1 < len(options) else None

    def _default_search_url(self) -> str:
        r_type_map = {"tochi": "1", "kodate": "2", "mansion": "3"}
        r_type = r_type_map.get(self.property_type, "3")
        return f"{self.BASE_URL}/contents/code/search_result?mode=list&all_pref=1&r_type={r_type}&by=area"

    async def parseNextPage(self, response: BeautifulSoup, current_url: str = ""):
        anchor_url = self._extract_next_paging_anchor(response)
        if anchor_url:
            return anchor_url
        base_url = current_url or self._default_search_url()
        next_offset = self._extract_next_form_offset(response) or self._extract_next_select_offset(response)
        if next_offset:
            return self._with_offset_param(base_url, next_offset)
        return ""

    async def parseRootPage(self, response: BeautifulSoup):
        detail_links = set()
        for a in response.select('a[href*="detail"]'):
            href = a.get("href")
            if href:
                full_url = self.getRootDestUrl(href)
                parsed = urllib.parse.urlparse(full_url)
                path = parsed.path
                if not path.endswith('/'):
                    path += '/'
                normalized = f"{self.BASE_URL}{path}"
                if normalized not in detail_links:
                    detail_links.add(normalized)
                    logging.debug(f"[Keisei] Match detail link: {normalized}")
                    price = self._extract_card_price(a)
                    yield ListItem(url=normalized, price=price)

    def _get_specs(self, response: BeautifulSoup) -> dict:
        specs = {}
        for table in response.select("table"):
            for tr in table.select("tr"):
                ths = tr.find_all("th")
                tds = tr.find_all("td")
                for i in range(min(len(ths), len(tds))):
                    key = ths[i].get_text().strip().replace("\n", "").replace(" ", "")
                    val = tds[i].get_text().strip()
                    val = re.sub(r'\s+', ' ', val)
                    specs[key] = val
        # 上部概要 ul.propertyInfoWidth01 の抽出
        for ul in response.select("ul.propertyInfoWidth01"):
            for li in ul.select("li"):
                dt = li.select_one("dt")
                dd = li.select_one("dd")
                if dt and dd:
                    key = dt.get_text().strip().replace("\n", "").replace(" ", "").replace("：", "").replace(":", "")
                    val = dd.get_text().strip()
                    val = re.sub(r'\s+', ' ', val)
                    specs[key] = val
        return specs

    def _split_address(self, address):
        return super()._split_address(address)

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)
        
        # 物件名
        item.propertyName = self._parsePropertyName(response)
            
        # 価格
        price_val = specs.get("価格", "") or specs.get("販売価格", "")
        if not price_val:
            for price_el in response.select("#price, .price_box"):
                if self._is_valid_selling_price_element(price_el):
                    price_val = price_el.get_text().strip()
                    if price_val:
                        break
            
        if price_val:
            item.priceStr = price_val
            item.price = converter.parse_price(item.priceStr)

        # 所在地
        addr_val = specs.get("所在地", "") or specs.get("住所", "")
        if addr_val:
            item.address = addr_val
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        # 交通
        traffic_str = specs.get("交通", "")
        if traffic_str:
            self._populateTraffic(item, traffic_str)

        item.biko = specs.get("備考", "") or specs.get("その他", "")
        item.genkyo = self._parseCurrentStatus(response, specs)
        item.tochikenri = self._parseRights(response, specs)
        item.torihiki = specs.get("取引態様", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "")

        return item

class KeiseiMansionParser(KeiseiParser, MansionParserBase):
    def _parsePriceStr(self, response, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseYoutoChiiki(self, response, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseSenyuMenseki(self, response, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("専有面積", "") or specs.get("壁芯面積", "")
        if val:
            m = re.search(r'([\d\.]+)', val)
            return Decimal(m.group(1)) if m else None
        return super()._parseSenyuMenseki(response, specs)

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

    def createEntity(self):
        return KeiseiMansion()

    def _parse_floors(self, item, specs):
        item.kaisuStr = _first_spec(specs, "所在階/構造・階建", "所在階", "階数")
        if item.kaisuStr:
            m = re.search(r'(\d{1,5})階', item.kaisuStr)
            if m:
                item.floorType_kai = int(m.group(1))
            m = re.search(r'地上(\d{1,5})階', item.kaisuStr)
            if m:
                item.floorType_chijo = int(m.group(1))
            m = re.search(r'地下(\d{1,5})階', item.kaisuStr)
            if m:
                item.floorType_chika = int(m.group(1))

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = self._parseMadori(response, specs)
        
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)

        self._parse_floors(item, specs)

        # 築年月
        item.chikunengetsuStr = _first_spec(specs, "築年月", "完成時期")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.balconyMensekiStr = specs.get("バルコニー面積", "")
        if item.balconyMensekiStr:
            item.balconyMenseki = converter.parse_menseki(item.balconyMensekiStr)

        # 総戸数
        item.soukosuStr = specs.get("総戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

        item.kanrihiStr = specs.get("管理費", "")
        if item.kanrihiStr:
            item.kanrihi = converter.parse_rent(item.kanrihiStr)

        item.syuzenTsumitateStr = specs.get("修繕積立金", "")
        if item.syuzenTsumitateStr:
            item.syuzenTsumitate = converter.parse_rent(item.syuzenTsumitateStr)

        item.kouzou = self._parseKouzou(response, specs)
        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        
        item.saikou = _first_spec(specs, "主要採光", "向き")
        item.saikouMuki = item.saikou
        item.saikouMukiStr = item.saikou
        item.saikouKadobeya = specs.get("角部屋", "")
        item.kadobeya = item.saikouKadobeya

        return item

class KeiseiKodateParser(KeiseiParser, KodateParserBase):
    def _parsePriceStr(self, response, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseSetsudou(self, response, specs=None):
        return super()._parseSetsudou(response, specs)

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

    def createEntity(self):
        return KeiseiKodate()

    @staticmethod
    def _ensure_not_mansion_spec(specs: dict, item) -> None:
        if not specs.get("土地面積") and (specs.get("専有面積") or "マンション" in str(specs.get("種目", ""))):
            raise SkipPropertyException(f"Keisei mansion mixed into kodate parser: {getattr(item, 'pageUrl', '')}")

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)
        self._ensure_not_mansion_spec(specs, item)

        item.madori = self._parseMadori(response, specs)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.kouzou = self._parseKouzou(response, specs)
        item.kaisuStr = specs.get("階数", "") or specs.get("階建", "")
        if item.kaisuStr:
            item.kaisu = converter.parse_numeric(item.kaisuStr)

        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)

        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)

        return item

class KeiseiTochiParser(KeiseiParser, TochiParserBase):
    def _parsePriceStr(self, response, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

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

    def createEntity(self):
        return KeiseiTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.kenchikuJoken = specs.get("建築条件", "")
        item.chimoku = self._parseChimoku(response, specs)
        
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)

        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)

        return item
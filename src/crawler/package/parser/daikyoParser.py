from decimal import Decimal
# -*- coding: utf-8 -*-
import re
import logging
import urllib.parse
from bs4 import BeautifulSoup

from package.models.daikyo import DaikyoMansion, DaikyoKodate, DaikyoTochi
from package.parser.baseParser import KodateParserBase, MansionParserBase, ParserBase, TochiParserBase
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

class DaikyoParser(ParserBase):

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

    BASE_URL = 'https://www.daikyo-anabuki.co.jp'
    property_type = ""

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('daikyo', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def _parsePrice(self, response: BeautifulSoup):
        return super()._parsePrice(response)

    def _parseAddress(self, response: BeautifulSoup):
        return super()._parseAddress(response)



    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        if linkUrl.startswith('/'):
            return self.BASE_URL + linkUrl
        return self.BASE_URL + "/" + linkUrl

    async def getResponseBs(self, session, url, charset=None) -> BeautifulSoup:
        return await super().getResponseBs(session, url, charset)


    def _find_paging_link(self, response: BeautifulSoup) -> str:
        for a in response.select(".paging a, .pager a, .result-pager a"):
            text = a.get_text().strip()
            if "次" in text or ">" in text or "next" in text.lower():
                href = a.get("href")
                if href:
                    return self.getRootDestUrl(href)
        return ""

    def _find_page_param_link(self, response: BeautifulSoup) -> str:
        for a in response.find_all("a", href=re.compile(r'[?&]page=\d+')):
            text = a.get_text().strip()
            classes = a.get("class") or []
            if "次" in text or ">" in text or "next" in text.lower() or "jsPagingNext" in classes:
                href = a.get("href")
                if href:
                    return self.getRootDestUrl(href)
        return ""

    async def parseNextPage(self, response: BeautifulSoup):
        # 1. 専門クラス・モダンセレクタ
        next_tag = response.select_one(".jsPagingNext, a[class*='PagingNext'], .result-pager__next a, a[rel='next']")
        if next_tag is not None:
            href = next_tag.get("href")
            if href:
                return self.getRootDestUrl(href)

        # 2. 汎用セレクタ (.paging, .pager, .result-pager)
        paging_url = self._find_paging_link(response)
        if paging_url:
            return paging_url

        # 3. page=N パラメータを持つリンク
        return self._find_page_param_link(response)

    def _normalize_detail_url(self, href: str) -> str:
        full_url = self.getRootDestUrl(href)
        parsed = urllib.parse.urlparse(full_url)
        path = parsed.path
        if not path.endswith('/'):
            path += '/'
        return f"{self.BASE_URL}{path}"

    def _extract_detail_links(self, soup: BeautifulSoup, detail_links: set):
        for a in soup.select('a[href*="detail"]'):
            href = a.get("href")
            if href:
                normalized = self._normalize_detail_url(href)
                if normalized not in detail_links:
                    detail_links.add(normalized)
                    logging.info(f"[Daikyo] Match detail link: {normalized}")
                    yield normalized

    def _extract_pref_urls(self, response: BeautifulSoup) -> set:
        slug_map = {"kodate": "house", "tochi": "land"}
        target_slug = slug_map.get(self.property_type, "mansion")
        pref_pattern = re.compile(rf'/buy/{target_slug}/p\d+/?$')
        pref_urls = set()
        for a in response.find_all("a", href=pref_pattern):
            href = a.get("href")
            if href:
                pref_urls.add(self.getRootDestUrl(href))
        return pref_urls

    async def _crawl_pref_url(self, p_url: str, detail_links: set):
        curr_p_url = p_url
        visited_p_urls = {curr_p_url}
        while curr_p_url:
            try:
                p_html = await self._getContent(None, curr_p_url)
                if not p_html:
                    break
                p_soup = BeautifulSoup(p_html, "html.parser")
                for link in self._extract_detail_links(p_soup, detail_links):
                    yield link

                next_page = await self.parseNextPage(p_soup)
                if next_page and next_page not in visited_p_urls:
                    visited_p_urls.add(next_page)
                    curr_p_url = next_page
                else:
                    break
            except Exception as pe:
                logging.warning(f"[Daikyo] Failed to fetch pref {curr_p_url}: {pe}")
                break

    async def parseRootPage(self, response: BeautifulSoup):
        detail_links = set()
        for link in self._extract_detail_links(response, detail_links):
            yield link

        # 全国トップページ等の場合、各都道府県別URL (/buy/{type}/pXX/) を取得して展開
        pref_urls = self._extract_pref_urls(response)
        if pref_urls:
            for p_url in sorted(pref_urls):
                async for link in self._crawl_pref_url(p_url, detail_links):
                    yield link

    def _get_specs(self, response: BeautifulSoup) -> dict:
        specs = {}
        for row in response.select(".table-detail-01__content"):
            th = row.select_one(".table-detail-01__title")
            td = row.select_one(".table-detail-01__box")
            if th and td:
                key = th.get_text().strip().replace("\n", "").replace(" ", "")
                val = td.get_text().strip()
                val = re.sub(r'\s+', ' ', val)
                specs[key] = val
                
        for table in response.select("table"):
            for tr in table.select("tr"):
                ths = tr.find_all("th")
                tds = tr.find_all("td")
                for i in range(min(len(ths), len(tds))):
                    key = ths[i].get_text().strip().replace("\n", "").replace(" ", "")
                    val = tds[i].get_text().strip()
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
            price_el = response.select_one(".text-price-01") or response.select_one(".text-price-01__number")
            if price_el:
                price_val = price_el.get_text(strip=True)
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

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("築年", "") or specs.get("完成時期", "") or specs.get("完成年月", "") or specs.get("竣工年月", "") or specs.get("建築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        return item

class DaikyoMansionParser(DaikyoParser, MansionParserBase):
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
        return DaikyoMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = self._parseMadori(response, specs)
        
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)

        # 階数・所在階
        item.kaisuStr = specs.get("所在階/構造・階建", "") or specs.get("所在階", "") or specs.get("階数", "")
        if item.kaisuStr:
            m = re.search(r'(\d+)階', item.kaisuStr)
            if m:
                item.floorType_kai = int(m.group(1))
            m = re.search(r'地上(\d+)階', item.kaisuStr)
            if m:
                item.floorType_chijo = int(m.group(1))
            m = re.search(r'地下(\d+)階', item.kaisuStr)
            if m:
                item.floorType_chika = int(m.group(1))

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("築年", "") or specs.get("完成時期", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.balconyMensekiStr = specs.get("バルコニー面積", "")
        if item.balconyMensekiStr:
            item.balconyMenseki = converter.parse_menseki(item.balconyMensekiStr)

        # 総戸数
        item.soukosuStr = specs.get("総戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

        # 管理費/修繕積立金
        kanri_syuzen_val = specs.get("管理費/修繕積立金", "")
        if kanri_syuzen_val:
            parts = re.split(r'[／/]', kanri_syuzen_val)
            if len(parts) >= 1:
                item.kanrihiStr = parts[0].strip()
                item.kanrihi = converter.parse_rent(item.kanrihiStr)
            if len(parts) >= 2:
                item.syuzenTsumitateStr = parts[1].strip()
                item.syuzenTsumitate = converter.parse_rent(item.syuzenTsumitateStr)
        else:
            item.kanrihiStr = specs.get("管理費", "")
            if item.kanrihiStr:
                item.kanrihi = converter.parse_rent(item.kanrihiStr)
            item.syuzenTsumitateStr = specs.get("修繕積立金", "")
            if item.syuzenTsumitateStr:
                item.syuzenTsumitate = converter.parse_rent(item.syuzenTsumitateStr)

        item.kouzou = self._parseKouzou(response, specs)
        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        
        item.saikou = specs.get("主要採光", "") or specs.get("向き", "")
        item.saikouMuki = item.saikou
        item.saikouMukiStr = item.saikou
        item.saikouKadobeya = specs.get("角部屋", "")
        item.kadobeya = item.saikouKadobeya

        return item

class DaikyoKodateParser(DaikyoParser, KodateParserBase):
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
        return DaikyoKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = self._parseMadori(response, specs)

        item.tochiMensekiStr = specs.get("土地面積", "") or specs.get("敷地面積", "") or specs.get("土地公簿面積", "") or specs.get("公簿面積", "") or specs.get("区画面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
        else:
            from package.parser.baseParser import SkipPropertyException
            raise SkipPropertyException("DaikyoKodate: Non-kodate property mixed in search list.")


        item.tatemonoMensekiStr = specs.get("建物面積", "") or specs.get("延床面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)


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

class DaikyoTochiParser(DaikyoParser, TochiParserBase):
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
        return DaikyoTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "") or specs.get("敷地面積", "") or specs.get("土地公簿面積", "") or specs.get("公簿面積", "") or specs.get("区画面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
        else:
            from package.parser.baseParser import SkipPropertyException
            raise SkipPropertyException("DaikyoTochi: Non-tochi property mixed in search list.")



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
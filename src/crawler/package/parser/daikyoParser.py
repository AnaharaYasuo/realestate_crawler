# -*- coding: utf-8 -*-
import re
import logging
import urllib.parse
import asyncio
from bs4 import BeautifulSoup

from package.models.daikyo import DaikyoMansion, DaikyoKodate, DaikyoTochi
from package.parser.baseParser import ParserBase
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

class DaikyoParser(ParserBase):
    BASE_URL = 'https://www.daikyo-anabuki.co.jp'
    property_type = ""

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('daikyo', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        if linkUrl.startswith('/'):
            return self.BASE_URL + linkUrl
        return self.BASE_URL + "/" + linkUrl

    async def getResponseBs(self, session, url, charset=None) -> BeautifulSoup:
        from playwright.async_api import async_playwright
        logging.info(f"DaikyoParser: Launching Playwright to render JS for URL: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            try:
                await page.goto(url, timeout=30000, wait_until='domcontentloaded')
                if "detail" in url:
                    await page.wait_for_selector('table', timeout=15000)
                else:
                    await page.wait_for_selector('body', timeout=15000)
                await asyncio.sleep(3)
                content = await page.content()
                return BeautifulSoup(content, 'html.parser')
            except Exception as e:
                logging.error(f"DaikyoParser Playwright failed: {e}")
                return await super().getResponseBs(session, url, charset)
            finally:
                await context.close()
                await browser.close()

    async def parseNextPage(self, response: BeautifulSoup):
        for a in response.select(".paging a, .pager a"):
            text = a.get_text().strip()
            if "次" in text or ">" in text or "next" in text.lower():
                href = a.get("href")
                if href:
                    return self.getRootDestUrl(href)
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
                    logging.info(f"[Daikyo] Match detail link: {normalized}")
                    yield normalized

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
        item.genkyo = specs.get("現況", "") or specs.get("現状", "")
        item.tochikenri = specs.get("土地権利", "")
        item.torihiki = specs.get("取引態様", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "")

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("築年", "") or specs.get("完成時期", "") or specs.get("完成年月", "") or specs.get("竣工年月", "") or specs.get("建築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        return item

class DaikyoMansionParser(DaikyoParser):
    property_type = 'mansion'

    def createEntity(self):
        return DaikyoMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "")
        
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

        item.kouzou = specs.get("建物構造", "") or specs.get("構造", "")
        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        
        item.saikou = specs.get("主要採光", "") or specs.get("向き", "")
        item.saikouMuki = item.saikou
        item.saikouMukiStr = item.saikou
        item.saikouKadobeya = specs.get("角部屋", "")
        item.kadobeya = item.saikouKadobeya

        return item

class DaikyoKodateParser(DaikyoParser):
    property_type = 'kodate'

    def createEntity(self):
        return DaikyoKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "")

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        item.kouzou = specs.get("建物構造", "") or specs.get("構造", "")
        item.kaisuStr = specs.get("階数", "") or specs.get("階建", "")
        if item.kaisuStr:
            item.kaisu = converter.parse_numeric(item.kaisuStr)

        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)

        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = specs.get("用途地域", "")
        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")

        return item

class DaikyoTochiParser(DaikyoParser):
    property_type = 'tochi'

    def createEntity(self):
        return DaikyoTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.kenchikuJoken = specs.get("建築条件", "")
        item.chimoku = specs.get("地目", "")
        
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)

        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = specs.get("用途地域", "")
        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")

        return item

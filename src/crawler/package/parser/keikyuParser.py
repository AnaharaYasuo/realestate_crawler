# -*- coding: utf-8 -*-
import sys
import re
import logging
import urllib.parse
import asyncio
from bs4 import BeautifulSoup
from django.db import models

from package.models.keikyu import KeikyuMansion, KeikyuKodate, KeikyuTochi
from package.parser.baseParser import ParserBase
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

class KeikyuParser(ParserBase):
    BASE_URL = 'https://www.keikyu-sumai.com'
    property_type = ""

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('keikyu', self.property_type or 'mansion')

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
        logging.info(f"KeikyuParser: Launching Playwright to render JS for URL: {url}")
        
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
                logging.error(f"KeikyuParser Playwright failed: {e}")
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
                    logging.info(f"[Keikyu] Match detail link: {normalized}")
                    yield normalized

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
        # 上部サマリーの抽出
        for dl in response.select("dl.searchresult-detail-list"):
            for dt, dd in zip(dl.select("dt"), dl.select("dd")):
                key = dt.get_text().strip().replace("\n", "").replace(" ", "").replace("：", "")
                val = dd.get_text().strip()
                val = re.sub(r'\s+', ' ', val)
                specs[key] = val

        # キーの表記揺れ標準化マッピングを追加
        fallback_mappings = {
            "面積": ["専有面積", "建物面積", "建物延面積", "土地面積"],
            "管理費": ["管理費等", "管理費/月"],
            "修繕積立金": ["修繕積立金等", "修繕積立金/月", "積立金"],
            "交通": ["最寄り駅", "最寄駅", "アクセス"],
            "現現況": ["現況", "現状", "入居状況"],
            "建物構造": ["構造", "構造・規模"],
            "引渡": ["引渡時期", "引渡/入居時期"]
        }
        for std_key, alt_keys in fallback_mappings.items():
            for alt in alt_keys:
                if alt in specs and std_key not in specs:
                    specs[std_key] = specs[alt]
                # 反対方向の補完
                if std_key in specs and alt not in specs:
                    specs[alt] = specs[std_key]
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
        if price_val:
            item.priceStr = price_val
            item.price = converter.parse_price(item.priceStr)

        # 所在地
        addr_val = specs.get("所在地", "") or specs.get("住所", "")
        if addr_val:
            item.address = addr_val
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        # 交通
        traffic_str = specs.get("交通", "") or specs.get("路線・駅", "")
        if traffic_str:
            self._populateTraffic(item, traffic_str)

        item.biko = specs.get("備考", "") or specs.get("その他", "")
        item.genkyo = specs.get("現況", "") or specs.get("現状", "")
        item.tochikenri = specs.get("土地権利", "")
        item.torihiki = specs.get("取引態様", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "")

        return item

class KeikyuMansionParser(KeikyuParser):
    property_type = 'mansion'

    def createEntity(self):
        return KeikyuMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "")
        
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)

        # 階数・所在階
        item.kaisuStr = specs.get("所在階/構造・階建", "") or specs.get("所在階", "") or specs.get("階数", "") or specs.get("構造・規模", "")
        if item.kaisuStr:
            # 所在階の抽出 (例: 3階 / 地上10階)
            m = re.search(r'(\d+)階', item.kaisuStr)
            if m:
                item.floorType_kai = int(m.group(1))
            # 地上階建の抽出
            m_chijo = re.search(r'(?:地上|造)(\d+)階建', item.kaisuStr) or re.search(r'地上(\d+)階', item.kaisuStr)
            if m_chijo:
                item.floorType_chijo = int(m_chijo.group(1))
            # 地下階建の抽出
            m_chika = re.search(r'地下(\d+)階建', item.kaisuStr) or re.search(r'地下(\d+)階', item.kaisuStr)
            if m_chika:
                item.floorType_chika = int(m_chika.group(1))
            else:
                item.floorType_chika = 0

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("完成時期", "")
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

        item.kouzou = specs.get("建物構造", "") or specs.get("構造", "")
        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        
        item.saikou = specs.get("主要採光", "") or specs.get("向き", "")
        item.saikouMuki = item.saikou
        item.saikouMukiStr = item.saikou
        item.saikouKadobeya = specs.get("角部屋", "")
        item.kadobeya = item.saikouKadobeya

        return item

class KeikyuKodateParser(KeikyuParser):
    property_type = 'kodate'

    def createEntity(self):
        return KeikyuKodate()

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

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

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

class KeikyuTochiParser(KeikyuParser):
    property_type = 'tochi'

    def createEntity(self):
        return KeikyuTochi()

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

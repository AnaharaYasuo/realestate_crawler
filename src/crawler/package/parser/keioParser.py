# -*- coding: utf-8 -*-
import sys
import re
import logging
import urllib.parse
import asyncio
from bs4 import BeautifulSoup
from django.db import models

from package.models.keio import KeioMansion, KeioKodate, KeioTochi
from package.parser.baseParser import ParserBase
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

class KeioParser(ParserBase):
    BASE_URL = 'https://chukai.keiofudosan.co.jp'
    property_type = ""

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('keio', self.property_type)

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            url = linkUrl
        elif linkUrl.startswith('/'):
            url = self.BASE_URL + linkUrl
        else:
            url = self.BASE_URL + "/sale/search/area/pref_13/" + linkUrl

        # パラメータ重複除去
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qsl(parsed.query)
        seen = set()
        clean_params = []
        for k, v in params:
            if k not in seen:
                clean_params.append((k, v))
                seen.add(k)
        query = urllib.parse.urlencode(clean_params)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))

    async def getResponseBs(self, session, url, charset=None) -> BeautifulSoup:
        from playwright.async_api import async_playwright
        logging.info(f"KeioParser: Launching Playwright to render JS for URL: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                ]
            )
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            try:
                # ページの読込（タイムアウト30秒）
                await page.goto(url, timeout=30000, wait_until='domcontentloaded')
                
                # 一覧ページの場合は article.data、詳細ページの場合は table.spec_table_default の出現を待つ
                if "/sale/" in url and url.split("/sale/")[-1].strip("/").isdigit():
                    await page.wait_for_selector('table.spec_table_default', timeout=20000)
                else:
                    await page.wait_for_selector('article.data', timeout=20000)
                    
                await asyncio.sleep(2)
                
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                return soup
            except Exception as e:
                logging.error(f"KeioParser: Playwright rendering failed: {e}")
                # 失敗した場合はフォールバック
                return await super().getResponseBs(session, url, charset)
            finally:
                await context.close()
                await browser.close()

    async def parseNextPage(self, response: BeautifulSoup):
        # ページネーション内の a.pager.current (アクティブなページ) の次のリンクを探す
        current = response.select_one("div.block_pager a.pager.current")
        if current:
            next_el = current.find_next_sibling("a", class_="pager")
            if next_el:
                href = next_el.get("href")
                if href and "page_num=" in href:
                    return self.getRootDestUrl(href)
        else:
            # 別のクラス指定「next」などがあるか、またはテキストチェック
            for a in response.select("div.block_pager a.pager"):
                text = a.get_text().strip()
                if "次" in text or ">" in text:
                    href = a.get("href")
                    if href and "page_num=" in href:
                        return self.getRootDestUrl(href)
        return ""

    async def parseRootPage(self, response: BeautifulSoup):
        detail_links = set()
        
        # 物件種別から実際の検索結果パスを解決
        base_search_url = "https://chukai.keiofudosan.co.jp/sale/search/area/pref_13/"
        
        for a in response.find_all("a", class_="abs_link"):
            href = a.get("href")
            if href:
                # /sale/<id>/ のパターンを抽出する
                if "/sale/" in href and href.strip("/").split("/")[-1].isdigit():
                    full_url = urllib.parse.urljoin(base_search_url, href)
                    parsed = urllib.parse.urlparse(full_url)
                    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if normalized not in detail_links:
                        detail_links.add(normalized)
                        logging.info(f"[Keio] Match detail link: {normalized}")
                        yield normalized

    def _get_specs(self, response: BeautifulSoup) -> dict:
        specs = {}
        for table in response.select("table.spec_table_default"):
            for tr in table.select("tr"):
                ths = tr.find_all("th")
                tds = tr.find_all("td")
                for i in range(min(len(ths), len(tds))):
                    key = ths[i].get_text().strip().replace("\n", "").replace(" ", "")
                    val = tds[i].get_text().strip()
                    # 不要なテキスト（住宅ローンシミュレーションへのリンク等）の除外
                    val = re.sub(r'ローンシミュレーション', '', val).strip()
                    val = re.sub(r'\s+', ' ', val)
                    specs[key] = val
        return specs

    def _split_address(self, address):
        return super()._split_address(address)

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)
        item.propertyName = self._parsePropertyName(response)
            
        # 価格
        price_val = specs.get("価格", "")
        if price_val:
            item.priceStr = price_val
            item.price = converter.parse_price(item.priceStr)

        # 所在地
        addr_val = specs.get("所在地", "")
        if addr_val:
            item.address = addr_val
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        # 交通
        traffic_str = specs.get("交通", "")
        if traffic_str:
            traffic_lines = re.split(r'\s{2,}', traffic_str)
            if len(traffic_lines) <= 1:
                traffic_lines = traffic_str.split("\n")
            self._populateTraffic(item, [t.strip() for t in traffic_lines if t.strip()])

        item.biko = specs.get("備考", "")
        item.genkyo = specs.get("現況", "")
        item.tochikenri = specs.get("土地権利", "") or specs.get("権利", "")
        item.torihiki = specs.get("取引態様", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "")

        return item

class KeioMansionParser(KeioParser):
    property_type = 'mansion'

    def createEntity(self):
        return KeioMansion()

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
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.balconyMensekiStr = specs.get("バルコニー面積", "") or specs.get("屋外設備", "")
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

class KeioKodateParser(KeioParser):
    property_type = 'kodate'

    def createEntity(self):
        return KeioKodate()

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

class KeioTochiParser(KeioParser):
    property_type = 'tochi'

    def createEntity(self):
        return KeioTochi()

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

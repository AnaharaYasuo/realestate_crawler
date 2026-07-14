# -*- coding: utf-8 -*-
import sys
import re
import logging
import urllib.parse
import asyncio
from bs4 import BeautifulSoup
from django.db import models

from package.models.heim import HeimMansion, HeimKodate, HeimTochi
from package.parser.baseParser import ParserBase
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

class HeimParser(ParserBase):
    BASE_URL = 'https://www.sumu-heim.jp'
    property_type = ""

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('heim', self.property_type)

    async def getResponseBs(self, session, url, charset=None) -> BeautifulSoup:
        from playwright.async_api import async_playwright
        logging.info(f"HeimParser: Launching Playwright to render JS for URL: {url}")
        
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
                # ページの読込。タイムアウトは30秒。
                await page.goto(url, timeout=30000, wait_until='domcontentloaded')
                # 物件リスト .property_list が表示されるまで待つ
                await page.wait_for_selector('.property_list', timeout=20000)
                await asyncio.sleep(2)
                
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                return soup
            except Exception as e:
                logging.error(f"HeimParser: Playwright rendering failed: {e}")
                # 失敗した場合は、親クラスの aiohttp によるフォールバックを呼ぶ
                return await super().getResponseBs(session, url, charset)
            finally:
                await context.close()
                await browser.close()

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        return self.BASE_URL + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        next_a = response.select_one(".pagination .next a, .pager .next a, a.next, li.next a")
        if next_a:
            href = next_a.get("href")
            if href:
                return self.getRootDestUrl(href)
        return ""

    async def parseRootPage(self, response: BeautifulSoup):
        detail_links = set()
        
        # 物件種別から実際のURLパス名へのマッピング
        type_map = {
            'mansion': 'mansion',
            'tochi': 'land',
            'kodate': 'kodate'
        }
        target_path = type_map.get(self.property_type, 'mansion')
        
        for a in response.find_all("a"):
            href = a.get("href")
            if href:
                logging.debug(f"[Heim Debug] Found href: {href}")
                # 'detail.php', 'cid=', 'id=' が含まれ、かつ対象物件種別名が含まれるか確認
                if "detail.php" in href and "cid=" in href and "id=" in href and target_path in href:
                    # 一覧ページのURL (https://www.sumu-heim.jp/buy/list.php) をベースに相対パスを解決
                    full_url = urllib.parse.urljoin("https://www.sumu-heim.jp/buy/list.php", href)
                    parsed = urllib.parse.urlparse(full_url)
                    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{parsed.query}"
                    if normalized not in detail_links:
                        detail_links.add(normalized)
                        logging.info(f"[Heim] Match detail link: {normalized}")
                        yield normalized

    def _get_specs(self, response: BeautifulSoup) -> dict:
        specs = {}
        # すむハイムのスペック表コンテナ .b_table .tr 構造
        table = response.select_one(".b_table")
        if table:
            for row in table.select(".tr"):
                th = row.select_one(".th")
                td = row.select_one(".td")
                if th and td:
                    # キーと値を取得
                    key = th.get_text().strip()
                    val = td.get_text().strip()
                    specs[key] = val
        return specs

    def _split_address(self, address):
        return super()._split_address(address)

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        
        # タイトル/物件名
        title_el = response.select_one("div.title_header > h2")
        if title_el:
            item.propertyName = title_el.get_text().strip()
            
        # 物件スペック表の取得
        specs = self._get_specs(response)
        
        # 価格
        price_el = response.select_one("div.price_box > h5 > span")
        if price_el:
            item.priceStr = price_el.get_text().strip()
            item.price = converter.parse_price(item.priceStr)
        elif "価格" in specs:
            item.priceStr = specs.get("価格", "")
            item.price = converter.parse_price(item.priceStr)

        # 所在地
        addr_p = response.select_one("p.place")
        if addr_p:
            # 内包されている「マップを見る」のaタグ等は除外する
            for a in addr_p.find_all("a"):
                a.decompose()
            item.address = addr_p.get_text().strip()
        else:
            item.address = specs.get("所在地", "")

        if item.address:
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        # 交通
        traffic_str = specs.get("交通", "")
        if traffic_str:
            # 複数交通路線の分割処理
            traffic_lines = re.split(r'\s{2,}', traffic_str)
            if len(traffic_lines) <= 1:
                traffic_lines = traffic_str.split(" ")
            self._populateTraffic(item, [t.strip() for t in traffic_lines if t.strip()])

        item.biko = specs.get("備考", "")
        item.genkyo = specs.get("現況", "")
        item.tochikenri = specs.get("土地権利", "")
        item.torihiki = specs.get("取引態様", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡時期/現況", "")

        return item

class HeimMansionParser(HeimParser):
    property_type = 'mansion'

    def createEntity(self):
        return HeimMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "")
        
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)

        # 階数・所在階
        item.kaisuStr = specs.get("階建/所在階", "") or specs.get("階数", "")
        if item.kaisuStr:
            m = re.search(r'(\d+)階部分', item.kaisuStr)
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

        item.kouzou = specs.get("建物構造", "")
        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        
        item.saikou = specs.get("主要採光面", "") or specs.get("向き", "")
        item.saikouMuki = item.saikou
        item.saikouMukiStr = item.saikou
        item.saikouKadobeya = specs.get("角部屋", "")
        item.kadobeya = item.saikouKadobeya

        return item

class HeimKodateParser(HeimParser):
    property_type = 'kodate'

    def createEntity(self):
        return HeimKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "")

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "") or specs.get("延床面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.kouzou = specs.get("建物構造", "")
        item.kaisuStr = specs.get("階数", "")
        if item.kaisuStr:
            item.kaisu = converter.parse_numeric(item.kaisuStr)

        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)

        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = specs.get("用途地域", "")
        item.setsudou = specs.get("接道状況", "")

        return item

class HeimTochiParser(HeimParser):
    property_type = 'tochi'

    def createEntity(self):
        return HeimTochi()

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
        item.setsudou = specs.get("接道状況", "")

        return item

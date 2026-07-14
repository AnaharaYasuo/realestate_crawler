# -*- coding: utf-8 -*-
import sys
import re
import logging
import urllib.parse
import asyncio
from bs4 import BeautifulSoup
from django.db import models

from package.models.rearie import RearieMansion, RearieKodate, RearieTochi
from package.parser.baseParser import ParserBase
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

class RearieParser(ParserBase):
    BASE_URL = 'https://homes.panasonic.com'
    property_type = ""

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('rearie', self.property_type)

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            url = linkUrl
        elif linkUrl.startswith('/'):
            url = self.BASE_URL + linkUrl
        else:
            url = self.BASE_URL + "/rearie/" + linkUrl
            
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
        logging.info(f"RearieParser: Launching Playwright to render JS for URL: {url}")
        
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
                
                # 一覧ページの場合は .props-list、詳細ページの場合は dl.table-view の出現を待つ
                if "detail.html" in url:
                    await page.wait_for_selector('dl.table-view', timeout=20000)
                else:
                    await page.wait_for_selector('.props-list', timeout=20000)
                    
                await asyncio.sleep(2)
                
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                return soup
            except Exception as e:
                logging.error(f"RearieParser: Playwright rendering failed: {e}")
                # 失敗した場合は、親クラスの aiohttp によるフォールバックを呼ぶ
                return await super().getResponseBs(session, url, charset)
            finally:
                await context.close()
                await browser.close()

    async def parseNextPage(self, response: BeautifulSoup):
        # ページネーションの「次へ」リンクを探す
        next_a = response.select_one("a.pager__item-next")
        if next_a:
            href = next_a.get("href")
            if href and "page=" in href:
                style = next_a.get("style", "")
                if "display: none" not in style:
                    return self.getRootDestUrl(href)
        return ""

    async def parseRootPage(self, response: BeautifulSoup):
        detail_links = set()
        
        # 物件種別から実際のURLパス名へのマッピング
        type_map = {
            'mansion': 'mansion',
            'tochi': 'land',
            'kodate': 'house'
        }
        target_path = type_map.get(self.property_type, 'mansion')
        
        # 一覧ページのベースURL
        base_search_url = f"https://homes.panasonic.com/rearie/buy/property/{target_path}/list.html"
        
        for a in response.find_all("a"):
            href = a.get("href")
            if href:
                # 'detail.html' と 'id=' が含まれる詳細物件リンクを探す
                if "detail.html" in href and "id=" in href and target_path in href:
                    full_url = urllib.parse.urljoin(base_search_url, href)
                    parsed = urllib.parse.urlparse(full_url)
                    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{parsed.query}"
                    if normalized not in detail_links:
                        detail_links.add(normalized)
                        logging.info(f"[Rearie] Match detail link: {normalized}")
                        yield normalized

    def _get_specs(self, response: BeautifulSoup) -> dict:
        specs = {}
        for dl in response.select("dl.table-view"):
            dts = dl.find_all("dt")
            for dt in dts:
                dd = dt.find_next_sibling("dd")
                if dt and dd:
                    key = dt.get_text().strip().replace("\n", "").replace(" ", "")
                    val = dd.get_text().strip()
                    specs[key] = val
        return specs

    def _split_address(self, address):
        return super()._split_address(address)

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        
        # タイトル/物件名
        title_el = response.find("h1")
        if title_el:
            # 改行や不要な空白などを整理
            raw_title = title_el.get_text().strip()
            # 複数行ある場合は最初の行を物件名にする
            item.propertyName = raw_title.split("\n")[0].strip()
            
        # 物件スペック表の取得
        specs = self._get_specs(response)
        
        # 価格
        price_val = specs.get("価格", "")
        if price_val:
            item.priceStr = price_val
            item.price = converter.parse_price(item.priceStr)

        # 所在地
        addr_val = specs.get("所在地", "")
        if addr_val:
            # 「周辺地図を閉じる」などの不要文字を除去
            item.address = addr_val.replace("周辺地図を閉じる", "").strip()
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        # 交通
        traffic_str = specs.get("アクセス", "")
        if traffic_str:
            traffic_lines = re.split(r'\s{2,}', traffic_str)
            if len(traffic_lines) <= 1:
                traffic_lines = traffic_str.split("\n")
            self._populateTraffic(item, [t.strip() for t in traffic_lines if t.strip()])

        item.biko = specs.get("備考", "")
        item.genkyo = specs.get("現況", "") or specs.get("現況/引渡時期", "")
        item.tochikenri = specs.get("土地権利", "") or specs.get("敷地権利", "")
        item.torihiki = specs.get("取引態様", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "")

        return item

class RearieMansionParser(RearieParser):
    property_type = 'mansion'

    def createEntity(self):
        return RearieMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "") or specs.get("間取り/内訳", "")
        
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)

        # 階数・所在階
        item.kaisuStr = specs.get("階/階建", "") or specs.get("階数", "")
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

        item.balconyMensekiStr = specs.get("バルコニー", "") or specs.get("バルコニー面積", "")
        if item.balconyMensekiStr:
            item.balconyMenseki = converter.parse_menseki(item.balconyMensekiStr)

        # 総戸数
        item.soukosuStr = specs.get("総戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

        item.kanrihiStr = specs.get("管理費等", "") or specs.get("管理費", "")
        if item.kanrihiStr:
            item.kanrihi = converter.parse_rent(item.kanrihiStr)

        item.syuzenTsumitateStr = specs.get("修繕積立金", "")
        if item.syuzenTsumitateStr:
            item.syuzenTsumitate = converter.parse_rent(item.syuzenTsumitateStr)

        item.kouzou = specs.get("構造", "") or specs.get("建物構造", "")
        item.kanriKeitai = specs.get("管理形態", "") or specs.get("管理形態/管理員の勤務形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        
        item.saikou = specs.get("主要採光", "") or specs.get("向き", "")
        item.saikouMuki = item.saikou
        item.saikouMukiStr = item.saikou
        item.saikouKadobeya = specs.get("角部屋", "")
        item.kadobeya = item.saikouKadobeya

        return item

class RearieKodateParser(RearieParser):
    property_type = 'kodate'

    def createEntity(self):
        return RearieKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "") or specs.get("間取り/内訳", "")

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

        item.kouzou = specs.get("構造", "") or specs.get("建物構造", "")
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

class RearieTochiParser(RearieParser):
    property_type = 'tochi'

    def createEntity(self):
        return RearieTochi()

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

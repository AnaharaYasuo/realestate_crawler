# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase
from package.models.sekisui import SekisuiMansion, SekisuiKodate, SekisuiTochi
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
import logging
import re
from decimal import Decimal
import datetime
import unicodedata

class SekisuiParser(ParserBase):
    BASE_URL = 'https://sumusite.sekisuihouse.co.jp'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('sekisui', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        if linkUrl.startswith('//'):
            return 'https:' + linkUrl
        return self.BASE_URL + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        # aタグから「次へ」や「次」のテキストを持つリンクを探索
        for a in response.find_all("a"):
            text = a.get_text().strip()
            if "次" in text or "next" in text.lower():
                href = a.get("href")
                if href:
                    return self.getRootDestUrl(href)
        return ""

    async def parseRootPage(self, response):
        detail_links = set()
        # /detail/C20010050622/ のようなID形式にマッチする href を正規表現で抽出
        for a in response.find_all("a", href=re.compile(r'/detail/[A-Za-z0-9]+/')):
            href = a.get("href")
            if href:
                full_url = self.getRootDestUrl(href)
                import urllib.parse
                parsed = urllib.parse.urlparse(full_url)
                normalized = f"{self.BASE_URL}{parsed.path}"
                if normalized not in detail_links:
                    detail_links.add(normalized)
                    yield normalized

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)

        # 住所分割
        if item.address:
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        # 交通情報のパース
        traffic_lines = self._parseTrafficLines(response)
        self._populateTraffic(item, traffic_lines)

        # 共通テーブルスペック
        specs = self._get_specs(response)
        item.biko = specs.get("備考", "")
        item.genkyo = specs.get("現況", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引渡可能時期", "")
        item.tochikenri = specs.get("土地権利", "")
        item.torihiki = specs.get("取引態様", "")

        return item

    def _parsePropertyName(self, response: BeautifulSoup):
        h1 = response.find("h1")
        if h1:
            return h1.get_text().strip()
        title_elem = response.select_one(".detail-header__title, .property-title, .title")
        if title_elem:
            return title_elem.get_text().strip()
        return ""

    def _parsePriceStr(self, response: BeautifulSoup):
        price_elem = response.select_one(".detail-header__price, .price-value, .property-price, .price")
        if price_elem:
            return price_elem.get_text().strip()
        specs = self._get_specs(response)
        return specs.get("価格", "")

    def _parsePrice(self, response: BeautifulSoup):
        price_str = self._parsePriceStr(response)
        if price_str:
            return converter.parse_price(price_str)
        return 0

    def _parseAddress(self, response: BeautifulSoup):
        specs = self._get_specs(response)
        return specs.get("所在地", "")

    def _split_address(self, address):
        return super()._split_address(address)

    def _get_specs(self, response: BeautifulSoup):
        # Sekisui specific specifications parsing
        specs = {}
        
        # 1. dl -> dt / dd structure
        for dl in response.find_all("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                key = dt.get_text().strip()
                val = dd.get_text().strip()
                val = re.sub(r'\s+', ' ', val)
                if key:
                    specs[key] = val
                    
        # 2. li -> p class="title" / p structure
        for li in response.find_all("li"):
            title_p = li.find("p", class_="title")
            if title_p:
                val_p = title_p.find_next_sibling("p")
                if val_p:
                    key = title_p.get_text().strip()
                    val = val_p.get_text().strip()
                    val = re.sub(r'\s+', ' ', val)
                    if key:
                        specs[key] = val
                        
        # 3. Normal tr/th/td tables
        for tr in response.find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if th and td:
                key = th.get_text().strip()
                val = td.get_text().strip()
                val = re.sub(r'\s+', ' ', val)
                if key:
                    specs[key] = val

        return specs

    def _parseTrafficLines(self, response: BeautifulSoup):
        specs = self._get_specs(response)
        traffic_text = specs.get("交通", "")
        if not traffic_text:
            return []
        lines = []
        # 改行やカンマで分割
        for l in re.split(r'[\r\n、]+', traffic_text):
            l = l.strip()
            # 「駅徒歩...」などの直後に改行なしで次の路線が繋がっている場合に分割
            parts = re.split(r'(?<=\)駅)|(?<=分\))|(?<=分)|(?<=m\))', l)
            for part in parts:
                part = part.strip()
                if part:
                    lines.append(part)
        return lines



class SekisuiMansionParser(SekisuiParser):
    property_type = 'mansion'

    def createEntity(self):
        return SekisuiMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "")
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)
            
        item.kaisuStr = specs.get("所在階", "") or specs.get("階数", "")
        if item.kaisuStr:
            item.floorType_kai = converter.parse_numeric(item.kaisuStr)

        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("完成年月", "") or specs.get("竣工年月", "") or specs.get("築年", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.balconyMensekiStr = specs.get("バルコニー面積", "")
        if item.balconyMensekiStr:
            item.balconyMenseki = converter.parse_menseki(item.balconyMensekiStr)

        item.saikou = specs.get("主要採光面", "") or specs.get("採光", "")
        item.soukosuStr = specs.get("総戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

        item.kanrihiStr = specs.get("管理費", "") or specs.get("管理費等", "")
        if item.kanrihiStr:
            item.kanrihi = converter.parse_yen(item.kanrihiStr)

        item.syuzenTsumitateStr = specs.get("修繕積立金", "")
        if item.syuzenTsumitateStr:
            item.syuzenTsumitate = converter.parse_yen(item.syuzenTsumitateStr)

        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        item.kouzou = specs.get("構造", "")
        
        return item


class SekisuiKodateParser(SekisuiParser):
    property_type = 'kodate'

    def createEntity(self):
        return SekisuiKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "") or specs.get("延床面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        item.kaisuStr = specs.get("階数", "") or specs.get("建物階数", "")
        item.madori = specs.get("間取り", "")
        item.kouzou = specs.get("構造", "") or specs.get("建物構造", "")
        
        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("完成年月", "") or specs.get("竣工年月", "") or specs.get("築年", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")
        
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")
        
        return item


class SekisuiTochiParser(SekisuiParser):
    property_type = 'tochi'

    def createEntity(self):
        return SekisuiTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.kenchikuJoken = specs.get("建築条件", "") or specs.get("建築条件付土地", "")
        item.chimoku = specs.get("地目", "")
        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")

        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")

        return item

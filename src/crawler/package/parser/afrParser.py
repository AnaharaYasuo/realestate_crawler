# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase
from package.models.afr import AfrMansion, AfrKodate, AfrTochi
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
import logging
import re
from decimal import Decimal
import datetime
import urllib.parse

class AfrParser(ParserBase):
    BASE_URL = 'https://www.hebel-haus.com'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('afr', self.property_type or 'kodate')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        return self.BASE_URL + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        # 1回のAjaxで全物件がロードされるため、改ページ巡回は不要です。
        return ""

    async def parseRootPage(self, response: BeautifulSoup):
        # レンスポンスHTMLに含まれる「MYSERACH.bukken.push」の物件番号を全抽出する
        html_str = str(response)
        
        # 'number': 'BMS09818' のパターンを検索
        detail_ids = set(re.findall(r"'number':\s*'([^']+)'", html_str))
        
        logging.info(f"AfrParser: Extracted {len(detail_ids)} property numbers from search list.")
        
        next_page = '/stockhebel/purchase/forhome/details.html'
        if self.property_type == 'investment':
            next_page = '/stockhebel/purchase/investment/details.html'
            
        for bno in sorted(list(detail_ids)):
            detail_url = f"{self.BASE_URL}{next_page}?bno={bno}"
            yield detail_url

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
        item.biko = specs.get("備考", "") or specs.get("その他", "")
        item.genkyo = specs.get("現状", "") or specs.get("現況", "")
        item.hikiwatashi = specs.get("引渡日", "") or specs.get("引渡", "") or specs.get("引渡時期", "")
        item.tochikenri = specs.get("土地権利", "")
        item.torihiki = specs.get("取引態様", "")

        return item

    def _parsePropertyName(self, response: BeautifulSoup):
        # H2要素のうち「物件画像」や「おすすめポイント」などの定型表現を除外して物件名を見つける
        ignore_titles = ["物件詳細", "物件画像", "間取り", "物件タイプ", "おすすめポイント", 
                         "建物メンテナンス情報", "物件情報", "お問い合わせ", 
                         "satisfaction", "recommendation", "検索条件変更"]
        for h2 in response.find_all("h2"):
            text = h2.get_text().strip()
            if text and not any(ign in text.lower() for ign in ignore_titles):
                return text
        # 見つからない場合はH1またはtitleから
        h1 = response.find("h1")
        if h1:
            return h1.get_text().strip()
        return ""

    def _parsePriceStr(self, response: BeautifulSoup):
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

    def _parseTrafficLines(self, response: BeautifulSoup):
        traffic_lines = []
        specs = self._get_specs(response)
        access_str = specs.get("交通", "")
        if access_str:
            lines = [line.strip() for line in re.split(r'[\r\n]+', access_str) if line.strip()]
            for line in lines:
                traffic_lines.append(line)
        return traffic_lines

    def _parseImages(self, response: BeautifulSoup):
        images = []
        # 「/photo/356px/」を含む高解像度画像を優先して抽出
        for img in response.find_all("img"):
            src = img.get("src")
            if src and "/photo/356px/" in src:
                full_url = self.getRootDestUrl(src)
                alt = img.get("alt", "")
                if full_url not in images:
                    images.append(full_url)
        return images

class AfrMansionParser(AfrParser):
    property_type = 'mansion'

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = AfrMansion

    def createEntity(self):
        return AfrMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 間取り
        item.madori = specs.get("間取り", "")

        # 専有面積
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)

        # 所在階・総階数
        item.kaisuStr = specs.get("所在階", "")
        item.soukaisuStr = specs.get("総階数", "")
        item.soukosuStr = specs.get("総戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        # 管理費・修繕積立金
        item.kanrihiStr = specs.get("管理費", "")
        if item.kanrihiStr:
            item.kanrihi = converter.parse_price(item.kanrihiStr) # 単位が円や万円の場合に対応
        item.syuzenTsumitateStr = specs.get("修繕積立金", "")
        if item.syuzenTsumitateStr:
            item.syuzenTsumitate = converter.parse_price(item.syuzenTsumitateStr)

        # 建物構造・管理形態
        item.kouzou = specs.get("構造", "") or specs.get("建物構造", "")
        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        item.balconyMensekiStr = specs.get("バルコニー面積", "")
        item.saikou = specs.get("主要採光面", "")

        return item

class AfrKodateParser(AfrParser):
    property_type = 'kodate'

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = AfrKodate

    def createEntity(self):
        return AfrKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 土地面積
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        # 建物面積
        item.tatemonoMensekiStr = specs.get("建物面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        # 構造・階数
        item.kouzou = specs.get("建物構造", "")
        item.kaisuStr = specs.get("階数", "")
        if item.kaisuStr:
            item.kaisu = converter.parse_numeric(item.kaisuStr)

        item.madori = specs.get("間取り", "")
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        # 建ぺい率・容積率
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        # 用途地域・都市計画
        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = specs.get("接道状況", "")

        return item

class AfrTochiParser(AfrParser):
    property_type = 'tochi'

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = AfrTochi

    def createEntity(self):
        return AfrTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 土地面積
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        # 建ぺい率・容積率
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        # 都市計画・用途地域
        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = specs.get("接道状況", "")
        item.chimoku = specs.get("地目", "")
        item.kenchikuJoken = specs.get("建築条件", "")

        return item

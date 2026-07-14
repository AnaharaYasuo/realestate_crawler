# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase
from package.models.smtrc import SmtrcMansion, SmtrcKodate, SmtrcTochi, SmtrcInvestment
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
import logging
import re
from decimal import Decimal
import datetime
import unicodedata

class SmtrcParser(ParserBase):
    BASE_URL = 'https://smtrc.jp'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('smtrc', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        return self.BASE_URL + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        # ページネーションリンクを探索
        for a in response.find_all("a"):
            text = a.get_text()
            if "次の" in text or "次へ" in text or "next" in text.lower():
                href = a.get("href")
                if href:
                    return self.getRootDestUrl(href)
        return ""

    async def parseRootPage(self, response):
        # 物件一覧ページから詳細リンクを抽出
        detail_links = set()
        for a in response.find_all("a", href=re.compile(r'/detail/CompareDetails')):
            href = a.get("href")
            if href:
                full_url = self.getRootDestUrl(href)
                import urllib.parse
                parsed = urllib.parse.urlparse(full_url)
                query = urllib.parse.parse_qs(parsed.query)
                code = query.get("propertyCode", [""])[0]
                if code:
                    normalized = f"{self.BASE_URL}/detail/CompareDetails?propertyCode={code}&pageId=D010"
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
        self._populateTraffic(item, "  ".join(traffic_lines))

        # 共通テーブルスペック
        specs = self._get_specs(response)
        item.biko = specs.get("備考", "")
        item.genkyo = specs.get("現況", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引渡可能時期", "")
        item.tochikenri = specs.get("土地権利", "")
        item.torihiki = specs.get("取引態様", "")

        # 築年月（表記揺れ 建築年月 もサポート）
        item.chikunengetsuStr = specs.get("築年月") or specs.get("建築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        return item

    def _parsePriceStr(self, response: BeautifulSoup):
        price_elem = response.select_one(".price-value, .property-price")
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

    def _parseTrafficLines(self, response: BeautifulSoup):
        specs = self._get_specs(response)
        traffic_text = specs.get("交通", "")
        if not traffic_text:
            return []
        # 改行や「、」で分割
        lines = []
        for l in re.split(r'[\r\n、]+', traffic_text):
            l = l.strip()
            if l:
                lines.append(l)
        return lines

class SmtrcMansionParser(SmtrcMansionParser if False else SmtrcParser):
    property_type = 'mansion'

    def createEntity(self):
        return SmtrcMansion()

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
        item.bunjoKaisya = specs.get("分譲会社", "")
        item.sekouKaisya = specs.get("施工会社", "")
        
        return item


class SmtrcKodateParser(SmtrcParser):
    property_type = 'kodate'

    def createEntity(self):
        return SmtrcKodate()

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

        # 都市計画関連
        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")
        
        # 建ぺい率・容積率
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        # 接道状況の抽出
        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")
        
        return item


class SmtrcTochiParser(SmtrcParser):
    property_type = 'tochi'

    def createEntity(self):
        return SmtrcTochi()

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
        item.kokudoHou = specs.get("国土法届出", "") or specs.get("国土法", "")

        # 建ぺい率・容積率
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")

        return item


class SmtrcInvestmentParser(SmtrcParser):
    property_type = 'investment'

    def createEntity(self):
        return SmtrcInvestment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 表面利回り
        gross_yield_str = specs.get("利回り", "") or specs.get("表面利回り", "") or specs.get("想定利回り", "")
        if gross_yield_str:
            item.grossYield = converter.parse_ratio(gross_yield_str)

        # 想定年間収入
        annual_rent_str = specs.get("想定年間収入", "") or specs.get("年間想定収入", "") or specs.get("想定収入", "") or specs.get("現行年間収入", "")
        if annual_rent_str:
            rent_val = converter.parse_rent(annual_rent_str)
            if rent_val:
                item.annualRent = rent_val
                item.monthlyRent = rent_val // 12

        item.currentStatus = specs.get("現況", "")
        item.kouzou = specs.get("構造", "") or specs.get("建物構造", "")


        # 総戸数 (「戸数」表記も考慮)
        item.soukosuStr = specs.get("総戸数", "") or specs.get("戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

        item.kaisuStr = specs.get("階数", "") or specs.get("建物階数", "")

        # 土地・建物面積
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "") or specs.get("延床面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        # 建ぺい率・容積率
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)

        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")
        item.chimoku = specs.get("地目", "")
        item.youtoChiiki = specs.get("用途地域", "")

        # 物件種別（Apartment, Mansion, Building）の判定
        h1_text = item.propertyName or ""
        if "アパート" in h1_text:
            item.propertyType = "Apartment"
        elif "マンション" in h1_text or "レジ" in h1_text:
            item.propertyType = "Mansion"
        elif "ビル" in h1_text or "店舗" in h1_text or "事務所" in h1_text:
            item.propertyType = "Building"
        else:
            item.propertyType = "Apartment" # fallback

        return item


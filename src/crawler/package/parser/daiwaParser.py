# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase
from package.models.daiwa import DaiwaMansion, DaiwaKodate, DaiwaTochi
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
import re
import urllib.parse

class DaiwaParser(ParserBase):
    BASE_URL = 'https://www.dh-realestate.co.jp'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('daiwa', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        if linkUrl.startswith('/'):
            return self.BASE_URL + linkUrl
        return self.BASE_URL + '/' + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        # ページネーションリンク
        for a in response.select(".pagination a, .pager a, .paging a"):
            text = a.get_text()
            if "次" in text or "next" in text.lower() or ">" in text:
                href = a.get("href")
                if href:
                    return self.getRootDestUrl(href)
        return ""

    async def parseRootPage(self, response: BeautifulSoup):
        detail_links = set()
        # 物件詳細リンクは /buy/mansion/100272 や /buy/house/100146 など
        pattern = re.compile(rf'/buy/{self.property_type or "mansion"}/\d+')
        for a in response.find_all("a", href=pattern):
            href = a.get("href")
            if href:
                full_url = self.getRootDestUrl(href)
                parsed = urllib.parse.urlparse(full_url)
                path = parsed.path
                if not path.endswith('/'):
                    # 末尾スラッシュなしが基本
                    pass
                normalized = f"{self.BASE_URL}{path}"
                if normalized not in detail_links:
                    detail_links.add(normalized)
                    yield normalized

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        for btn in response.find_all(class_=re.compile(r'btn|button|map', re.I)):
            btn.decompose()
            
        item = super()._parsePropertyDetailPage(item, response)

        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)

        # 住所分割
        if item.address:
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        # 交通
        traffic_lines = self._parseTrafficLines(response)
        self._populateTraffic(item, traffic_lines)

        # 共通スペック
        specs = self._get_specs(response)
        item.biko = specs.get("備考", "") or specs.get("その他", "")
        item.genkyo = specs.get("現況", "") or specs.get("現状", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引渡時期（予定）", "")
        item.tochikenri = specs.get("土地権利", "")
        item.torihiki = specs.get("取引態様", "")

        return item

    def _parsePropertyName(self, response: BeautifulSoup):
        title_el = response.find("h1") or response.select_one(".boxtitle h2")
        if title_el:
            return title_el.get_text().strip()
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
            parts = [p.strip() for p in re.split(r'[\r\n\t、\s]+', access_str) if p.strip()]
            current_line = []
            for part in parts:
                current_line.append(part)
                if "徒歩" in part and "分" in part:
                    traffic_lines.append(" ".join(current_line))
                    current_line = []
            if current_line:
                traffic_lines.append(" ".join(current_line))
        return traffic_lines

    def _parseImages(self, response: BeautifulSoup):
        images = []
        for img in response.select(".splide__list .splide__slide img, #property-overview img"):
            src = img.get("src")
            if src:
                full_url = self.getRootDestUrl(src)
                if full_url not in images:
                    images.append(full_url)
        return images

class DaiwaMansionParser(DaiwaParser):
    property_type = 'mansion'

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = DaiwaMansion

    def createEntity(self):
        return DaiwaMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "")
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)

        item.kaisuStr = specs.get("所在階", "") or specs.get("階数", "")
        item.soukosuStr = specs.get("総戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

        item.chikunengetsuStr = specs.get("築年月／完成予定年月", "") or specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.kanrihiStr = specs.get("管理費", "")
        if item.kanrihiStr:
            item.kanrihi = converter.parse_price(item.kanrihiStr)
        item.syuzenTsumitateStr = specs.get("修繕積立金", "")
        if item.syuzenTsumitateStr:
            item.syuzenTsumitate = converter.parse_price(item.syuzenTsumitateStr)

        item.kouzou = specs.get("構造", "") or specs.get("建物構造", "")
        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        item.balconyMensekiStr = specs.get("バルコニー面積", "")
        item.saikou = specs.get("主要採光面", "")

        return item

class DaiwaKodateParser(DaiwaParser):
    property_type = 'house'

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = DaiwaKodate

    def createEntity(self):
        return DaiwaKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        item.kouzou = specs.get("建物構造", "")
        item.kaisuStr = specs.get("階数", "")
        if item.kaisuStr:
            item.kaisu = converter.parse_numeric(item.kaisuStr)

        item.madori = specs.get("間取り", "")
        item.chikunengetsuStr = specs.get("築年月／完成予定年月", "") or specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = specs.get("接道状況", "")

        return item

class DaiwaTochiParser(DaiwaParser):
    property_type = 'land'

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = DaiwaTochi

    def createEntity(self):
        return DaiwaTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = specs.get("接道状況", "")
        item.chimoku = specs.get("地目", "")
        item.kenchikuJoken = specs.get("建築条件", "")

        return item

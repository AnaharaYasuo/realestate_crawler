# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase
from package.models.totate import TotateMansion, TotateKodate, TotateTochi
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
import re
import urllib.parse

class TotateParser(ParserBase):
    BASE_URL = 'https://sumikae.ttfuhan.co.jp'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('totate', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        if linkUrl.startswith('/'):
            return self.BASE_URL + linkUrl
        return self.BASE_URL + '/' + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        # 東京建物の改ページリンク。pagingクラスなどの a タグから next または数字を探す。
        for a in response.select(".paging a, .pager a"):
            text = a.get_text()
            if "次" in text or "next" in text.lower() or ">" in text:
                href = a.get("href")
                if href:
                    return self.getRootDestUrl(href)
        return ""

    async def parseRootPage(self, response: BeautifulSoup):
        detail_links = set()
        # 物件詳細リンクは /mansion/NFD1C4021/ のような形式
        re.compile(rf'/{self.property_type or "mansion"}/[A-Za-z0-9]+')
        for a in response.select(".items .item h4.name a, a[href^='/" + (self.property_type or "mansion") + "/N']"):
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
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "")
        item.tochikenri = specs.get("土地権利", "")
        item.torihiki = specs.get("取引態様", "")

        return item

    def _parsePropertyName(self, response: BeautifulSoup):
        # 物件名の要素を探す (.page-title .name が基本、フォールバックでパンくず等)
        title_el = response.select_one(".page-title .name") or response.select_one("#pankuzu span.selected") or response.select_one(".boxtitle h2")
        if title_el:
            return title_el.get_text().strip()
        # ヘッダーロゴ以外の h1 を探す
        for h1 in response.find_all("h1"):
            if not h1.find("img") and not h1.select_one("a img"):
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
        for img in response.select("ul.bxslider-details-head > li:not(.bx-clone) img, td.madorizu-wrap img"):
            src = img.get("src")
            if src:
                full_url = self.getRootDestUrl(src)
                if full_url not in images:
                    images.append(full_url)
        return images

class TotateMansionParser(TotateParser):
    property_type = 'mansion'

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = TotateMansion

    def createEntity(self):
        return TotateMansion()

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

        item.chikunengetsuStr = specs.get("築年月", "")
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

class TotateKodateParser(TotateParser):
    property_type = 'kodate'

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = TotateKodate

    def createEntity(self):
        return TotateKodate()

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
        item.chikunengetsuStr = specs.get("築年月", "")
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

class TotateTochiParser(TotateParser):
    property_type = 'tochi'

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = TotateTochi

    def createEntity(self):
        return TotateTochi()

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

# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase
from package.models.sumai1 import Sumai1Mansion, Sumai1Kodate, Sumai1Tochi, Sumai1Investment
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
import re
import datetime

class Sumai1Parser(ParserBase):
    BASE_URL = 'https://www.sumai1.com'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('sumai1', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        return self.BASE_URL + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        # 「次へ」「次のページ」などのリンクを探索
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
        for a in response.find_all("a", href=re.compile(r'/buyers/.*?/bukken/buk_')):
            href = a.get("href")
            if href:
                full_url = self.getRootDestUrl(href)
                import urllib.parse
                parsed = urllib.parse.urlparse(full_url)
                # パス部分のみで正規化
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

    def _parse_kenpei_youseki(self, item, specs):
        kenpei_str = specs.get("建ぺい率", "") or specs.get("建ぺい率／容積率", "")
        youseki_str = specs.get("容積率", "") or specs.get("建ぺい率／容積率", "")
        
        if "／" in kenpei_str:
            parts = kenpei_str.split("／")
            if len(parts) >= 2:
                item.kenpeiStr = parts[0].strip()
                item.yousekiStr = parts[1].strip()
        elif "/" in kenpei_str:
            parts = kenpei_str.split("/")
            if len(parts) >= 2:
                item.kenpeiStr = parts[0].strip()
                item.yousekiStr = parts[1].strip()
        else:
            item.kenpeiStr = kenpei_str
            item.yousekiStr = youseki_str
            
        item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.youseki = converter.parse_ratio(item.yousekiStr)

    def _get_specs(self, response: BeautifulSoup) -> dict:
        specs = {}
        # Parse all definition lists and tables
        for table in response.select("table"):
            for tr in table.select("tr"):
                ths = tr.find_all("th")
                tds = tr.find_all("td")
                for i in range(min(len(ths), len(tds))):
                    key = ths[i].get_text().strip().replace("\n", "").replace(" ", "").replace("\u3000", "")
                    val = tds[i].get_text().strip()
                    specs[key] = val
        for dl in response.select("dl"):
            for dt, dd in zip(dl.select("dt"), dl.select("dd")):
                key = dt.get_text().strip().replace("\n", "").replace(" ", "").replace("\u3000", "").replace("：", "")
                val = dd.get_text().strip()
                specs[key] = val

        # キーの表記揺れ標準化
        fallback_mappings = {
            "建ぺい率": ["建ペイ率"],
            "建ぺい率／容積率": ["建ぺい率/容積率", "建ペイ率/容積率", "建ペイ率／容積率", "建ぺい・容積率"],
            "引渡時期": ["引渡", "引渡可能時期", "引渡時期可能時期", "引渡し可能年月"],
            "都市計画": ["都市計画区域"],
            "建築条件": ["建築条件付", "建築条件付き"]
        }
        for std_key, alt_keys in fallback_mappings.items():
            for alt in alt_keys:
                if alt in specs and std_key not in specs:
                    specs[std_key] = specs[alt]
                if std_key in specs and alt not in specs:
                    specs[alt] = specs[std_key]
        return specs

    def _parsePropertyName(self, response: BeautifulSoup):
        h1 = response.find("h1")
        if h1:
            return h1.get_text().strip()
        title_elem = response.select_one(".property-title, .title")
        if title_elem:
            return title_elem.get_text().strip()
        return ""

    def _parsePriceStr(self, response: BeautifulSoup):
        price_elem = response.select_one(".price-value, .property-price, .price")
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
        addr = specs.get("所在地", "")
        if addr and addr.startswith("自治体情報"):
            addr = addr.replace("自治体情報", "").strip()
        return addr

    def _split_address(self, address):
        return super()._split_address(address)

    def _parseTrafficLines(self, response: BeautifulSoup):
        specs = self._get_specs(response)
        traffic_text = specs.get("交通", "")
        if not traffic_text:
            return []
        lines = []
        for l in re.split(r'[\r\n、]+', traffic_text):
            l = l.strip()
            if l:
                lines.append(l)
        return lines

class Sumai1MansionParser(Sumai1Parser):
    property_type = 'mansion'

    def createEntity(self):
        return Sumai1Mansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "")
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)
            
        item.kaisuStr = specs.get("所在階", "") or specs.get("階数", "") or specs.get("建物階数", "") or specs.get("階建", "")
        if item.kaisuStr:
            item.floorType_kai = converter.parse_numeric(item.kaisuStr)

        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("完成時期", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.balconyMensekiStr = specs.get("バルコニー面積", "")
        if item.balconyMensekiStr:
            item.balconyMenseki = converter.parse_menseki(item.balconyMensekiStr)

        item.saikou = specs.get("主要採光面", "") or specs.get("採光", "") or specs.get("主要採光", "") or specs.get("向き", "")
        item.soukosuStr = specs.get("総戸数", "") or specs.get("戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

        item.kanrihiStr = specs.get("管理費", "") or specs.get("管理費等", "") or specs.get("管理費/月", "")
        if item.kanrihiStr:
            item.kanrihi = converter.parse_yen(item.kanrihiStr)

        item.syuzenTsumitateStr = specs.get("修繕積立金", "") or specs.get("修繕積立金等", "") or specs.get("修繕積立金/月", "")
        if item.syuzenTsumitateStr:
            item.syuzenTsumitate = converter.parse_yen(item.syuzenTsumitateStr)

        item.kanriKeitai = specs.get("管理形態", "") or specs.get("管理形態(方式)", "")
        item.kanriKaisya = specs.get("管理会社", "")
        item.kouzou = specs.get("構造", "") or specs.get("建物構造", "")
        item.bunjoKaisya = specs.get("分譲会社", "") or specs.get("販売会社", "")
        item.sekouKaisya = specs.get("施工会社", "")
        
        return item


class Sumai1KodateParser(Sumai1Parser):
    property_type = 'kodate'

    def createEntity(self):
        return Sumai1Kodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "") or specs.get("敷地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "") or specs.get("延床面積", "") or specs.get("専有面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        item.kaisuStr = specs.get("階数", "") or specs.get("建物階数", "") or specs.get("階建", "")
        item.madori = specs.get("間取り", "")
        item.kouzou = specs.get("構造", "") or specs.get("建物構造", "")
        
        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("完成時期", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")
        
        self._parse_kenpei_youseki(item, specs)

        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")
        
        return item


class Sumai1TochiParser(Sumai1Parser):
    property_type = 'tochi'

    def createEntity(self):
        return Sumai1Tochi()

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

        self._parse_kenpei_youseki(item, specs)

        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")

        return item


class Sumai1InvestmentParser(Sumai1Parser):
    property_type = 'investment'

    def createEntity(self):
        return Sumai1Investment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 隠しinputからの抽出を試みる
        sotei_shunyu_input = response.find("input", id="manshitsuji_sotei_shunyu")
        manshitsuji_rimawari_input = response.find("input", id="manshitsuji_rimawari")
        ju_kosu_input = response.find("input", id="ju_kosu")

        # 表面利回り
        gross_yield_str = ""
        if manshitsuji_rimawari_input and manshitsuji_rimawari_input.get("value"):
            gross_yield_str = manshitsuji_rimawari_input.get("value")
        if not gross_yield_str:
            gross_yield_str = specs.get("利回り", "") or specs.get("表面利回り", "") or specs.get("想定利回り", "")
        if gross_yield_str:
            item.grossYield = converter.parse_ratio(gross_yield_str)

        # 想定年間収入
        annual_rent_str = ""
        if sotei_shunyu_input and sotei_shunyu_input.get("value"):
            annual_rent_str = sotei_shunyu_input.get("value")
        if not annual_rent_str:
            annual_rent_str = specs.get("想定年間収入", "") or specs.get("年間想定収入", "") or specs.get("想定収入", "")
        if annual_rent_str:
            rent_val = converter.parse_rent(annual_rent_str)
            if rent_val:
                item.annualRent = rent_val
                item.monthlyRent = rent_val // 12

        item.currentStatus = specs.get("現況", "")
        
        # 構造
        kozo_input = response.find("input", id="kozo_name")
        if kozo_input and kozo_input.get("value"):
            item.kouzou = kozo_input.get("value")
        else:
            item.kouzou = specs.get("構造", "") or specs.get("建物構造", "")

        # 築年月
        chikunen_input = response.find("input", id="chikunen_getsu")
        if chikunen_input and chikunen_input.get("value"):
            chikunen_val = chikunen_input.get("value")
            if len(chikunen_val) == 6:
                try:
                    item.chikunengetsu = datetime.date(int(chikunen_val[:4]), int(chikunen_val[4:]), 1)
                except:
                    pass
        if not item.chikunengetsu:
            item.chikunengetsuStr = specs.get("築年月", "")
            if item.chikunengetsuStr:
                item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        # 総戸数
        soukosu_val = ""
        if ju_kosu_input and ju_kosu_input.get("value"):
            soukosu_val = ju_kosu_input.get("value")
        if not soukosu_val:
            soukosu_val = specs.get("総戸数", "")
            if not soukosu_val:
                # 構造のtdから「総戸数22戸」などを抽出する
                kozo_td = specs.get("構造", "") or specs.get("建物構造", "")
                if kozo_td:
                    m = re.search(r'総戸数(\d+)', kozo_td)
                    if m:
                        soukosu_val = m.group(1)
        if soukosu_val:
            item.soukosu = converter.parse_numeric(str(soukosu_val))

        item.kaisuStr = specs.get("階数", "") or specs.get("建物階数", "")

        # 土地・建物面積
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "") or specs.get("延床面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        self._parse_kenpei_youseki(item, specs)

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


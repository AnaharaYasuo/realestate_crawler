from decimal import Decimal
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import InvestmentParserBase, KodateParserBase, MansionParserBase, ParserBase, TochiParserBase
from package.models.sumai1 import Sumai1Mansion, Sumai1Kodate, Sumai1Tochi, Sumai1Investment
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
from package.utils.property_type_detector import PropertyTypeDetector
import re
import datetime

LABEL_KENPEI_YOUSEKI = "建ぺい率／容積率"


def _first_spec(specs: dict, *keys: str) -> str:
    for k in keys:
        v = specs.get(k)
        if v:
            return v
    return ""


def _parse_sumai1_table_specs(response: BeautifulSoup) -> dict:
    specs = {}
    for table in response.select("table"):
        for tr in table.select("tr"):
            ths = tr.find_all("th")
            tds = tr.find_all("td")
            for i in range(min(len(ths), len(tds))):
                key = ths[i].get_text().strip().replace("\n", "").replace(" ", "").replace("\u3000", "")
                val = tds[i].get_text().strip()
                specs[key] = val
    return specs


def _parse_sumai1_dl_specs(response: BeautifulSoup) -> dict:
    specs = {}
    for dl in response.select("dl"):
        for dt, dd in zip(dl.select("dt"), dl.select("dd")):
            key = dt.get_text().strip().replace("\n", "").replace(" ", "").replace("\u3000", "").replace("：", "")
            val = dd.get_text().strip()
            specs[key] = val
    return specs


def _apply_sumai1_fallbacks(specs: dict) -> None:
    fallback_mappings = {
        "建ぺい率": ["建ペイ率"],
        LABEL_KENPEI_YOUSEKI: ["建ぺい率/容積率", "建ペイ率/容積率", "建ペイ率／容積率", "建ぺい・容積率"],
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


class Sumai1Parser(ParserBase):

    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    BASE_URL = 'https://www.sumai1.com'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('sumai1', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, link_url):
        if link_url.startswith('http'):
            return link_url
        return self.BASE_URL + link_url

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
        item.genkyo = self._parseCurrentStatus(response, specs)
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引渡可能時期", "")
        item.rights = self._parseRights(response, specs)
        item.torihiki = specs.get("取引態様", "")

        return item

    def _parse_kenpei_youseki(self, item, specs):
        kenpei_str = specs.get("建ぺい率", "") or specs.get(LABEL_KENPEI_YOUSEKI, "")
        youseki_str = specs.get("容積率", "") or specs.get(LABEL_KENPEI_YOUSEKI, "")
        
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
        specs = _parse_sumai1_table_specs(response)
        specs.update(_parse_sumai1_dl_specs(response))
        _apply_sumai1_fallbacks(specs)
        return specs

    def _parsePropertyName(self, response: BeautifulSoup, _specs=None):
        h1 = response.find("h1")
        if h1:
            return h1.get_text().strip()
        title_elem = response.select_one(".property-title, .title")
        if title_elem:
            return title_elem.get_text().strip()
        return ""

    def _parsePriceStr(self, response: BeautifulSoup, specs=None):
        _ = specs
        price_elem = response.select_one(".price-value, .property-price, .price")
        if price_elem:
            return price_elem.get_text().strip()
        specs = self._get_specs(response)
        return specs.get("価格", "")

    def _parsePrice(self, response: BeautifulSoup, specs=None):
        price_str = self._parsePriceStr(response, specs)
        if price_str:
            return converter.parse_price(price_str)
        return 0

    def _parseAddress(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
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

class Sumai1MansionParser(Sumai1Parser, MansionParserBase):
    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseYoutoChiiki(self, response, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseSenyuMenseki(self, response, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("専有面積", "") or specs.get("壁芯面積", "")
        if val:
            m = re.search(r'([\d\.]+)', val)
            return Decimal(m.group(1)) if m else None
        return super()._parseSenyuMenseki(response, specs)

    def _parseMadori(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "") or super()._parseMadori(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("構造", "") or super()._parseKouzou(response, specs)

    def _parseFloor(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("階数", "") or specs.get("所在階", "") or super()._parseFloor(response, specs)

    def _parseSouKosu(self, response, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("総戸数", "")
        if val:
            m = re.search(r'(\d+)', val)
            return int(m.group(1)) if m else None
        return super()._parseSouKosu(response, specs)

    def _parseManagementFee(self, response, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("管理費", "") or specs.get("管理費等", "")
        return converter.parse_yen(val) if val and 'converter' in globals() else super()._parseManagementFee(response, specs)

    def _parseReserveFund(self, response, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("修繕積立金", "")
        return converter.parse_yen(val) if val and 'converter' in globals() else super()._parseReserveFund(response, specs)

    def _parseKenpei(self, response, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseYouseki(self, response, specs=None):
        return super()._parseYouseki(response, specs)

    property_type = 'mansion'

    def createEntity(self):
        return Sumai1Mansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = self._parseMadori(response, specs)
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)
            
        item.kaisuStr = _first_spec(specs, "所在階", "階数", "建物階数", "階建")
        if item.kaisuStr:
            item.floorType_kai = converter.parse_numeric(item.kaisuStr)

        item.chikunengetsuStr = _first_spec(specs, "築年月", "完成時期")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.balconyMensekiStr = specs.get("バルコニー面積", "")
        if item.balconyMensekiStr:
            item.balconyMenseki = converter.parse_menseki(item.balconyMensekiStr)

        item.saikou = _first_spec(specs, "主要採光面", "採光", "主要採光", "向き")
        item.soukosuStr = _first_spec(specs, "総戸数", "戸数")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

        item.kanrihiStr = _first_spec(specs, "管理費", "管理費等", "管理費/月")
        if item.kanrihiStr:
            item.kanrihi = converter.parse_yen(item.kanrihiStr)

        item.syuzenTsumitateStr = _first_spec(specs, "修繕積立金", "修繕積立金等", "修繕積立金/月")
        if item.syuzenTsumitateStr:
            item.syuzenTsumitate = converter.parse_yen(item.syuzenTsumitateStr)

        item.kanriKeitai = _first_spec(specs, "管理形態", "管理形態(方式)")
        item.kanriKaisya = specs.get("管理会社", "")
        item.kouzou = self._parseKouzou(response, specs)
        item.bunjoKaisya = _first_spec(specs, "分譲会社", "販売会社")
        item.sekouKaisya = specs.get("施工会社", "")
        
        return item


class Sumai1KodateParser(Sumai1Parser, KodateParserBase):
    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseSetsudou(self, response, specs=None):
        return super()._parseSetsudou(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    def _parseMadori(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "") or super()._parseMadori(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("構造", "") or super()._parseKouzou(response, specs)

    def _parseKenpei(self, response, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseYouseki(self, response, specs=None):
        return super()._parseYouseki(response, specs)

    def _parseRights(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "") or super()._parseYoutoChiiki(response, specs)

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
        item.madori = self._parseMadori(response, specs)
        item.kouzou = self._parseKouzou(response, specs)
        
        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("完成時期", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kuiki = specs.get("都市計画", "")
        
        self._parse_kenpei_youseki(item, specs)

        item.setsudou = self._parseSetsudou(response, specs)
        
        return item


class Sumai1TochiParser(Sumai1Parser, TochiParserBase):
    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseMaguchi(self, response, specs=None):
        return super()._parseMaguchi(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseKenpei(self, response, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseYouseki(self, response, specs=None):
        return super()._parseYouseki(response, specs)

    def _parseChimoku(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("地目", "") or super()._parseChimoku(response, specs)

    def _parseSetsudou(self, response, specs=None) -> str:
        return super()._parseSetsudou(response, specs)

    def _parseRights(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "") or super()._parseYoutoChiiki(response, specs)

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
        item.chimoku = self._parseChimoku(response, specs)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kuiki = specs.get("都市計画", "")
        item.kokudoHou = specs.get("国土法届出", "") or specs.get("国土法", "")

        self._parse_kenpei_youseki(item, specs)

        item.setsudou = self._parseSetsudou(response, specs)

        return item


class Sumai1InvestmentParser(Sumai1Parser, InvestmentParserBase):
    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseMonthlyRent(self, response, specs=None):
        return super()._parseMonthlyRent(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseChimoku(self, response, specs=None):
        return super()._parseChimoku(response, specs)

    def _parseSetsudou(self, response, specs=None):
        return super()._parseSetsudou(response, specs)

    def _parseYoutoChiiki(self, response, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseGrossYield(self, response, specs=None):
        return super()._parseGrossYield(response, specs)

    def _parseAnnualRent(self, response, specs=None):
        return super()._parseAnnualRent(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        return super()._parseKouzou(response, specs)

    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    property_type = 'investment'

    def createEntity(self):
        return Sumai1Investment()

    def _parse_investment_yield_and_rent(self, item, response: BeautifulSoup, specs: dict):
        rimawari_input = response.find("input", id="manshitsuji_rimawari")
        gross_yield_str = rimawari_input.get("value") if rimawari_input and rimawari_input.get("value") else ""
        if not gross_yield_str:
            gross_yield_str = _first_spec(specs, "利回り", "表面利回り", "想定利回り")
        if gross_yield_str:
            item.grossYield = converter.parse_ratio(gross_yield_str)

        shunyu_input = response.find("input", id="manshitsuji_sotei_shunyu")
        annual_rent_str = shunyu_input.get("value") if shunyu_input and shunyu_input.get("value") else ""
        if not annual_rent_str:
            annual_rent_str = _first_spec(specs, "想定年間収入", "年間想定収入", "想定収入")
        if annual_rent_str:
            rent_val = converter.parse_rent(annual_rent_str)
            if rent_val:
                item.annualRent = rent_val
                item.monthlyRent = rent_val // 12

    def _parse_investment_kouzou_and_chikunen(self, item, response: BeautifulSoup, specs: dict):
        kozo_input = response.find("input", id="kozo_name")
        if kozo_input and kozo_input.get("value"):
            item.kouzou = kozo_input.get("value")
        else:
            item.kouzou = self._parseKouzou(response, specs)

        chikunen_input = response.find("input", id="chikunen_getsu")
        if chikunen_input and chikunen_input.get("value"):
            chikunen_val = chikunen_input.get("value")
            if len(chikunen_val) == 6:
                try:
                    item.chikunengetsu = datetime.date(int(chikunen_val[:4]), int(chikunen_val[4:]), 1)
                except Exception:
                    pass
        if not item.chikunengetsu:
            item.chikunengetsuStr = specs.get("築年月", "")
            if item.chikunengetsuStr:
                item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

    def _parse_investment_soukosu(self, item, response: BeautifulSoup, specs: dict):
        ju_kosu_input = response.find("input", id="ju_kosu")
        soukosu_val = ju_kosu_input.get("value") if ju_kosu_input and ju_kosu_input.get("value") else ""
        if not soukosu_val:
            soukosu_val = specs.get("総戸数", "")
            if not soukosu_val:
                kozo_td = _first_spec(specs, "構造", "建物構造")
                if kozo_td:
                    m = re.search(r'総戸数(\d+)', kozo_td)
                    if m:
                        soukosu_val = m.group(1)
        if soukosu_val:
            item.soukosu = converter.parse_numeric(str(soukosu_val))

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        self._parse_investment_yield_and_rent(item, response, specs)

        item.genkyo = self._parseCurrentStatus(response, specs)
        item.currentStatus = item.genkyo

        self._parse_investment_kouzou_and_chikunen(item, response, specs)
        self._parse_investment_soukosu(item, response, specs)

        item.kaisuStr = _first_spec(specs, "階数", "建物階数")

        # 土地・建物面積
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = _first_spec(specs, "建物面積", "延床面積")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        self._parse_kenpei_youseki(item, specs)

        item.setsudou = self._parseSetsudou(response, specs)
        item.chimoku = self._parseChimoku(response, specs)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)

        # 物件種別（Apartment, Mansion, Building）の判定 (共通化)
        item.propertyType = PropertyTypeDetector.detect_investment_type(item.propertyName or "")

        return item
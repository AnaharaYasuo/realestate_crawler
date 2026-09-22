from decimal import Decimal
from typing import Optional
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import InvestmentParserBase, KodateParserBase, MansionParserBase, ParserBase, TochiParserBase
from package.models.odakyu import OdakyuMansion, OdakyuKodate, OdakyuTochi, OdakyuInvestment
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
from package.utils.property_type_detector import PropertyTypeDetector
import re
import urllib.parse

class OdakyuParser(ParserBase):

    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    BASE_URL = 'https://www.odakyu-chukai.com'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('odakyu', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        if linkUrl.startswith('/'):
            return self.BASE_URL + linkUrl
        return self.BASE_URL + '/' + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        # ページネーション内の「次へ」または `paging`, `pagenation-block` 領域内の a タグ
        for a in response.select(".paging a, .pager a, .pagenation-block a, .pagination a"):
            text = a.get_text()
            if "次" in text or "next" in text.lower() or ">" in text:
                href = a.get("href")
                if href:
                    return self.getRootDestUrl(href)
        return ""

    def _normalize_detail_url(self, href: str) -> Optional[str]:
        if self.property_type == 'investment':
            # 投資一覧は /mansion/detail/ID/ 等を返す。/detail/ID/ へ潰すと 404 になる (Issue #317)
            full_url = self.getRootDestUrl(href)
            m = re.search(
                r'/(?P<kind>mansion|house|kodate|land|tochi|invest)/detail/(?P<id>[A-Za-z0-9\-]+)',
                full_url,
            )
            if not m:
                return None
            return f"{self.BASE_URL}/{m.group('kind')}/detail/{m.group('id')}/"
        full_url = self.getRootDestUrl(href)
        path = urllib.parse.urlparse(full_url).path
        if not path.endswith('/'):
            path += '/'
        return f"{self.BASE_URL}{path}"

    async def parseRootPage(self, response: BeautifulSoup):
        detail_links = set()
        # 投資用と居住用でパターン分岐 (/mansion/detail/, /house/detail/, /land/detail/, /detail/)
        if self.property_type == 'investment':
            pattern = re.compile(
                r'/(?:mansion|house|kodate|land|tochi|invest)/detail/[A-Za-z0-9\-]+'
            )
        else:
            pattern = re.compile(r'/(?:mansion|house|kodate|land|tochi)/detail/[A-Za-z0-9\-]+')

        for a in response.find_all("a", href=pattern):
            href = a.get("href")
            if not href:
                continue
            normalized = self._normalize_detail_url(href)
            if normalized and normalized not in detail_links:
                detail_links.add(normalized)
                yield normalized

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # 不要なマップ・ボタンなどを取り除く
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
        item.genkyo = self._parseCurrentStatus(response, specs)
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "")
        item.tochikenri = self._parseRights(response, specs)
        item.torihiki = specs.get("取引態様", "")

        return self.clean_parsed_item(item)

    def _parsePropertyName(self, response: BeautifulSoup):
        title_el = response.find("h1") or response.select_one(".detailTitle h2")
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
        for img in response.select(".photo img, .slideWrap img, .mainPhoto img"):
            src = img.get("src")
            if src:
                full_url = self.getRootDestUrl(src)
                if full_url not in images:
                    images.append(full_url)
        return images

class OdakyuMansionParser(OdakyuParser, MansionParserBase):
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

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = OdakyuMansion

    def createEntity(self):
        return OdakyuMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = self._parseMadori(response, specs)
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

        item.kouzou = self._parseKouzou(response, specs)
        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        item.balconyMensekiStr = specs.get("バルコニー面積", "")
        item.saikou = specs.get("主要採光面", "")

        return item

class OdakyuKodateParser(OdakyuParser, KodateParserBase):
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

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = OdakyuKodate

    def createEntity(self):
        return OdakyuKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        item.kouzou = self._parseKouzou(response, specs)
        item.kaisuStr = specs.get("階数", "")
        if item.kaisuStr:
            item.kaisu = converter.parse_numeric(item.kaisuStr)

        item.madori = self._parseMadori(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = self._parseSetsudou(response, specs)

        return item

class OdakyuTochiParser(OdakyuParser, TochiParserBase):
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

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = OdakyuTochi

    def createEntity(self):
        return OdakyuTochi()

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

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = self._parseSetsudou(response, specs)
        item.chimoku = self._parseChimoku(response, specs)
        item.kenchikuJoken = specs.get("建築条件", "")

        return item


class OdakyuInvestmentParser(OdakyuParser, InvestmentParserBase):
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

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = OdakyuInvestment

    def createEntity(self):
        return OdakyuInvestment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 表面利回り
        gross_yield_str = specs.get("利回り", "") or specs.get("表面利回り", "")
        if gross_yield_str:
            item.grossYield = converter.parse_ratio(gross_yield_str)

        # 想定年間収入
        annual_rent_str = specs.get("想定年間収入", "") or specs.get("年間想定収入", "")
        if annual_rent_str:
            rent_val = converter.parse_price(annual_rent_str)
            if rent_val:
                item.annualRent = rent_val
                item.monthlyRent = rent_val // 12

        item.genkyo = self._parseCurrentStatus(response, specs)
        item.currentStatus = item.genkyo
        item.kouzou = self._parseKouzou(response, specs)

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        # 総戸数
        item.soukosuStr = specs.get("総戸数", "")
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

        item.setsudou = self._parseSetsudou(response, specs)
        item.chimoku = self._parseChimoku(response, specs)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)

        # 物件種別（Apartment, Mansion, Building）の判定 (共通化)
        item.propertyType = PropertyTypeDetector.detect_investment_type(item.propertyName or "")

        return item
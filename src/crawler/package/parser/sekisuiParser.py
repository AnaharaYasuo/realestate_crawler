import re
from decimal import Decimal
from bs4 import BeautifulSoup
from package.parser.baseParser import KodateParserBase, MansionParserBase, ParserBase, TochiParserBase
from package.models.sekisui import SekisuiMansion, SekisuiKodate, SekisuiTochi
from package.utils.selector_loader import SelectorLoader
from package.utils import converter

KEY_COMPLETION_DATE = "完成時期（築年月）"
KEY_STRUCTURE_FLOORS = "構造・階数"


def _parse_sekisui_dl_specs(response: BeautifulSoup, specs: dict) -> None:
    for dl in response.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            key = dt.get_text().strip()
            val = re.sub(r'\s+', ' ', dd.get_text().strip())
            if key:
                specs[key] = val


def _parse_sekisui_li_specs(response: BeautifulSoup, specs: dict) -> None:
    for li in response.find_all("li"):
        title_p = li.find("p", class_="title")
        if not title_p:
            continue
        val_p = title_p.find_next_sibling("p")
        if val_p:
            key = title_p.get_text().strip()
            val = re.sub(r'\s+', ' ', val_p.get_text().strip())
            if key:
                specs[key] = val


def _parse_sekisui_tr_specs(response: BeautifulSoup, specs: dict) -> None:
    for tr in response.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if th and td:
            key = th.get_text().strip()
            val = re.sub(r'\s+', ' ', td.get_text().strip())
            if key:
                specs[key] = val


class SekisuiParser(ParserBase):

    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    BASE_URL = 'https://sumusite.sekisuihouse.co.jp'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('sekisui', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        return super()._parseTransport1(response, specs)

    def getRootDestUrl(self, link_url):
        if link_url.startswith('http'):
            return link_url
        if link_url.startswith('//'):
            return 'https:' + link_url
        return self.BASE_URL + link_url

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
        item.genkyo = self._parseCurrentStatus(response, specs)
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引渡可能時期", "")
        item.tochikenri = self._parseRights(response, specs)
        item.torihiki = specs.get("取引態様", "")

        return item

    def _parsePropertyName(self, response: BeautifulSoup, _specs=None):
        h1 = response.find("h1")
        if h1:
            return h1.get_text().strip()
        title_elem = response.select_one(".detail-header__title, .property-title, .title")
        if title_elem:
            return title_elem.get_text().strip()
        specs = _specs or self._get_specs(response)
        return specs.get("物件名", "") or specs.get("建物名", "") or ""

    def _parsePriceStr(self, response: BeautifulSoup, specs=None):
        _ = specs
        price_elem = response.select_one(".detail-header__price, .price-value, .property-price, .price")
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
        return specs.get("所在地", "")

    def _split_address(self, address):
        return super()._split_address(address)

    def _get_specs(self, response: BeautifulSoup):
        # Sekisui specific specifications parsing
        specs = {}
        _parse_sekisui_dl_specs(response, specs)
        _parse_sekisui_li_specs(response, specs)
        _parse_sekisui_tr_specs(response, specs)
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



class SekisuiMansionParser(SekisuiParser, MansionParserBase):
    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

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
        specs = specs or self._get_specs(response)
        val = (
            specs.get(KEY_COMPLETION_DATE, "")
            or specs.get("築年月", "")
            or specs.get("完成年月", "")
            or specs.get("竣工年月", "")
            or specs.get("築年", "")
            or specs.get("完成時期", "")
        )
        if val:
            return converter.parse_chikunengetsu(val)
        return super()._parseChikunengetsu(response, specs)

    def _parseFloorTypeChijo(self, response: BeautifulSoup, specs=None) -> int | None:
        specs = specs or self._get_specs(response)
        val = specs.get(KEY_STRUCTURE_FLOORS, "") or specs.get("階数", "") or specs.get("建物構造", "")
        if val:
            m_chijo = re.search(r'地上\s*(\d{1,3})階', val)
            if m_chijo:
                return int(m_chijo.group(1))
            m_kai = re.search(r'(\d{1,3})階建', val)
            if m_kai:
                return int(m_kai.group(1))
        return None

    def _parseFloorTypeChika(self, response: BeautifulSoup, specs=None) -> int | None:
        specs = specs or self._get_specs(response)
        val = specs.get(KEY_STRUCTURE_FLOORS, "") or specs.get("階数", "") or specs.get("建物構造", "")
        if val:
            m_chika = re.search(r'地下\s*(\d{1,3})階', val)
            if m_chika:
                return int(m_chika.group(1))
            if re.search(r'(\d{1,3})階建', val) or re.search(r'地上\s*(\d{1,3})階', val):
                return 0
        return None

    def _parseFloorTypeKai(self, response: BeautifulSoup, specs=None) -> int | None:
        specs = specs or self._get_specs(response)
        val = specs.get("所在階", "")
        if val:
            m = re.search(r'(\d{1,3})階', val)
            if m:
                return int(m.group(1))
        return None


    def _parseKouzou(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("構造", "") or specs.get(KEY_STRUCTURE_FLOORS, "") or specs.get("建物構造", "") or super()._parseKouzou(response, specs)

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
        return SekisuiMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = self._parseMadori(response, specs)
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)
            
        item.kaisuStr = specs.get("所在階", "") or specs.get("階数", "")
        if item.kaisuStr:
            item.floorType_kai = converter.parse_numeric(item.kaisuStr)

        item.chikunengetsuStr = (
            specs.get("築年月", "")
            or specs.get("完成年月", "")
            or specs.get("竣工年月", "")
            or specs.get("築年", "")
            or specs.get(KEY_COMPLETION_DATE, "")
            or specs.get("完成時期", "")
        )
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
        item.kouzou = self._parseKouzou(response, specs)

        item.floorType_chijo = self._parseFloorTypeChijo(response, specs)
        item.floorType_chika = self._parseFloorTypeChika(response, specs)
        item.floorType_kai = self._parseFloorTypeKai(response, specs)
        
        return item



class SekisuiKodateParser(SekisuiParser, KodateParserBase):
    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)

    def _parseSetsudou(self, response, specs=None):
        return super()._parseSetsudou(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)


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
        return specs.get("構造", "") or specs.get(KEY_STRUCTURE_FLOORS, "") or specs.get("建物構造", "") or super()._parseKouzou(response, specs)

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
        item.madori = self._parseMadori(response, specs)
        item.kouzou = self._parseKouzou(response, specs)
        
        item.chikunengetsuStr = (
            specs.get("築年月", "")
            or specs.get("完成年月", "")
            or specs.get("竣工年月", "")
            or specs.get("築年", "")
            or specs.get(KEY_COMPLETION_DATE, "")
            or specs.get("完成時期", "")
        )
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kuiki = specs.get("都市計画", "")
        
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.setsudou = self._parseSetsudou(response, specs)
        
        return item


class SekisuiTochiParser(SekisuiParser, TochiParserBase):
    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)

    def _parseMaguchi(self, response, specs=None):
        return super()._parseMaguchi(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)


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
        return SekisuiTochi()

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

        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.setsudou = self._parseSetsudou(response, specs)

        return item
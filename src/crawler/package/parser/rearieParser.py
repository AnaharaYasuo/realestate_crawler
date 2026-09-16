from decimal import Decimal
# -*- coding: utf-8 -*-
import re
import logging
import urllib.parse
from bs4 import BeautifulSoup

from package.models.rearie import RearieMansion, RearieKodate, RearieTochi
from package.parser.baseParser import KodateParserBase, MansionParserBase, ParserBase, TochiParserBase
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

class RearieParser(ParserBase):

    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parsePriceStr(self, response, specs=None):
        return super()._parsePriceStr(response, specs)

    BASE_URL = 'https://homes.panasonic.com'
    property_type = ""

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('rearie', self.property_type)

    def getCharset(self):
        return "utf-8"

    def _parsePrice(self, response: BeautifulSoup):
        return super()._parsePrice(response)

    def _parseAddress(self, response: BeautifulSoup):
        return super()._parseAddress(response)


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
        return await super().getResponseBs(session, url, charset)


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
        specs = super()._get_specs(response)
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
        item.genkyo = self._parseCurrentStatus(response, specs)
        item.tochikenri = self._parseRights(response, specs)
        item.torihiki = specs.get("取引態様", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "")

        return item

class RearieMansionParser(RearieParser, MansionParserBase):
    def _parsePriceStr(self, response, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

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
        return RearieMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = self._parseMadori(response, specs)
        
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

        item.kouzou = self._parseKouzou(response, specs)
        item.kanriKeitai = specs.get("管理形態", "") or specs.get("管理形態/管理員の勤務形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        
        item.saikou = specs.get("主要採光", "") or specs.get("向き", "")
        item.saikouMuki = item.saikou
        item.saikouMukiStr = item.saikou
        item.saikouKadobeya = specs.get("角部屋", "")
        item.kadobeya = item.saikouKadobeya

        return item

class RearieKodateParser(RearieParser, KodateParserBase):
    def _parsePriceStr(self, response, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

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
        return RearieKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = self._parseMadori(response, specs)

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

        item.kouzou = self._parseKouzou(response, specs)
        item.kaisuStr = specs.get("階数", "") or specs.get("階建", "")
        if item.kaisuStr:
            item.kaisu = converter.parse_numeric(item.kaisuStr)

        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)

        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)

        return item

class RearieTochiParser(RearieParser, TochiParserBase):
    def _parsePriceStr(self, response, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

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
        return RearieTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.kenchikuJoken = specs.get("建築条件", "")
        item.chimoku = self._parseChimoku(response, specs)
        
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)

        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)

        return item
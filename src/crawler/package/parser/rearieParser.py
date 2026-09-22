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

    BASE_API_URL = "https://phfudousan.repros.jp"
    REPROS_KEY = "32df8d8a-58fb-5d59-ab6a-6e6c09239add"
    REPROS_HEADERS = {
        'Origin': 'https://homes.panasonic.com',
        'Referer': 'https://homes.panasonic.com/',
        'x-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }

    def _get_api_paths(self):
        type_map = {
            'mansion': ('kubunList', 'kubunDetail', 'mansion'),
            'tochi': ('tochiList', 'tochiDetail', 'land'),
            'kodate': ('kodateList', 'kodateDetail', 'house'),
        }
        return type_map.get(self.property_type, ('kubunList', 'kubunDetail', 'mansion'))

    async def getResponseBs(self, session, url, charset=None) -> BeautifulSoup:
        if "phfudousan.repros.jp" in url:
            async with session.get(url, headers=self.REPROS_HEADERS) as resp:
                data = await resp.json()
                soup = BeautifulSoup("<html><body></body></html>", "html.parser")
                soup._json_data = data.get("data", data)
                return soup
        return await super().getResponseBs(session, url, charset)

    async def parseNextPageJson(self, json_data: dict) -> str:
        page = json_data.get("page", 1)
        max_page = json_data.get("maxPage", 1)
        if page < max_page:
            list_endpoint, _, _ = self._get_api_paths()
            return f"{self.BASE_API_URL}/api/v2/{list_endpoint}/?key={self.REPROS_KEY}&page={page + 1}"
        return ""

    async def parseNextPage(self, response: BeautifulSoup):
        if hasattr(response, "_json_data"):
            return await self.parseNextPageJson(response._json_data)
        # ページネーションの「次へ」リンクを探す
        next_a = response.select_one("a.pager__item-next")
        if next_a:
            href = next_a.get("href")
            if href and "page=" in href:
                style = next_a.get("style", "")
                if "display: none" not in style:
                    return self.getRootDestUrl(href)
        return ""

    async def parseRootPageJson(self, json_data: dict):
        items = json_data.get("list", [])
        _, detail_endpoint, _ = self._get_api_paths()
        for item in items:
            p_id = item.get("id")
            if p_id:
                yield f"{self.BASE_API_URL}/api/v1/{detail_endpoint}/?id={p_id}&key={self.REPROS_KEY}"

    async def parseRootPage(self, response: BeautifulSoup):
        if hasattr(response, "_json_data"):
            async for u in self.parseRootPageJson(response._json_data):
                yield u
            return

        detail_links = set()
        type_map = {
            'mansion': 'mansion',
            'tochi': 'land',
            'kodate': 'house'
        }
        target_path = type_map.get(self.property_type, 'mansion')
        base_search_url = f"https://homes.panasonic.com/rearie/buy/property/{target_path}/list.html"
        
        for a in response.find_all("a"):
            href = a.get("href")
            if href:
                if "detail.html" in href and "id=" in href and target_path in href:
                    full_url = urllib.parse.urljoin(base_search_url, href)
                    parsed = urllib.parse.urlparse(full_url)
                    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{parsed.query}"
                    if normalized not in detail_links:
                        detail_links.add(normalized)
                        logging.info(f"[Rearie] Match detail link: {normalized}")
                        yield normalized

    def _parsePropertyDetailJson(self, item, data: dict):
        item.propertyName = data.get("propName") or ""
        price_num = data.get("price")
        if price_num:
            try:
                p_int = int(price_num)
                item.price = p_int * 10000
                item.priceStr = f"{p_int:,}万円"
            except Exception:
                item.priceStr = str(price_num)
                item.price = converter.parse_price(item.priceStr)

        item.address = data.get("address") or ""
        if item.address:
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        tate_menseki = data.get("tateMenseki")
        if self.property_type == "mansion":
            if tate_menseki:
                item.senyuMenseki = converter.parse_menseki(tate_menseki)
                item.senyuMensekiStr = str(tate_menseki)
            baru = data.get("baruMenseki")
            if baru:
                item.balconyMenseki = converter.parse_menseki(baru)
                item.balconyMensekiStr = str(baru)
            kai = data.get("kai")
            if kai and str(kai).isdigit():
                item.floorType_kai = int(kai)
            kaidate = data.get("kaidate")
            if kaidate and str(kaidate).isdigit():
                item.floorType_chijo = int(kaidate)
            kosuu = data.get("kosuu")
            if kosuu and str(kosuu).isdigit():
                item.soukosu = int(kosuu)
                item.soukosuStr = str(kosuu)
            kanrihi = data.get("kanrihi")
            if kanrihi:
                item.kanrihi = converter.parse_price(kanrihi)
                item.kanrihiStr = str(kanrihi)
            tumikin = data.get("tumikin")
            if tumikin:
                item.syuzenTsumitate = converter.parse_price(tumikin)
                item.syuzenTsumitateStr = str(tumikin)
        elif self.property_type == "kodate":
            if tate_menseki:
                item.tatemonoMenseki = converter.parse_menseki(tate_menseki)
                item.tatemonoMensekiStr = str(tate_menseki)
            tochi_m = data.get("tochiMenseki")
            if tochi_m:
                item.tochiMenseki = converter.parse_menseki(tochi_m)
                item.tochiMensekiStr = str(tochi_m)
            kenpei = data.get("kenpei")
            if kenpei:
                item.kenpei = converter.parse_ratio(kenpei)
                item.kenpeiStr = str(kenpei)
            youseki = data.get("youseki")
            if youseki:
                item.youseki = converter.parse_ratio(youseki)
                item.yousekiStr = str(youseki)
            item.youtoChiiki = data.get("chiiki") or ""
            item.setsudou = data.get("setudou") or ""
        elif self.property_type == "tochi":
            tochi_m = data.get("tochiMenseki")
            if tochi_m:
                item.tochiMenseki = converter.parse_menseki(tochi_m)
                item.tochiMensekiStr = str(tochi_m)
            item.kenchikuJoken = data.get("jyouken") or ""
            item.chimoku = data.get("chimoku") or ""
            kenpei = data.get("kenpei")
            if kenpei:
                item.kenpei = converter.parse_ratio(kenpei)
                item.kenpeiStr = str(kenpei)
            youseki = data.get("youseki")
            if youseki:
                item.youseki = converter.parse_ratio(youseki)
                item.yousekiStr = str(youseki)
            item.youtoChiiki = data.get("chiiki") or ""
            item.setsudou = data.get("setudou") or ""

        item.tochikenri = data.get("tochiKenri") or ""
        item.genkyo = data.get("genkyou") or ""
        item.torihiki = data.get("torihiki") or ""
        item.hikiwatashi = data.get("hikiwata") or ""
        item.kouzou = data.get("kouzou") or ""
        chiku = data.get("chiku")
        if chiku:
            item.chikunengetsu = converter.parse_chikunengetsu(chiku)
            item.chikunengetsuStr = str(chiku)
        item.madori = data.get("madori") or ""
        moyori = data.get("moyori")
        if moyori:
            lines = moyori if isinstance(moyori, list) else list(moyori.values())
            self._populateTraffic(item, [str(t) for t in lines])
        item.biko = data.get("point") or ""

        _, _, type_path = self._get_api_paths()
        p_id = data.get("id")
        if p_id:
            item.pageUrl = f"https://homes.panasonic.com/rearie/buy/property/{type_path}/detail.html?id={p_id}"
        return item

    async def parsePropertyDetailPage(self, session, url):
        if "phfudousan.repros.jp" in url:
            item = self.createEntity()
            item.pageUrl = url
            async with session.get(url, headers=self.REPROS_HEADERS) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to fetch Rearie API {url}: {resp.status}")
                res_json = await resp.json()
                data = res_json.get("data", res_json)
                item = self._parsePropertyDetailJson(item, data)
                item = self.clean_parsed_item(item)
                self.validate_required_fields(item)
                return item
        item = await super().parsePropertyDetailPage(session, url)
        if item is not None and (not item.pageUrl or "detail.html" in url):
            item.pageUrl = url
        return item

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
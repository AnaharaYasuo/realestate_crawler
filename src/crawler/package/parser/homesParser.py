from decimal import Decimal
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import (
    InvestmentParserBase,
    KodateParserBase,
    MansionParserBase,
    ParserBase,
    SkipPropertyException,
    TochiParserBase,
)
from package.models.homes import HomesMansion, HomesKodate, HomesInvestmentApartment, HomesTochi
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
import logging
import re

logger = logging.getLogger(__name__)

_HOMES_DIRECTION_RE = r'(北東|北西|南東|南西|北|南|東|西)'
_HOMES_MAGUCHI_RE = (
    r'(?:間口|接面|接す|接道)\s*[：:]?\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?'
)
_HOMES_WIDTH_RE = r'(?:幅員|幅|道路|前面)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?'
_HOMES_DIR_WIDTH_RE = (
    r'(?:北東|北西|南東|南西|北|南|東|西)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)'
)
_HOMES_ROAD_TYPE_RE = r'(公道|私道)'
_HOMES_ROAD_STRUCT_RE = r'(角地|二方|三方|四方|敷延|袋小路|中間地|両面道路)'


class HomesParser(ParserBase):

    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    BASE_URL = 'https://toushi.homes.co.jp'
    property_type = ''  # Default for type checker

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('homes', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        price_str = specs.get("価格", "") or specs.get("販売価格", "")
        if not price_str and response:
            el = response.select_one(".price, .mod-price, span.priceNum")
            if el:
                price_str = el.get_text(strip=True)
        return price_str

    def _parsePrice(self, response: BeautifulSoup, specs=None):
        price_str = self._parsePriceStr(response, specs)
        return converter.parse_price(price_str)

    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        addr = specs.get("所在地", "") or specs.get("住所", "")
        if not addr and response:
            el = response.select_one(".address, .mod-address")
            if el:
                addr = el.get_text(strip=True)
        return addr

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("交通", "") or specs.get("最寄り駅", "")



    def getRootDestUrl(self, linkUrl):
        if not linkUrl:
            return ""
        if linkUrl.startswith('http'):
            return linkUrl
        if not linkUrl.startswith('/'):
            linkUrl = '/' + linkUrl
        return self.BASE_URL + linkUrl


    async def parseNextPage(self, response: BeautifulSoup):
        """
        一覧ページから「次へ」のページリンクを抽出し、絶対URLとして返す
        """
        response = self._homes_ensure_soup(response)
        next_url = self._homes_find_next_anchor_url(response)
        if next_url:
            return next_url
        return self._homes_increment_canonical_page(response)

    @staticmethod
    def _homes_ensure_soup(response):
        if isinstance(response, BeautifulSoup):
            return response
        import lxml.etree
        html_str = lxml.etree.tostring(response, encoding='utf-8').decode('utf-8')
        return BeautifulSoup(html_str, "html.parser")

    def _homes_find_next_anchor_url(self, response: BeautifulSoup) -> str:
        next_tag = (
            response.select_one("a.next")
            or response.select_one(".page-next a")
            or response.select_one("a[rel='next']")
        )
        if not next_tag:
            for a in response.find_all("a", href=True):
                text = a.get_text().strip()
                if "次" in text or text == ">" or text == "»":
                    next_tag = a
                    break
        if not next_tag:
            return ""
        href = next_tag.get("href")
        return self.getRootDestUrl(href) if href else ""

    def _homes_increment_canonical_page(self, response: BeautifulSoup) -> str:
        # フォールバック: canonical URLをベースに page パラメータをインクリメント
        canonical = response.find("link", rel="canonical")
        if not canonical:
            return ""
        current_url = canonical.get("href", "")
        if not current_url:
            return ""

        import urllib.parse
        parsed = urllib.parse.urlparse(current_url)
        query = urllib.parse.parse_qs(parsed.query)

        page_list = query.get("page", [])
        try:
            current_page = int(page_list[0]) if page_list else 1
        except ValueError:
            current_page = 1

        query["page"] = [str(current_page + 1)]
        new_query = urllib.parse.urlencode(query, doseq=True)
        return urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        ))


    async def parseRootPage(self, response):
        """
        検索結果一覧ページ（BeautifulSoup）から詳細物件ページのURLを抽出する
        """
        import urllib.parse
        detail_links = set()
        for a in response.select("a[href*='/bukkendetail/']"):
            href = a.get("href")
            if href:
                full_url = self.getRootDestUrl(href)
                # クレンジング（URLの正規化）
                parsed = urllib.parse.urlparse(full_url)
                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if normalized not in detail_links:
                    detail_links.add(normalized)
                    yield normalized

    def _find_by_table_header(self, response: BeautifulSoup, headers):
        """thタグのテキストに含まれるキーワードから、対応するtdタグのテキストを抽出する。
        headers: 探索するキーワードのリスト
        """
        if isinstance(headers, str):
            headers = [headers]
        for tr in response.select("table tr"):
            th = tr.find("th")
            td = tr.find("td")
            if th and td:
                th_text = th.get_text(strip=True)
                if any(h in th_text for h in headers):
                    return td
        return None

    @staticmethod
    def _clean_text(tag, first_line_only=False):
        """タグからテキストを取得し、改行・余分な空白を正規化する。
        first_line_only=True の場合、最初の有効な行のみ返す。
        """
        if not tag:
            return ""
        import re
        text = tag.get_text(separator="\n").strip()
        # 「地図を見る」「積算価格を試算する」等のリンクテキストを除去
        text = re.sub(r'地図を見る.*$', '', text, flags=re.MULTILINE).strip()
        text = re.sub(r'積算価格を試算する.*$', '', text, flags=re.MULTILINE).strip()
        if first_line_only:
            # 最初の空でない行を返す
            for line in text.split('\n'):
                line = line.strip()
                if line:
                    return line
            return ""
        # 複数行を半角スペースで連結して返す
        return re.sub(r'\s+', ' ', text).strip()

    def _homes_apply_setsudou_details(self, item, setsudou_info: str) -> None:
        """接道状況テキストから間口・道路幅・方位等を抽出する。"""
        if not setsudou_info:
            item.roadStructure = getattr(item, "roadStructure", None) or "中間地"
            return

        mag_match = re.search(_HOMES_MAGUCHI_RE, setsudou_info)
        if mag_match:
            item.maguchiStr = mag_match.group(0)
            item.maguchi = Decimal(mag_match.group(1))

        width_match = re.search(_HOMES_WIDTH_RE, setsudou_info)
        if width_match:
            item.roadWidthStr = width_match.group(0)
            item.roadWidth = Decimal(width_match.group(1))
        else:
            dir_width_match = re.search(_HOMES_DIR_WIDTH_RE, setsudou_info)
            if dir_width_match:
                item.roadWidthStr = dir_width_match.group(0)
                item.roadWidth = Decimal(dir_width_match.group(1))

        direction_match = re.search(_HOMES_DIRECTION_RE, setsudou_info)
        item.roadDirection = direction_match.group(1) if direction_match else ""

        type_match = re.search(_HOMES_ROAD_TYPE_RE, setsudou_info)
        item.roadType = type_match.group(1) if type_match else ""

        struct_match = re.search(_HOMES_ROAD_STRUCT_RE, setsudou_info)
        item.roadStructure = struct_match.group(1) if struct_match else "中間地"

    def _homes_apply_kenpei_youseki(
        self, item, kenpei_text: str, youseki_text: str
    ) -> None:
        if youseki_text and ("／" in youseki_text or "/" in youseki_text) and not kenpei_text:
            parts = re.split(r'[／/]', youseki_text)
            if len(parts) >= 2:
                kenpei_text = parts[0].strip()
                youseki_text = parts[1].strip()
        item.kenpeiStr = kenpei_text
        item.kenpei = converter.parse_ratio(kenpei_text)
        item.yousekiStr = youseki_text
        item.youseki = converter.parse_ratio(youseki_text)

    def _homes_apply_okuyuki(self, item) -> None:
        if item.tochiMenseki and getattr(item, 'maguchi', None) and item.maguchi > 0:
            item.okuyuki = round(item.tochiMenseki / item.maguchi, 2)
            item.okuyukiStr = f"{item.okuyuki}m"

    def _homes_text_from_selectors(self, response, css_selectors, headers) -> str:
        tag = None
        for sel in css_selectors:
            tag = response.select_one(sel)
            if tag:
                break
        if not tag:
            tag = self._find_by_table_header(response, headers)
        return tag.get_text().strip() if tag else ""

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        
        # タイトル・物件名
        title_tag = response.select_one("td.prg-nameTableItem") or self._find_by_table_header(response, ["物件名", "名称", "建物名"])
        item.propertyName = self._clean_text(title_tag, first_line_only=True)
        
        # 1. 住所（「地図を見る」等を除去し、最初の行のみ取得）
        addr_tag = response.select_one("td.prg-addressTableItem") or self._find_by_table_header(response, ["住所", "所在地"])
        item.address = self._clean_text(addr_tag, first_line_only=True)
        if item.address:
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        
        # 2. 価格（「積算価格を試算する」等を除去）
        price_tag = response.select_one("td.prg-priceTableItem") or self._find_by_table_header(response, ["価格", "販売価格"])
        item.priceStr = self._clean_text(price_tag, first_line_only=False)
        item.price = converter.parse_price(item.priceStr)
        
        # 3. 交通
        traffic_tag = response.select_one("td.prg-accessTableItem") or self._find_by_table_header(response, ["交通", "アクセス"])
        item.traffic = self._clean_text(traffic_tag, first_line_only=False)
        self._populateTraffic(item, item.traffic)
        
        # 4. 構造（「（軽量鉄骨造）」等の括弧補足を含めて1行にまとめる）
        struct_tag = response.select_one("td.prg-structureTableItem")
        item.kouzou = self._clean_text(struct_tag)
        
        # 5. 築年月（「(築42年)」等の括弧補足を除去し、年月部分のみ取得）
        period_tag = response.select_one("td.prg-periodTableItem")
        item.chikunengetsuStr = self._clean_text(period_tag, first_line_only=True)
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)
            
        return item


class HomesMansionParser(HomesParser, MansionParserBase):
    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

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
        return HomesMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        
        madori_tag = response.select_one("td.prg-madoriTableItem") or self._find_by_table_header(response, ["間取り"])
        item.madori = madori_tag.get_text().strip() if madori_tag else ""
        
        area_tag = response.select_one("td.prg-senyuAreaTableItem") or response.select_one("td.prg-houseAreaTableItem") or self._find_by_table_header(response, ["専有面積", "建物面積", "延床面積"])
        item.senyuMensekiStr = area_tag.get_text().strip() if area_tag else ""
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)
            
        kaisu_tag = response.select_one("td.prg-floorTableItem") or self._find_by_table_header(response, ["所在階", "階数", "階建"])
        item.kaisuStr = kaisu_tag.get_text().strip() if kaisu_tag else ""
        
        kosu_tag = response.select_one("td.prg-allNumberTableItem") or self._find_by_table_header(response, ["総戸数", "戸数", "総区画"])
        item.soukosuStr = kosu_tag.get_text().strip() if kosu_tag else ""
        item.soukosu = converter.parse_number(item.soukosuStr)
        
        return item


class HomesKodateParser(HomesParser, KodateParserBase):
    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

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
        return HomesKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        land_tag = response.select_one("td.prg-landAreaTableItem") or self._find_by_table_header(response, ["土地面積", "敷地面積"])
        item.tochiMensekiStr = land_tag.get_text().strip() if land_tag else ""
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        house_tag = response.select_one("td.prg-houseAreaTableItem") or self._find_by_table_header(response, ["建物面積", "延床面積"])
        item.tatemonoMensekiStr = house_tag.get_text().strip() if house_tag else ""
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        setsudou_info = self._homes_text_from_selectors(
            response,
            ("td.prg-setsudouTableItem", "td.prg-roadTableItem"),
            ["接道状況", "接道"],
        )
        item.setsudou = setsudou_info
        self._homes_apply_setsudou_details(item, setsudou_info)

        ratio_tag = response.select_one("td.prg-floorAreaRatioTableItem") or self._find_by_table_header(response, ["建ぺい率／容積率", "建ぺい率/容積率"])
        kenpei_tag = response.select_one("td.prg-buildingCoverageTableItem") or self._find_by_table_header(response, ["建ぺい率"])
        kenpei_text = kenpei_tag.get_text().strip() if kenpei_tag else ""
        youseki_text = ratio_tag.get_text().strip() if ratio_tag else ""
        self._homes_apply_kenpei_youseki(item, kenpei_text, youseki_text)
        self._homes_apply_okuyuki(item)

        return item


class HomesInvestmentApartmentParser(HomesParser, InvestmentParserBase):
    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseMonthlyRent(self, response, specs=None):
        return super()._parseMonthlyRent(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

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

    property_type = 'investmentapartment'

    def createEntity(self):
        return HomesInvestmentApartment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        # 利回り
        yield_tag = response.select_one("span.prg-rimawariTableItem") or self._find_by_table_header(response, ["利回り"])
        yield_str = yield_tag.get_text().strip() if yield_tag else ""
        item.grossYield = converter.parse_ratio(yield_str)

        # 想定賃料 (Homesは満室想定年収 prg-annualIncomeTableItem が取れる)
        income_tag = response.select_one("td.prg-annualIncomeTableItem") or self._find_by_table_header(response, ["満室想定年収", "想定年収", "想定賃料"])
        income_str = income_tag.get_text().strip() if income_tag else ""
        item.annualRent = converter.parse_price(income_str)
        item.monthlyRent = int(item.annualRent / 12) if item.annualRent else 0
        if not item.annualRent and not item.grossYield:
            raise SkipPropertyException(
                "Homes invest: missing yield/annualRent on listing (skip and try next)"
            )

        status_tag = response.select_one("td.prg-statusTableItem") or self._find_by_table_header(response, ["現況", "入居状況"])
        item.currentStatus = status_tag.get_text().strip() if status_tag else ""

        land_tag = response.select_one("td.prg-landAreaTableItem") or self._find_by_table_header(response, ["土地面積", "敷地面積"])
        item.tochiMensekiStr = land_tag.get_text().strip() if land_tag else ""
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        house_tag = response.select_one("td.prg-houseAreaTableItem") or self._find_by_table_header(response, ["建物面積", "延床面積", "専有面積"])
        item.tatemonoMensekiStr = house_tag.get_text().strip() if house_tag else ""
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        ratio_tag = response.select_one("td.prg-floorAreaRatioTableItem") or self._find_by_table_header(response, ["建ぺい率／容積率", "建ぺい率/容積率"])
        kenpei_tag = response.select_one("td.prg-buildingCoverageTableItem") or self._find_by_table_header(response, ["建ぺい率"])
        kenpei_text = kenpei_tag.get_text().strip() if kenpei_tag else ""
        youseki_text = ratio_tag.get_text().strip() if ratio_tag else ""
        self._homes_apply_kenpei_youseki(item, kenpei_text, youseki_text)

        setsudou_tag = response.select_one("td.prg-roadTableItem") or self._find_by_table_header(response, ["接道状況", "接道"])
        item.setsudou = setsudou_tag.get_text().strip() if setsudou_tag else ""

        chimoku_tag = response.select_one("td.prg-landCategoryTableItem") or self._find_by_table_header(response, ["地目"])
        item.chimoku = chimoku_tag.get_text().strip() if chimoku_tag else ""

        right_tag = response.select_one("td.prg-rightTableItem") or self._find_by_table_header(response, ["土地権利", "権利"])
        item.tochikenri = right_tag.get_text().strip() if right_tag else ""

        return item


class HomesTochiParser(HomesParser, TochiParserBase):
    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

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
        return HomesTochi()

    def _homes_apply_tochi_kenpei_youseki(self, item, response: BeautifulSoup) -> None:
        ratio_tag = response.select_one("td.prg-floorAreaRatioTableItem") or self._find_by_table_header(
            response, ["建ぺい率／容積率", "建ぺい率/容積率"]
        )
        if ratio_tag:
            ratio_text = ratio_tag.get_text().strip()
            parts = ratio_text.split("／")
            if len(parts) >= 2:
                item.kenpeiStr = parts[0].strip()
                item.yousekiStr = parts[1].strip()
                item.kenpei = converter.parse_ratio(item.kenpeiStr)
                item.youseki = converter.parse_ratio(item.yousekiStr)
            else:
                item.yousekiStr = ratio_text
                item.youseki = converter.parse_ratio(ratio_text)

        kenpei_tag = response.select_one("td.prg-buildingCoverageTableItem") or self._find_by_table_header(
            response, ["建ぺい率"]
        )
        if kenpei_tag:
            item.kenpeiStr = kenpei_tag.get_text().strip()
            item.kenpei = converter.parse_ratio(item.kenpeiStr)

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)

        land_tag = (
            response.select_one("td.prg-landAreaTableItem")
            or response.select_one("td.prg-houseAreaTableItem")
            or self._find_by_table_header(response, ["土地面積", "敷地面積"])
        )
        item.tochiMensekiStr = land_tag.get_text().strip() if land_tag else ""
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        self._homes_apply_tochi_kenpei_youseki(item, response)

        setsudou_info = self._homes_text_from_selectors(
            response,
            ("td.prg-setsudouTableItem", "td.prg-roadTableItem"),
            ["接道状況", "接道"],
        )
        item.setsudou = setsudou_info

        item.chimoku = self._homes_text_from_selectors(
            response,
            ("td.prg-chimokuTableItem", "td.prg-landCategoryTableItem"),
            ["地目"],
        )
        item.tochikenri = self._homes_text_from_selectors(
            response,
            ("td.prg-rightTableItem",),
            ["土地権利", "権利"],
        )
        item.youtoChiiki = self._homes_text_from_selectors(
            response,
            ("td.prg-areaTableItem", "td.prg-useDistrictTableItem"),
            ["用途地域"],
        )
        self._homes_apply_setsudou_details(item, setsudou_info)

        return item
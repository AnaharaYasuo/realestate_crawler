# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase
from package.models.homes import HomesMansion, HomesKodate, HomesInvestmentApartment, HomesTochi
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
import logging
import re

logger = logging.getLogger(__name__)

class HomesParser(ParserBase):
    BASE_URL = 'https://toushi.homes.co.jp'
    property_type = ''  # Default for type checker

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('homes', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        return self.BASE_URL + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        """
        一覧ページから「次へ」のページリンクを抽出し、絶対URLとして返す
        (Vue.jsによる動的レンダリングを回避するため、canonical URLをベースにページ番号をプログラム側でインクリメントする)
        """
        canonical = response.find("link", rel="canonical")
        if not canonical:
            return ""
        current_url = canonical.get("href", "")
        if not current_url:
            return ""
        
        import urllib.parse
        parsed = urllib.parse.urlparse(current_url)
        query = urllib.parse.parse_qs(parsed.query)
        
        # pageパラメータの抽出とインクリメント
        page_list = query.get("page", [])
        if page_list:
            try:
                current_page = int(page_list[0])
            except ValueError:
                current_page = 1
        else:
            current_page = 1
            
        next_page = current_page + 1
        query["page"] = [str(next_page)]
        
        # クエリパラメータを再構成
        new_query = urllib.parse.urlencode(query, doseq=True)
        next_url = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
        return next_url

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

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        
        # タイトル・物件名
        title_tag = response.select_one("td.prg-nameTableItem")
        item.propertyName = self._clean_text(title_tag, first_line_only=True)
        
        # 1. 住所（「地図を見る」等を除去し、最初の行のみ取得）
        addr_tag = response.select_one("td.prg-addressTableItem")
        item.address = self._clean_text(addr_tag, first_line_only=True)
        
        # 2. 価格（「積算価格を試算する」等を除去）
        price_tag = response.select_one("td.prg-priceTableItem")
        item.priceStr = self._clean_text(price_tag, first_line_only=False)
        item.price = converter.parse_price(item.priceStr)
        
        # 3. 交通
        traffic_tag = response.select_one("td.prg-accessTableItem")
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


class HomesMansionParser(HomesParser):
    property_type = 'mansion'

    def createEntity(self):
        return HomesMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        
        madori_tag = response.select_one("td.prg-madoriTableItem")
        item.madori = madori_tag.get_text().strip() if madori_tag else ""
        
        area_tag = response.select_one("td.prg-senyuAreaTableItem") or response.select_one("td.prg-houseAreaTableItem")
        item.senyuMensekiStr = area_tag.get_text().strip() if area_tag else ""
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)
            
        kaisu_tag = response.select_one("td.prg-floorTableItem")
        item.kaisuStr = kaisu_tag.get_text().strip() if kaisu_tag else ""
        
        kosu_tag = response.select_one("td.prg-allNumberTableItem")
        item.soukosuStr = kosu_tag.get_text().strip() if kosu_tag else ""
        item.soukosu = converter.parse_number(item.soukosuStr)
        
        return item


class HomesKodateParser(HomesParser):
    property_type = 'kodate'

    def createEntity(self):
        return HomesKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        
        land_tag = response.select_one("td.prg-landAreaTableItem")
        item.tochiMensekiStr = land_tag.get_text().strip() if land_tag else ""
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
            
        house_tag = response.select_one("td.prg-houseAreaTableItem")
        item.tatemonoMensekiStr = house_tag.get_text().strip() if house_tag else ""
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)
            
        # 接道状況
        setsudou_tag = response.select_one("td.prg-setsudouTableItem") or response.select_one("td.prg-roadTableItem")
        setsudou_info = setsudou_tag.get_text().strip() if setsudou_tag else ""
        item.setsudou = setsudou_info
        
        # 接道状況テキストから詳細情報を正規表現で切り出し
        if setsudou_info:
            # 間口 (maguchi)
            mag_match = re.search(r'(?:間口|接面|接す|接道)\s*[：:]?\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', setsudou_info)
            if mag_match:
                from decimal import Decimal
                item.maguchiStr = mag_match.group(0)
                item.maguchi = Decimal(mag_match.group(1))
                
            # 前面道路幅員 (roadWidth)
            width_match = re.search(r'(?:幅員|幅|道路|前面)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', setsudou_info)
            if width_match:
                from decimal import Decimal
                item.roadWidthStr = width_match.group(0)
                item.roadWidth = Decimal(width_match.group(1))
            else:
                dir_width_match = re.search(r'(?:北東|北西|南東|南西|北|南|東|西)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)', setsudou_info)
                if dir_width_match:
                    from decimal import Decimal
                    item.roadWidthStr = dir_width_match.group(0)
                    item.roadWidth = Decimal(dir_width_match.group(1))
                
            # 接道方位 (roadDirection)
            direction_match = re.search(r'(北東|北西|南東|南西|北|南|東|西)', setsudou_info)
            item.roadDirection = direction_match.group(1) if direction_match else ""
            
            # 道路区分 (roadType: 公道/私道)
            type_match = re.search(r'(公道|私道)', setsudou_info)
            item.roadType = type_match.group(1) if type_match else ""
            
            # 接道構造（角地など）(roadStructure)
            struct_match = re.search(r'(角地|二方|三方|四方|敷延|袋小路|中間地|両面道路)', setsudou_info)
            item.roadStructure = struct_match.group(1) if struct_match else "中間地"
        else:
            item.roadStructure = "中間地"
            
        # 奥行き (okuyuki)
        if item.tochiMenseki and getattr(item, 'maguchi', None) and item.maguchi > 0:
            from decimal import Decimal
            item.okuyuki = round(item.tochiMenseki / item.maguchi, 2)
            item.okuyukiStr = f"{item.okuyuki}m"
            
        return item


class HomesInvestmentApartmentParser(HomesParser):
    property_type = 'investmentapartment'

    def createEntity(self):
        return HomesInvestmentApartment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        
        # 利回り
        yield_tag = response.select_one("span.prg-rimawariTableItem")
        yield_str = yield_tag.get_text().strip() if yield_tag else ""
        item.grossYield = converter.parse_ratio(yield_str)
        
        # 想定賃料 (Homesは満室想定年収 prg-annualIncomeTableItem が取れる)
        income_tag = response.select_one("td.prg-annualIncomeTableItem")
        income_str = income_tag.get_text().strip() if income_tag else ""
        item.annualRent = converter.parse_price(income_str)
        item.monthlyRent = int(item.annualRent / 12) if item.annualRent else 0
        
        status_tag = response.select_one("td.prg-statusTableItem")
        item.currentStatus = status_tag.get_text().strip() if status_tag else ""
        
        # 面積
        land_tag = response.select_one("td.prg-landAreaTableItem")
        item.tochiMensekiStr = land_tag.get_text().strip() if land_tag else ""
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
            
        house_tag = response.select_one("td.prg-houseAreaTableItem")
        item.tatemonoMensekiStr = house_tag.get_text().strip() if house_tag else ""
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)
            
        # 土地詳細
        kenpei_tag = response.select_one("td.prg-buildingCoverageTableItem")
        item.kenpeiStr = kenpei_tag.get_text().strip() if kenpei_tag else ""
        item.kenpei = converter.parse_ratio(item.kenpeiStr)
        
        youseki_tag = response.select_one("td.prg-floorAreaRatioTableItem")
        item.yousekiStr = youseki_tag.get_text().strip() if youseki_tag else ""
        item.youseki = converter.parse_ratio(item.yousekiStr)
        
        setsudou_tag = response.select_one("td.prg-roadTableItem")
        item.setsudou = setsudou_tag.get_text().strip() if setsudou_tag else ""
        
        chimoku_tag = response.select_one("td.prg-landCategoryTableItem")
        item.chimoku = chimoku_tag.get_text().strip() if chimoku_tag else ""
        
        right_tag = response.select_one("td.prg-rightTableItem")
        item.tochikenri = right_tag.get_text().strip() if right_tag else ""
        
        return item


class HomesTochiParser(HomesParser):
    property_type = 'tochi'

    def createEntity(self):
        return HomesTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        
        # 土地面積
        land_tag = response.select_one("td.prg-landAreaTableItem") or response.select_one("td.prg-houseAreaTableItem")
        item.tochiMensekiStr = land_tag.get_text().strip() if land_tag else ""
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
            
        # 建ぺい率・容積率 (合体しているケースがあるため両対応)
        ratio_tag = response.select_one("td.prg-floorAreaRatioTableItem")
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
                
        kenpei_tag = response.select_one("td.prg-buildingCoverageTableItem")
        if kenpei_tag:
            item.kenpeiStr = kenpei_tag.get_text().strip()
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        
        # 接道状況
        setsudou_tag = response.select_one("td.prg-setsudouTableItem") or response.select_one("td.prg-roadTableItem")
        setsudou_info = setsudou_tag.get_text().strip() if setsudou_tag else ""
        item.setsudou = setsudou_info
        
        # 地目
        chimoku_tag = response.select_one("td.prg-chimokuTableItem") or response.select_one("td.prg-landCategoryTableItem")
        item.chimoku = chimoku_tag.get_text().strip() if chimoku_tag else ""
        
        # 土地権利
        right_tag = response.select_one("td.prg-rightTableItem")
        item.tochikenri = right_tag.get_text().strip() if right_tag else ""
        
        # 用途地域
        youto_tag = response.select_one("td.prg-areaTableItem") or response.select_one("td.prg-useDistrictTableItem")
        item.youtoChiiki = youto_tag.get_text().strip() if youto_tag else ""
        
        # 接道状況テキストから詳細情報を正規表現で切り出し
        if setsudou_info:
            # 間口 (maguchi)
            mag_match = re.search(r'(?:間口|接面|接す|接道)\s*[：:]?\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', setsudou_info)
            if mag_match:
                from decimal import Decimal
                item.maguchiStr = mag_match.group(0)
                item.maguchi = Decimal(mag_match.group(1))
                
            # 前面道路幅員 (roadWidth)
            width_match = re.search(r'(?:幅員|幅|道路|前面)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', setsudou_info)
            if width_match:
                from decimal import Decimal
                item.roadWidthStr = width_match.group(0)
                item.roadWidth = Decimal(width_match.group(1))
            else:
                dir_width_match = re.search(r'(?:北東|北西|南東|南西|北|南|東|西)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)', setsudou_info)
                if dir_width_match:
                    from decimal import Decimal
                    item.roadWidthStr = dir_width_match.group(0)
                    item.roadWidth = Decimal(dir_width_match.group(1))
                
            # 接道方位 (roadDirection)
            direction_match = re.search(r'(北東|北西|南東|南西|北|南|東|西)', setsudou_info)
            item.roadDirection = direction_match.group(1) if direction_match else ""
            
            # 道路区分 (roadType: 公道/私道)
            type_match = re.search(r'(公道|私道)', setsudou_info)
            item.roadType = type_match.group(1) if type_match else ""
            
            # 接道状況 (roadStructure)
            structure_match = re.search(r'(角地|二方|三方|四方|敷延|袋小路|中間地|両面道路)', setsudou_info)
            item.roadStructure = structure_match.group(1) if structure_match else "中間地"
            
        return item


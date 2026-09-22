from decimal import Decimal
# -*- coding: utf-8 -*-
import logging
import os
import re
import urllib.parse

from bs4 import BeautifulSoup
from package.parser.baseParser import InvestmentParserBase, KodateParserBase, MansionParserBase, ParserBase, TochiParserBase
from package.models.mizuho import MizuhoMansion, MizuhoKodate, MizuhoTochi, MizuhoInvestment
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
from package.utils.property_type_detector import PropertyTypeDetector
from package.utils.mizuho_bypass import get_mizuho_links

class MizuhoParser(ParserBase):

    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    BASE_URL = 'https://www.mizuho-re.co.jp'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('mizuho', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        if linkUrl.startswith('/'):
            return self.BASE_URL + linkUrl
        return self.BASE_URL + '/' + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        # 「次へ」のリンクを探索
        for a in response.find_all("a"):
            text = a.get_text()
            if "次へ" in text or "次のページ" in text or "next" in text.lower():
                href = a.get("href")
                if href:
                    return self.getRootDestUrl(href)
        return ""

    def _load_temp_links_file(self):
        # 物件種別ごとに一時ファイルを分離し、他種別ジョブのURL混入を防ぐ
        prop_type = self.property_type or "mansion"
        links_file = f"src/crawler/Temp/mizuho_{prop_type}_links.txt"
        if not os.path.exists(links_file):
            return []
        logging.info(f"Mizuho: Loading start URLs from temporary file: {links_file}")
        try:
            with open(links_file, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logging.error(f"Mizuho: Failed to read temporary URLs file: {e}")
            return []

    def _extract_static_detail_links(self, response: BeautifulSoup) -> set:
        detail_links = set()
        for a in response.find_all("a", href=re.compile(r'/(?:buyers|investors)/(?:property|detail)/\d+')):
            href = a.get("href")
            if not href:
                continue
            full_url = self.getRootDestUrl(href)
            parsed = urllib.parse.urlparse(full_url)
            path = parsed.path
            if not path.endswith('/'):
                path += '/'
            normalized = f"{self.BASE_URL}{path}"
            detail_links.add(normalized)
        return detail_links

    async def _execute_playwright_bypass_links(self):
        logging.info(f"Mizuho: No links found in static HTML (possible WAF/JS). Executing Playwright bypass for {self.property_type}...")
        try:
            start_urls = {
                'mansion': "https://www.mizuho-re.co.jp/buyers/search/area/type_Mansion/pref_13/list/",
                'kodate': "https://www.mizuho-re.co.jp/buyers/search/area/type_House/pref_13/list/",
                'tochi': "https://www.mizuho-re.co.jp/buyers/search/area/type_Tochi/pref_13/list/",
                'investment': "https://www.mizuho-re.co.jp/investors/search/area/all_apartment-building-dormitory-office-store-warehouse-factory-land-other/pref_13/list/",
            }
            start_url = getattr(self, '_last_url', None) or start_urls.get(self.property_type, start_urls['mansion'])
            urls = await get_mizuho_links(start_url)
            if urls:
                logging.info(f"Mizuho: Successfully obtained {len(urls)} links via Playwright bypass.")
                return urls
            logging.warning("Mizuho: Playwright bypass returned 0 links.")
        except Exception:
            logging.exception("Mizuho: Playwright bypass failed.")
        return []

    async def parseRootPage(self, response: BeautifulSoup):
        """
        みずほ不動産販売の一覧ページから物件詳細URLを抽出する。
        1. 一時ファイルからURLを読み込み (存在する場合)
        2. 静的HTMLから正規表現でリンクを抽出
        3. リンクが見つからない場合、PlaywrightによるWAF回避処理を実行
        """
        temp_urls = self._load_temp_links_file()
        if temp_urls:
            logging.info(f"Mizuho: Loaded {len(temp_urls)} URLs from temporary file.")
            for url in temp_urls:
                yield url
            return

        detail_links = self._extract_static_detail_links(response)
        if detail_links:
            for url in detail_links:
                yield url
            return

        bypass_urls = await self._execute_playwright_bypass_links()
        for url in bypass_urls:
            yield url

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # tdの中の不要なボタン（周辺地図、街の情報、ローンシミュレーションなど）を除去してパースする
        # 元のDOMを壊さないよう、deep copyされたsoupを使うのが理想だが、ここでは直接decomposeする
        for btn_cls in ["mapBtn", "townBtn", "orangeBtn", "redBtn"]:
            for btn in response.find_all(class_=btn_cls):
                btn.decompose()
        for btn in response.find_all("button"):
            btn.decompose()

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
        item.biko = specs.get("備考", "") or specs.get("その他", "")
        item.genkyo = self._parseCurrentStatus(response, specs)
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引渡時期（予定）", "")
        item.tochikenri = self._parseRights(response, specs)
        item.torihiki = specs.get("取引態様", "")

        return item

    def _parsePropertyName(self, response: BeautifulSoup):
        # 物件タイトル要素
        title_el = response.select_one(".detailTitle .h3Title") or response.select_one(".detailTitle h4")
        if title_el:
            # 内包するimg（NEWマーク等）を取り除く
            new_img = title_el.find("img")
            if new_img:
                new_img.decompose()
            return title_el.get_text().strip()
        # 代替
        h1 = response.find("h1")
        if h1:
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
            # 複数行や改行、または全角スペース等で区切られた交通情報を分割
            # 例: "都営大江戸線 『勝どき』駅 徒歩8分 都営大江戸線 『月島』駅 徒歩18分"
            # 空白区切りで分割
            parts = [p.strip() for p in re.split(r'[\r\n\t、\s]+', access_str) if p.strip()]
            
            # 分割したパーツを「路線」「駅」「徒歩分数」のまとまりごとに復元する
            # "徒歩XX分" が現れるまでを1つの交通情報行とする
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
        # .slickDetailImg ul.slideWrap li img からスライド画像を全取得
        for img in response.select(".slickDetailImg ul.slideWrap li img"):
            src = img.get("src")
            if src:
                full_url = self.getRootDestUrl(src)
                if full_url not in images:
                    images.append(full_url)
        return images

class MizuhoMansionParser(MizuhoParser, MansionParserBase):
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
        self.ModelClass = MizuhoMansion

    def createEntity(self):
        return MizuhoMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 間取り
        item.madori = self._parseMadori(response, specs)

        # 専有面積
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)

        # 所在階・総階数
        item.kaisuStr = specs.get("所在階", "")
        item.soukosuStr = specs.get("総戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        # 管理費・修繕積立金
        item.kanrihiStr = specs.get("管理費", "")
        if item.kanrihiStr:
            item.kanrihi = converter.parse_price(item.kanrihiStr)
        item.syuzenTsumitateStr = specs.get("修繕積立金", "")
        if item.syuzenTsumitateStr:
            item.syuzenTsumitate = converter.parse_price(item.syuzenTsumitateStr)

        # 建物構造・管理形態
        item.kouzou = self._parseKouzou(response, specs)
        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        item.balconyMensekiStr = specs.get("バルコニー面積", "")
        item.saikou = specs.get("主要採光面", "")

        return item

class MizuhoKodateParser(MizuhoParser, KodateParserBase):
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
        self.ModelClass = MizuhoKodate

    def createEntity(self):
        return MizuhoKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 土地面積
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        # 建物面積
        item.tatemonoMensekiStr = specs.get("建物面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        # 構造・階数
        item.kouzou = self._parseKouzou(response, specs)
        item.kaisuStr = specs.get("階数", "")
        if item.kaisuStr:
            item.kaisu = converter.parse_numeric(item.kaisuStr)

        item.madori = self._parseMadori(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        # 建ぺい率・容積率
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        # 用途地域・都市計画
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = self._parseSetsudou(response, specs)

        return item

class MizuhoTochiParser(MizuhoParser, TochiParserBase):
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
        self.ModelClass = MizuhoTochi

    def createEntity(self):
        return MizuhoTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 土地面積
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        # 建ぺい率・容積率
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        # 都市計画・用途地域
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = self._parseSetsudou(response, specs)
        item.chimoku = self._parseChimoku(response, specs)
        item.kenchikuJoken = specs.get("建築条件", "")

        return item


class MizuhoInvestmentParser(MizuhoParser, InvestmentParserBase):
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
        return MizuhoInvestment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 表面利回り
        gross_yield_str = specs.get("利回り", "") or specs.get("表面利回り", "") or specs.get("想定利回り", "")
        if gross_yield_str:
            item.grossYield = converter.parse_ratio(gross_yield_str)

        # 想定年間収入
        annual_rent_str = specs.get("想定年間収入", "") or specs.get("年間想定収入", "") or specs.get("想定収入", "") or specs.get("現行年間収入", "")
        if annual_rent_str:
            rent_val = converter.parse_rent(annual_rent_str)
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
        item.soukosuStr = specs.get("総戸数", "") or specs.get("住戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)
        if not item.soukosu and item.biko:
            # 備考欄から「住戸数：24戸」や「総戸数：12戸」を抽出するフォールバック
            m = re.search(r'(?:住戸数|総戸数)[:：](\d+)戸', item.biko)
            if m:
                item.soukosu = int(m.group(1))

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
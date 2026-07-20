# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase
from package.models.mizuho import MizuhoMansion, MizuhoKodate, MizuhoTochi, MizuhoInvestment
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
import logging
import re
import urllib.parse

class MizuhoParser(ParserBase):
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

    async def parseRootPage(self, response: BeautifulSoup):
        # 1. ローカルの一時URLリストファイルがあるかチェックして読み込む (WAF回避のハイブリッド方式)
        import os
        links_file = "src/crawler/Temp/mizuho_links.txt"
        if os.path.exists(links_file):
            logging.info(f"Mizuho: Loading start URLs from temporary file: {links_file}")
            try:
                with open(links_file, "r", encoding="utf-8") as f:
                    urls = [line.strip() for line in f if line.strip()]
                logging.info(f"Mizuho: Loaded {len(urls)} URLs from temporary file.")
                for url in urls:
                    yield url
                return
            except Exception as e:
                logging.error(f"Mizuho: Failed to read temporary URLs file: {e}")

        # 2. 投資用（investment）の場合は、PlaywrightによるWAF回避処理を実行
        if self.property_type == 'investment':
            logging.info("Mizuho: Executing Playwright WAF bypass for investment crawl...")
            try:
                from package.utils.mizuho_bypass import get_mizuho_investment_links
                start_url = "https://www.mizuho-re.co.jp/investors/search/area/all_apartment-building-dormitory-office-store-warehouse-factory-land-other/pref_13/list/"
                urls = await get_mizuho_investment_links(start_url)
                if urls:
                    logging.info(f"Mizuho: Successfully obtained {len(urls)} links via Playwright bypass.")
                    for url in urls:
                        yield url
                    return
                else:
                    logging.warning("Mizuho: Playwright bypass returned 0 links, falling back to static HTML.")
            except Exception as e:
                logging.error(f"Mizuho: Playwright bypass failed: {e}. Falling back to static HTML.")

        # 3. ファイルが無い、またはPlaywrightが失敗した、または居住用の場合のフォールバック（従来処理）
        detail_links = set()
        # /buyers/property/12桁の数字/ または /investors/property/12桁の数字/ パターンのURLを探す
        for a in response.find_all("a", href=re.compile(r'/(?:buyers|investors)/property/\d{12}')):
            href = a.get("href")
            if href:
                full_url = self.getRootDestUrl(href)
                # 末尾のスラッシュの有無などを考慮して正規化
                parsed = urllib.parse.urlparse(full_url)
                path = parsed.path
                if not path.endswith('/'):
                    path += '/'
                normalized = f"{self.BASE_URL}{path}"
                if normalized not in detail_links:
                    detail_links.add(normalized)
                    yield normalized

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
        item.genkyo = specs.get("現況", "") or specs.get("現状", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引渡時期（予定）", "")
        item.tochikenri = specs.get("土地権利", "")
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

class MizuhoMansionParser(MizuhoParser):
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
        item.madori = specs.get("間取り", "")

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
        item.kouzou = specs.get("構造", "") or specs.get("建物構造", "")
        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        item.balconyMensekiStr = specs.get("バルコニー面積", "")
        item.saikou = specs.get("主要採光面", "")

        return item

class MizuhoKodateParser(MizuhoParser):
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
        item.kouzou = specs.get("建物構造", "")
        item.kaisuStr = specs.get("階数", "")
        if item.kaisuStr:
            item.kaisu = converter.parse_numeric(item.kaisuStr)

        item.madori = specs.get("間取り", "")
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
        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = specs.get("接道状況", "")

        return item

class MizuhoTochiParser(MizuhoParser):
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
        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = specs.get("接道状況", "")
        item.chimoku = specs.get("地目", "")
        item.kenchikuJoken = specs.get("建築条件", "")

        return item


class MizuhoInvestmentParser(MizuhoParser):
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

        item.currentStatus = specs.get("現況", "")
        item.kouzou = specs.get("構造", "") or specs.get("建物構造", "")

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


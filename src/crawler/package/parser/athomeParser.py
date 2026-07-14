# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase
from package.models.athome import AthomeMansion, AthomeKodate, AthomeInvestmentApartment, AthomeTochi
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
import logging
import re

logger = logging.getLogger(__name__)

class AthomeParser(ParserBase):
    BASE_URL = 'https://www.athome.co.jp'
    property_type = ''  # Default for type checker

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('athome', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    async def _humanMouseMove(self, page, start_x, start_y, end_x, end_y):
        import random
        import math
        import asyncio
        
        # 3次ベジエ曲線の制御点をランダムに生成
        control_x1 = start_x + (end_x - start_x) * random.uniform(0.1, 0.4) + random.randint(-50, 50)
        control_y1 = start_y + (end_y - start_y) * random.uniform(0.1, 0.4) + random.randint(-50, 50)
        control_x2 = start_x + (end_x - start_x) * random.uniform(0.6, 0.9) + random.randint(-50, 50)
        control_y2 = start_y + (end_y - start_y) * random.uniform(0.6, 0.9) + random.randint(-50, 50)
        
        # 移動ステップ数をランダムに決定 (15〜35ステップ)
        steps = random.randint(15, 35)
        
        for i in range(steps + 1):
            t = i / steps
            # 3次ベジエ曲線公式
            x = (1-t)**3 * start_x + 3*(1-t)**2 * t * control_x1 + 3*(1-t) * t**2 * control_x2 + t**3 * end_x
            y = (1-t)**3 * start_y + 3*(1-t)**2 * t * control_y1 + 3*(1-t) * t**2 * control_y2 + t**3 * end_y
            
            # 手ブレをシミュレート
            if i < steps:
                x += random.uniform(-1.5, 1.5)
                y += random.uniform(-1.5, 1.5)
                
            # イージング（開始と終了はゆっくり、中間は速く）をシミュレートするディレイ
            ease_factor = math.sin(t * math.pi)  # 0 -> 1 -> 0
            delay = 0.005 + (1.0 - ease_factor) * 0.02 + random.uniform(0.001, 0.005)
            
            await page.mouse.move(int(x), int(y))
            await asyncio.sleep(delay)

    async def _getContent(self, session, url):
        import asyncio
        import random
        await asyncio.sleep(1.0)
        try:
            from playwright.async_api import async_playwright
            logging.info(f"Playwright: fetching URL with Bezier-stealth: {url}...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars"
                    ]
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    viewport={'width': 1280, 'height': 800}
                )
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.chrome = {
                        runtime: {}
                    };
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ja', 'en-US', 'en']
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                """)
                page = await context.new_page()
                await page.goto(url, timeout=40000, wait_until="load")
                
                # Human behavior simulation using randomized Bezier curves
                current_x = random.randint(100, 500)
                current_y = random.randint(100, 400)
                await page.mouse.move(current_x, current_y)
                
                for _ in range(random.randint(3, 6)):
                    next_x = random.randint(100, 1100)
                    next_y = random.randint(100, 700)
                    await self._humanMouseMove(page, current_x, current_y, next_x, next_y)
                    current_x, current_y = next_x, next_y
                    await page.wait_for_timeout(random.randint(300, 800))
                
                for _ in range(random.randint(2, 4)):
                    scroll_y = random.randint(200, 600)
                    await page.evaluate(f"window.scrollBy(0, {scroll_y})")
                    await page.wait_for_timeout(random.randint(500, 1000))
                
                await page.evaluate("window.scrollBy(0, -300)")
                await page.wait_for_timeout(1000)
                
                content_str = await page.content()
                await browser.close()
                content_bytes = content_str.encode('utf-8')
                logging.info(f"Playwright stealth fetch success: {len(content_bytes)} bytes for URL: {url}")
                return content_bytes
        except Exception as e:
            logging.error(f"Playwright stealth fetch failed for {url}: {e}")
            return await super()._getContent(session, url)

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        return self.BASE_URL + linkUrl

    async def parseNextPage(self, response):
        """
        一覧ページから「次へ」のページリンクを抽出し、絶対URLとして返す
        """
        from bs4 import BeautifulSoup
        if not isinstance(response, BeautifulSoup):
            import lxml.etree
            html_str = lxml.etree.tostring(response, encoding='utf-8').decode('utf-8')
            response = BeautifulSoup(html_str, "html.parser")

        next_tag = (
            response.select_one(".pagination__item--next a") or 
            response.select_one(".pagination__next a") or
            response.select_one(".prg-next a") or
            response.select_one(".pagination__list a:last-child")
        )
        if not next_tag:
            for a in response.find_all("a"):
                text = a.get_text().strip()
                if "次" in text or text == ">" or text == "»":
                    next_tag = a
                    break
        if next_tag:
            href = next_tag.get("href")
            if href:
                return self.getRootDestUrl(href)
        return ""

    async def parseRootPage(self, response):
        """
        検索結果一覧ページ（BeautifulSoup）から詳細物件ページのURLを抽出する
        """
        from bs4 import BeautifulSoup
        if not isinstance(response, BeautifulSoup):
            import lxml.etree
            html_str = lxml.etree.tostring(response, encoding='utf-8').decode('utf-8')
            response = BeautifulSoup(html_str, "html.parser")

        import urllib.parse
        import re
        detail_links = set()
        
        # 物件詳細URLの抽出 (例: /mansion/6988014156/ や /kodate/12345/ や /toushi/6982464731/)
        for a in response.select("a[href]"):
            href = a.get("href")
            if not href:
                continue
                
            # クエリパラメータを削除してパス部分のみでマッチさせる
            path = urllib.parse.urlparse(href).path
            
            # /mansion/数字/ , /kodate/数字/ , /toushi/数字/ のパターンを検出
            if re.match(r'^/(mansion|kodate|toushi|tochi)/\d+/?$', path):
                full_url = self.getRootDestUrl(path)
                parsed = urllib.parse.urlparse(full_url)
                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if normalized not in detail_links:
                    detail_links.add(normalized)
                    yield normalized

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # 共通の親メソッド呼び出し
        item = super()._parsePropertyDetailPage(item, response)
        
        # タイトル・物件名
        title_tag = response.select_one("#detailTitleArea h2 em")
        if not title_tag:
            title_tag = response.select_one(".bukken-name")
        if not title_tag:
            title_tag = response.select_one("h1")
            
        p_name = title_tag.get_text().strip() if title_tag else ""
        if p_name:
            p_name = p_name.split('\n')[0].strip()
        item.propertyName = p_name
        
        # 1. 住所
        item.address = self._parseAddress(response)
        
        # 2. 価格
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        
        # 3. 交通
        item.traffic = self._parseTraffic(response)
        self._populateTraffic(item, item.traffic)
        
        # th/td テーブルの値を辞書化して抽出を容易にする
        specs = self._get_specs_table(response)
        
        # 4. 共通情報
        item.kouzou = specs.get("建物構造", "")
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)
            
        return item

    def _get_specs_table(self, response: BeautifulSoup) -> dict:
        """
        アットホーム詳細ページの物件スペックテーブルを辞書化して返す。
        """
        specs = {}
        # 任意のテーブル行からth/tdペアを収集する
        for row in response.select("table tr"):
            th_tags = row.find_all("th")
            td_tags = row.find_all("td")
            for th, td in zip(th_tags, td_tags):
                label = th.get_text().strip()
                val = td.get_text().strip()
                if label:
                    # 改行後の不要なテキスト（支払シミュレーション等）を取り除く
                    val_cleaned = val.split('\n')[0].strip()
                    specs[label] = val_cleaned
        return specs

    def _parseAddress(self, response: BeautifulSoup) -> str:
        for th in response.find_all("th"):
            text = th.get_text().strip()
            if "所在地" in text and th.find_next_sibling("td"):
                return th.find_next_sibling("td").get_text().strip().split('\n')[0].strip()
        return ""

    def _parsePriceStr(self, response: BeautifulSoup) -> str:
        for th in response.find_all("th"):
            text = th.get_text().strip()
            if "価格" in text and th.find_next_sibling("td"):
                return th.find_next_sibling("td").get_text().strip().split('\n')[0].strip()
        return ""

    def _parsePrice(self, response: BeautifulSoup) -> int:
        pstr = self._parsePriceStr(response)
        return converter.parse_price(pstr) or 0

    def _parseTraffic(self, response: BeautifulSoup) -> str:
        for th in response.find_all("th"):
            text = th.get_text().strip()
            if "交通" in text and th.find_next_sibling("td"):
                return th.find_next_sibling("td").get_text().strip()
        return ""

class AthomeMansionParser(AthomeParser):
    property_type = 'mansion'

    def createEntity(self):
        return AthomeMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs_table(response)
        
        item.madori = specs.get("間取り", "")
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)
            
        item.kaisuStr = specs.get("階建 / 階", "")
        item.saikou = specs.get("主要採光面", "")
        item.soukosuStr = specs.get("総戸数", "")
        item.soukosu = converter.parse_number(item.soukosuStr)
        item.kanrihiStr = specs.get("管理費等", "")
        item.kanrihi = converter.parse_price(item.kanrihiStr)
        item.syuzenTsumitateStr = specs.get("修繕積立金", "")
        item.syuzenTsumitate = converter.parse_price(item.syuzenTsumitateStr)
        item.tyusyajo = specs.get("駐車場", "")
        
        return item


class AthomeKodateParser(AthomeParser):
    property_type = 'kodate'

    def createEntity(self):
        return AthomeKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs_table(response)
        
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
            
        item.tatemonoMensekiStr = specs.get("建物面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)
            
        item.kaisuStr = specs.get("階建 / 階", "")
        item.tyusyajo = specs.get("駐車場", "")
        item.chimoku = specs.get("地目", "")
        item.kenpeiStr = specs.get("建ぺい率", "")
        item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        item.youseki = converter.parse_ratio(item.yousekiStr)
        item.youtoChiiki = specs.get("用途地域", "")
        item.setsudou = specs.get("接道状況", "")
        
        # 土地スペックパラメータ抽出（間口、道路幅、方位、私道公道など）
        road_info = specs.get("前面道路", "")
        setsudou_info = specs.get("接道状況", "")
        maguchi_info = specs.get("間口", "") or specs.get("接面", "")
        
        # 間口 (maguchi)
        item.maguchiStr = maguchi_info
        if maguchi_info:
            mag_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', maguchi_info)
            if mag_match:
                from decimal import Decimal
                item.maguchi = Decimal(mag_match.group(1))
        elif setsudou_info:
            mag_match = re.search(r'(?:間口|接面|接す|接道)\s*[：:]?\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', setsudou_info)
            if mag_match:
                from decimal import Decimal
                item.maguchi = Decimal(mag_match.group(1))
                
        # 前面道路幅員 (roadWidth)
        road_width_str = ""
        if road_info:
            width_match = re.search(r'(?:幅員|幅|道路|前面)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', road_info)
            if width_match:
                road_width_str = width_match.group(0)
                from decimal import Decimal
                item.roadWidth = Decimal(width_match.group(1))
            else:
                dir_width_match = re.search(r'(?:北東|北西|南東|南西|北|南|東|西)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)', road_info)
                if dir_width_match:
                    road_width_str = dir_width_match.group(0)
                    from decimal import Decimal
                    item.roadWidth = Decimal(dir_width_match.group(1))
        elif setsudou_info:
            width_match = re.search(r'(?:幅員|幅|道路|前面)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', setsudou_info)
            if width_match:
                road_width_str = width_match.group(0)
                from decimal import Decimal
                item.roadWidth = Decimal(width_match.group(1))
            else:
                dir_width_match = re.search(r'(?:北東|北西|南東|南西|北|南|東|西)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)', setsudou_info)
                if dir_width_match:
                    road_width_str = dir_width_match.group(0)
                    from decimal import Decimal
                    item.roadWidth = Decimal(dir_width_match.group(1))
        item.roadWidthStr = road_width_str
        
        # 道路方位 (roadDirection)
        road_dir = ""
        if road_info:
            dir_match = re.search(r'(北東|北西|南東|南西|北|南|東|西)', road_info)
            if dir_match: road_dir = dir_match.group(1)
        elif setsudou_info:
            dir_match = re.search(r'(北東|北西|南東|南西|北|南|東|西)', setsudou_info)
            if dir_match: road_dir = dir_match.group(1)
        item.roadDirection = road_dir
        
        # 道路私道区分 (roadType)
        road_type = ""
        if road_info:
            type_match = re.search(r'(公道|私道)', road_info)
            if type_match: road_type = type_match.group(1)
        elif setsudou_info:
            type_match = re.search(r'(公道|私道)', setsudou_info)
            if type_match: road_type = type_match.group(1)
        item.roadType = road_type
        
        # 接道構造（角地など）(roadStructure)
        road_struct = "中間地"
        if setsudou_info:
            struct_match = re.search(r'(角地|二方|三方|四方|敷延|袋小路|中間地|両面道路)', setsudou_info)
            if struct_match: road_struct = struct_match.group(1)
        item.roadStructure = road_struct
        
        # 奥行き (okuyuki)
        if item.tochiMenseki and getattr(item, 'maguchi', None) and item.maguchi > 0:
            from decimal import Decimal
            item.okuyuki = round(item.tochiMenseki / item.maguchi, 2)
            item.okuyukiStr = f"{item.okuyuki}m"
            
        return item


class AthomeInvestmentApartmentParser(AthomeParser):
    property_type = 'investmentapartment'

    def createEntity(self):
        return AthomeInvestmentApartment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # 物件種目の動的判定と委譲処理 (Dynamic Dispatch)
        specs = self._get_specs_table(response)
        shumoku = specs.get("物件種目", "")
        
        if shumoku:
            # 区分マンションの場合のみ、区分用のAthomeMansionParserに委譲する（一棟マンションは一棟アパートと同様に本クラスでそのままパースする）
            if "マンション" in shumoku and "一棟" not in shumoku:
                parser = AthomeMansionParser()
                new_item = parser.createEntity()
                new_item.pageUrl = item.pageUrl
                return parser._parsePropertyDetailPage(new_item, response)
            elif "戸建" in shumoku or "テラス" in shumoku:
                parser = AthomeKodateParser()
                new_item = parser.createEntity()
                new_item.pageUrl = item.pageUrl
                return parser._parsePropertyDetailPage(new_item, response)
            elif "土地" in shumoku:
                parser = AthomeTochiParser()
                new_item = parser.createEntity()
                new_item.pageUrl = item.pageUrl
                return parser._parsePropertyDetailPage(new_item, response)
                
        item = super()._parsePropertyDetailPage(item, response)
        
        # 投資用固有情報
        yield_str = specs.get("利回り", "")
        item.grossYield = converter.parse_ratio(yield_str)
        
        rent_str = specs.get("想定賃料", "")
        item.annualRent = converter.parse_price(rent_str)
        item.monthlyRent = int(item.annualRent / 12) if item.annualRent else 0
        item.currentStatus = specs.get("現況", "")
        
        # 面積・構造
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
            
        item.tatemonoMensekiStr = specs.get("建物面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)
            
        item.soukosuStr = specs.get("総戸数", "")
        item.soukosu = converter.parse_number(item.soukosuStr)
        item.kaisuStr = specs.get("階建 / 階", "")
        
        # 土地詳細
        item.kenpeiStr = specs.get("建ぺい率", "")
        item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        item.youseki = converter.parse_ratio(item.yousekiStr)
        item.setsudou = specs.get("接道状況", "")
        item.chimoku = specs.get("地目", "")
        item.youtoChiiki = specs.get("用途地域", "")
        item.tochikenri = specs.get("土地権利", "")
        
        return item


class AthomeTochiParser(AthomeParser):
    property_type = 'tochi'

    def createEntity(self):
        return AthomeTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs_table(response)
        
        # 土地面積
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
            
        # 用途地域・建容
        item.youtoChiiki = specs.get("用途地域", "")
        item.kenpeiStr = specs.get("建ぺい率", "")
        item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        item.youseki = converter.parse_ratio(item.yousekiStr)
        
        item.chimoku = specs.get("地目", "")
        item.setsudou = specs.get("接道状況", "")
        
        # 土地スペックパラメータ抽出（間口、道路幅、方位、私道公道など）
        road_info = specs.get("前面道路", "")
        setsudou_info = specs.get("接道状況", "")
        maguchi_info = specs.get("間口", "") or specs.get("接面", "")
        
        # 間口 (maguchi)
        item.maguchiStr = maguchi_info
        if maguchi_info:
            mag_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', maguchi_info)
            if mag_match:
                from decimal import Decimal
                item.maguchi = Decimal(mag_match.group(1))
        elif setsudou_info:
            mag_match = re.search(r'(?:間口|接面|接す)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', setsudou_info)
            if mag_match:
                from decimal import Decimal
                item.maguchi = Decimal(mag_match.group(1))
                
        # 前面道路幅員 (roadWidth)
        road_width_str = ""
        if road_info:
            width_match = re.search(r'(?:幅員|幅)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', road_info)
            if width_match:
                road_width_str = width_match.group(0)
                from decimal import Decimal
                item.roadWidth = Decimal(width_match.group(1))
        if not item.roadWidth and setsudou_info:
            width_match = re.search(r'(?:幅員|幅|道路)\s*(?:約)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)?', setsudou_info)
            if width_match:
                road_width_str = width_match.group(0)
                from decimal import Decimal
                item.roadWidth = Decimal(width_match.group(1))
        item.roadWidthStr = road_width_str
        
        # 接道方位 (roadDirection)
        direction_match = None
        if road_info:
            direction_match = re.search(r'(北東|北西|南東|南西|北|南|東|西)', road_info)
        if not direction_match and setsudou_info:
            direction_match = re.search(r'(北東|北西|南東|南西|北|南|東|西)', setsudou_info)
        item.roadDirection = direction_match.group(1) if direction_match else ""
        
        # 道路区分 (roadType: 公道/私道)
        type_match = None
        if road_info:
            type_match = re.search(r'(公道|私道)', road_info)
        if not type_match and setsudou_info:
            type_match = re.search(r'(公道|私道)', setsudou_info)
        item.roadType = type_match.group(1) if type_match else ""
        
        # 接道状況 (roadStructure)
        structure_match = None
        if setsudou_info:
            structure_match = re.search(r'(角地|二方|三方|四方|敷延|袋小路|中間地|両面道路)', setsudou_info)
        item.roadStructure = structure_match.group(1) if structure_match else "中間地"
        
        return item


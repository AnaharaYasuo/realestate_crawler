# -*- coding: utf-8 -*-
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup
from package.parser.baseParser import InvestmentParserBase, KodateParserBase, MansionParserBase, ParserBase, TochiParserBase, ListingEndedException
from package.models.athome import AthomeMansion, AthomeKodate, AthomeInvestmentApartment, AthomeTochi
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
from decimal import Decimal
import asyncio
import math
import secrets
import logging
import re
import urllib.parse

logger = logging.getLogger(__name__)

ATHOME_NAV_KEYWORDS = ("/list/", "-city", "/city/", "/map/", "/line/", "/rosen_map/", "/buyall/")
ATHOME_LIST_KEYWORDS = ("tokyo", "-city", "/city/", "/list/", "toushi", "chuko", "buy_other")


class AthomeParser(ParserBase):

    def _get_specs(self, response):
        return self._get_specs_table(response)

    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    def _parseKouzou(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("構造", "") or specs.get("建物構造", "")

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    BASE_URL = 'https://www.athome.co.jp'
    property_type = ''  # Default for type checker

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('athome', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    async def _humanMouseMove(self, page, start_x, start_y, end_x, end_y):
        """Move a Playwright mouse between two points along a randomized path."""
        prng = secrets.SystemRandom()
        
        # 3次ベジエ曲線の制御点をランダムに生成
        control_x1 = start_x + (end_x - start_x) * prng.uniform(0.1, 0.4) + prng.randint(-50, 50)  # NOSONAR
        control_y1 = start_y + (end_y - start_y) * prng.uniform(0.1, 0.4) + prng.randint(-50, 50)  # NOSONAR
        control_x2 = start_x + (end_x - start_x) * prng.uniform(0.6, 0.9) + prng.randint(-50, 50)  # NOSONAR
        control_y2 = start_y + (end_y - start_y) * prng.uniform(0.6, 0.9) + prng.randint(-50, 50)  # NOSONAR
        
        # 移動ステップ数をランダムに決定 (15〜35ステップ)
        steps = prng.randint(15, 35)  # NOSONAR
        
        for i in range(steps + 1):
            t = i / steps
            # 3次ベジエ曲線公式
            x = (1-t)**3 * start_x + 3*(1-t)**2 * t * control_x1 + 3*(1-t) * t**2 * control_x2 + t**3 * end_x
            y = (1-t)**3 * start_y + 3*(1-t)**2 * t * control_y1 + 3*(1-t) * t**2 * control_y2 + t**3 * end_y
            
            # 手ブレをシミュレート
            if i < steps:
                x += prng.uniform(-1.5, 1.5)  # NOSONAR
                y += prng.uniform(-1.5, 1.5)  # NOSONAR
                
            # イージング（開始と終了はゆっくり、中間は速く）をシミュレートするディレイ
            ease_factor = math.sin(t * math.pi)  # 0 -> 1 -> 0
            delay = 0.005 + (1.0 - ease_factor) * 0.02 + prng.uniform(0.001, 0.005)  # NOSONAR
            
            await page.mouse.move(int(x), int(y))
            await asyncio.sleep(delay)

    async def _getContent(self, session, url):
        """Fetch a URL with Playwright, falling back to the base HTTP fetcher."""
        await asyncio.sleep(0.5)
        try:
            from playwright.async_api import async_playwright

            logging.info(f"Playwright: fetching URL with stealth: {url}...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-infobars',
                        '--window-position=0,0',
                        '--ignore-certificate-errors',
                        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
                    ]
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    locale='ja-JP',
                    timezone_id='Asia/Tokyo'
                )
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US', 'en'] });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    window.chrome = { runtime: {} };
                """)
                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    await page.wait_for_timeout(2000)
                    try:
                        await page.wait_for_selector("a[href*='bklist'], a[href*='bkdetail'], a[href*='tokyo'], .item-list, .building-list", timeout=5000)
                    except Exception:
                        pass
                except Exception as goto_err:
                    logging.warning(f"Playwright goto warning for {url}: {goto_err}")
                
                content_str = await page.content()
                if "認証にご協力ください" in content_str or "認証中" in content_str or "Just a moment..." in content_str:
                    logging.info(f"Retrying page load for challenge screen at {url}...")
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(3000)
                        content_str = await page.content()
                    except Exception as reload_err:
                        logging.warning(f"Playwright reload warning for {url}: {reload_err}")

                await browser.close()
                content_bytes = content_str.encode('utf-8')
                logging.info(f"Playwright stealth fetch success: {len(content_bytes)} bytes for URL: {url}")
                return content_bytes
        except Exception as e:
            logging.error(f"Playwright stealth fetch failed for {url}: {e}")
            return await super()._getContent(session, url)

    def getRootDestUrl(self, linkUrl, base_domain=None):
        if not linkUrl:
            return ""
        if linkUrl.startswith('http'):
            return re.sub(r'(?<!:)//+', '/', linkUrl)
        base = base_domain or getattr(self, 'current_base_domain', None) or self.BASE_URL
        joined = urllib.parse.urljoin(base, linkUrl)
        return re.sub(r'(?<!:)//+', '/', joined)

    @staticmethod
    def _find_sequential_numbered_tag(response: BeautifulSoup):
        curr_tag = response.select_one(".pagination__list .current, .pagination__list .is-current, .pagination__item--current")
        if not curr_tag:
            return None
        try:
            curr_num = int(curr_tag.get_text().strip())
        except (ValueError, TypeError):
            return None
        target_str = str(curr_num + 1)
        for a in response.select(".pagination__list a"):
            if a.get_text().strip() == target_str:
                return a
        return None

    @staticmethod
    def _find_text_next_tag(response: BeautifulSoup):
        for a in response.find_all("a"):
            text = a.get_text().strip()
            if "次" in text or text in (">", "»"):
                return a
        return None

    async def parseNextPage(self, response, base_domain: Optional[str] = None):
        """
        一覧ページから「次へ」のページリンクを抽出し、絶対URLとして返す
        """
        from bs4 import BeautifulSoup
        if not isinstance(response, BeautifulSoup):
            import lxml.etree
            html_str = lxml.etree.tostring(response, encoding='utf-8').decode('utf-8')
            response = BeautifulSoup(html_str, "html.parser")

        next_tag = (
            response.select_one(".pagination__item--next a")
            or response.select_one(".pagination__next a")
            or response.select_one(".prg-next a")
            or self._find_sequential_numbered_tag(response)
            or self._find_text_next_tag(response)
        )
        if next_tag and next_tag.get("href"):
            return self.getRootDestUrl(next_tag["href"], base_domain=base_domain)
        return ""

    def _normalize_athome_url(self, href: str, base_domain: str) -> str:
        full_url = self.getRootDestUrl(href, base_domain=base_domain)
        parsed = urllib.parse.urlparse(full_url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized

    def _is_athome_detail_path(self, path: str, href: str) -> bool:
        if "bkdetail" in href:
            return True
        pattern = r'/(mansion|kodate|toushi|tochi|bldg|building|detail|buy_toushi|buy_other)/\d{6,}/?'
        return bool(re.search(pattern, path))

    def _extract_detail_links_from_soup(self, soup: BeautifulSoup, base_domain: str):
        for a in soup.select("a[href]"):
            sub_href = a.get("href")
            if not sub_href:
                continue
            sub_path = urllib.parse.urlparse(sub_href).path
            sub_is_nav = any(nav in sub_path for nav in ATHOME_NAV_KEYWORDS)
            if not sub_is_nav and self._is_athome_detail_path(sub_path, sub_href):
                yield self._normalize_athome_url(sub_href, base_domain)

    def _is_athome_list_url(self, path: str, href: str, is_list_or_nav: bool) -> bool:
        if is_list_or_nav or "bklist" in href or "sitemaplist" in path:
            return True
        return any(kw in path for kw in ATHOME_LIST_KEYWORDS)

    async def _crawl_single_list_page(self, curr_l_url: str, base_domain: str) -> Tuple[List[str], Optional[str]]:
        try:
            list_html = await self._getContent(None, curr_l_url)
            if not list_html:
                return [], None
            parsed_curr = urllib.parse.urlparse(curr_l_url)
            page_base = f"{parsed_curr.scheme or 'https'}://{parsed_curr.netloc}" if parsed_curr.netloc else base_domain
            sub_soup = BeautifulSoup(list_html, "html.parser")
            links = list(self._extract_detail_links_from_soup(sub_soup, page_base))
            next_page = await self.parseNextPage(sub_soup, base_domain=page_base)
            return links, next_page
        except Exception as e:
            logging.warning(f"Error expanding list_link {curr_l_url}: {e}")
            return [], None

    async def _expand_sub_list_pages(self, list_links, base_domain: str):
        visited_l_urls = set()
        for l_url in list_links:
            curr_l_url = l_url
            visited_l_urls.add(curr_l_url)
            while curr_l_url:
                links, next_page = await self._crawl_single_list_page(curr_l_url, base_domain)
                for normalized in links:
                    yield normalized
                if next_page and next_page not in visited_l_urls:
                    visited_l_urls.add(next_page)
                    curr_l_url = next_page
                else:
                    break

    ATHOME_ALLOWED_HOSTS = ("www.athome.co.jp", "toushi-athome.jp", "athome.co.jp")

    def _classify_and_collect_athome_url(self, href: str, detail_links: set, list_links: set) -> Tuple[Optional[str], Optional[str]]:
        parsed_url = urllib.parse.urlparse(href)
        if parsed_url.netloc and parsed_url.netloc not in self.ATHOME_ALLOWED_HOSTS:
            return None, None
        if parsed_url.scheme and parsed_url.scheme not in ("http", "https"):
            return None, None
        path = parsed_url.path
        netloc = parsed_url.netloc or "www.athome.co.jp"
        base = f"{parsed_url.scheme or 'https'}://{netloc}"
        is_list_or_nav = any(nav in path for nav in ATHOME_NAV_KEYWORDS)
        normalized = self._normalize_athome_url(href, base)
        
        if not is_list_or_nav and self._is_athome_detail_path(path, href):
            if normalized not in detail_links:
                detail_links.add(normalized)
                return normalized, None
        elif self._is_athome_list_url(path, href, is_list_or_nav):
            if normalized not in list_links and normalized != "https://toushi-athome.jp/":
                list_links.add(normalized)
        return None, base

    async def parseRootPage(self, response):
        """
        検索結果一覧ページまたはエリア選択ページ（BeautifulSoup）から詳細物件ページ／市区町村一覧のURLを抽出する
        """
        if not isinstance(response, BeautifulSoup):
            import lxml.etree
            html_str = lxml.etree.tostring(response, encoding='utf-8').decode('utf-8')
            response = BeautifulSoup(html_str, "html.parser")

        detail_links = set()
        list_links = set()
        base = "https://www.athome.co.jp"
        
        for a in response.select("a[href]"):
            href = a.get("href")
            if not href:
                continue
            detail_url, found_base = self._classify_and_collect_athome_url(href, detail_links, list_links)
            if found_base:
                base = found_base
            if detail_url:
                yield detail_url

        if list_links:
            async for normalized in self._expand_sub_list_pages(list_links, base):
                if normalized not in detail_links:
                    detail_links.add(normalized)
                    yield normalized

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # 0. 掲載終了・物件不在の早期検知
        title_text = response.title.get_text().strip() if response.title else ""
        body_text = response.body.get_text() if response.body else ""
        if any(msg in title_text or msg in body_text for msg in ["掲載を終了しました", "お探しの物件は見つかりませんでした", "指定された物件は掲載を終了", "掲載終了物件"]) or response.select_one(".mod-message-end, .not-found"):
            raise ListingEndedException("Athome listing ended or not found")

        # 共通の親メソッド呼び出し
        item = super()._parsePropertyDetailPage(item, response)
        
        # 1. タイトル・物件名
        title_tag = response.select_one("#detailTitleArea h2 em") or response.select_one(".bukken-name") or response.select_one("h1")
        p_name = title_tag.get_text().strip() if title_tag else ""
        if not p_name and response.title:
            title_text = response.title.get_text().strip()
            title_text = re.sub(r'^【アットホーム】', '', title_text).strip()
            title_text = re.sub(r'｜.*$', '', title_text).strip()
            p_name = title_text
            
        if p_name:
            p_name = p_name.split('\n')[0].strip()
        item.propertyName = p_name
        
        # 2. 住所
        item.address = self._parseAddress(response)
        if item.address:
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        
        # 2. 価格
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        
        # 3. 交通
        item.traffic = self._parseTraffic(response)
        self._populateTraffic(item, item.traffic)
        
        # th/td テーブルの値を辞書化して抽出を容易にする
        specs = self._get_specs_table(response)
        
        # 4. 共通情報
        item.kouzou = self._parseKouzou(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)
            
        # 土地権利および地代
        item.tochikenri = self._parseRights(response, specs)
        item.chidaiStr = self._parseChidaiStr(response, specs)
        item.chidai = self._parseChidai(response, specs)
            
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

class AthomeMansionParser(AthomeParser, MansionParserBase):
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
        return AthomeMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs_table(response)
        
        item.madori = self._parseMadori(response, specs)
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


class AthomeKodateParser(AthomeParser, KodateParserBase):
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
        item.chimoku = self._parseChimoku(response, specs)
        item.kenpeiStr = specs.get("建ぺい率", "")
        item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        item.youseki = converter.parse_ratio(item.yousekiStr)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)
        
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


class AthomeInvestmentApartmentParser(AthomeParser, InvestmentParserBase):
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
        item.genkyo = self._parseCurrentStatus(response, specs)
        item.currentStatus = item.genkyo
        
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
        item.setsudou = self._parseSetsudou(response, specs)
        item.chimoku = self._parseChimoku(response, specs)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.tochikenri = self._parseRights(response, specs)
        
        return item


class AthomeTochiParser(AthomeParser, TochiParserBase):
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
        return AthomeTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs_table(response)
        
        # 土地面積
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
            
        # 用途地域・建容
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kenpeiStr = specs.get("建ぺい率", "")
        item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        item.youseki = converter.parse_ratio(item.yousekiStr)
        
        item.chimoku = self._parseChimoku(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)
        
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

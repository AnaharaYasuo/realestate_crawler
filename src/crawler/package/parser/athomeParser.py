# -*- coding: utf-8 -*-
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup
from package.parser.baseParser import InvestmentParserBase, KodateParserBase, MansionParserBase, ParserBase, TochiParserBase, ListingEndedException, SkipPropertyException
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

HTML_PARSER = "html.parser"
LABEL_KAIDATE_KAI = "階建 / 階"

ATHOME_NAV_KEYWORDS = ("/list/", "-city", "/city/", "/map/", "/line/", "/rosen_map/", "/buyall/")
ATHOME_LIST_KEYWORDS = ("tokyo", "-city", "/city/", "/list/", "toushi", "chuko", "buy_other")
_ATHOME_DIRECTION_RE = r'(北東|北西|南東|南西|北|南|東|西)'
_ATHOME_WIDTH_RE = r'(?:幅員|幅|道路|前面)\s*(?:約\s*)?(\d+(?:\.\d+)?)\s*[m米]?'
_ATHOME_DIR_WIDTH_RE = (
    r'(?:北東|北西|南東|南西|北|南|東|西)\s*(?:約\s*)?(\d+(?:\.\d+)?)\s*[m米]'
)
_ATHOME_MAGUCHI_RE = r'(\d+(?:\.\d+)?)\s*[m米]?'
_ATHOME_MAGUCHI_IN_SETSUDOU_RE = (
    r'(?:間口|接面|接す|接道)\s*[：:]?\s*(?:約\s*)?(\d+(?:\.\d+)?)\s*[m米]?'
)
_ATHOME_ROAD_TYPE_RE = r'(公道|私道)'
_ATHOME_ROAD_STRUCT_RE = r'(角地|二方|三方|四方|敷延|袋小路|中間地|両面道路)'
_ATHOME_CHALLENGE_MARKERS = ("認証にご協力ください", "認証中", "Just a moment...")
_ATHOME_PLAYWRIGHT_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-infobars',
    '--window-position=0,0',
    '--ignore-certificate-errors',
    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
]
_ATHOME_STEALTH_INIT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    window.chrome = { runtime: {} };
"""
_ATHOME_CONTENT_READY_JS = """() => {
    const text = document.body ? document.body.innerText : '';
    if (text.includes('認証中') || text.includes('認証にご協力')) {
        return false;
    }
    const hrefs = Array.from(document.querySelectorAll('a[href]'))
        .map(a => a.getAttribute('href') || '');
    const hasDetail = hrefs.some(h =>
        /\\/(mansion|kodate|tochi|buy_other)\\/\\d{6,}/.test(h)
        || h.includes('bkdetail')
    );
    const hasPriceTable = text.includes('価格')
        && !!document.querySelector('#detailTitleArea, table');
    return hasDetail || hasPriceTable;
}"""
_ATHOME_LIST_SELECTOR = (
    "a[href*='bklist'], a[href*='bkdetail'], "
    "a[href*='tokyo'], .item-list, .building-list, "
    "#detailTitleArea"
)


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

    async def _athome_scroll_midpage(self, page) -> None:
        for _ in range(2):
            try:
                await page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight / 2)"
                )
                break
            except Exception as scroll_err:
                logger.debug("Athome scroll retry: %s", scroll_err)
                await page.wait_for_timeout(400)

    async def _athome_wait_content_ready(self, page) -> None:
        try:
            await page.wait_for_function(_ATHOME_CONTENT_READY_JS, timeout=3500)
        except Exception as wait_err:
            logger.debug("Athome content-ready wait skipped: %s", wait_err)
            try:
                await page.wait_for_selector(_ATHOME_LIST_SELECTOR, timeout=2500)
            except Exception as sel_err:
                logger.debug("Athome list selector wait skipped: %s", sel_err)

    async def _athome_settle_page(self, page, url: str) -> None:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=12000)
            # Athome often issues a follow-up navigation; wait for it to settle.
            try:
                await page.wait_for_load_state("networkidle", timeout=1500)
            except Exception as idle_err:
                logger.debug("Athome networkidle wait skipped: %s", idle_err)
            await page.wait_for_timeout(300)
            await self._athome_scroll_midpage(page)
            await page.wait_for_timeout(300)
            await self._athome_wait_content_ready(page)
        except Exception as goto_err:
            logger.warning("Playwright goto warning for %s: %s", url, goto_err)

    async def _athome_reload_if_challenge(self, page, url: str, content_str: str) -> str:
        if not any(m in content_str for m in _ATHOME_CHALLENGE_MARKERS):
            return content_str
        logger.info("Retrying page load for challenge screen at %s...", url)
        try:
            await page.reload(wait_until="domcontentloaded", timeout=10000)
            try:
                await page.wait_for_load_state("networkidle", timeout=2000)
            except Exception as idle_err:
                logger.debug("Athome reload networkidle skipped: %s", idle_err)
            await page.wait_for_timeout(800)
            return await page.content()
        except Exception as reload_err:
            logger.warning("Playwright reload warning for %s: %s", url, reload_err)
            return content_str

    async def _athome_fetch_with_playwright(self, url: str) -> bytes:
        from playwright.async_api import async_playwright

        logger.info("Playwright: fetching URL with stealth: %s...", url)
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=_ATHOME_PLAYWRIGHT_ARGS,
            )
            try:
                context = await browser.new_context(
                    user_agent=(
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                        '(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
                    ),
                    viewport={'width': 1920, 'height': 1080},
                    locale='ja-JP',
                    timezone_id='Asia/Tokyo',
                )
                try:
                    await context.add_init_script(_ATHOME_STEALTH_INIT)
                    page = await context.new_page()
                    try:
                        await self._athome_settle_page(page, url)
                        content_str = await page.content()
                        content_str = await self._athome_reload_if_challenge(page, url, content_str)
                    finally:
                        await page.close()
                finally:
                    await context.close()
            finally:
                await browser.close()
            content_bytes = content_str.encode('utf-8')
            logger.info(
                "Playwright stealth fetch success: %s bytes for URL: %s",
                len(content_bytes),
                url,
            )
            return content_bytes

    async def _getContent(self, session, url):
        """Fetch a URL with Playwright, falling back to the base HTTP fetcher."""
        await asyncio.sleep(0.5)
        try:
            return await self._athome_fetch_with_playwright(url)
        except Exception as e:
            logger.exception("Playwright stealth fetch failed for %s: %s", url, e)
            return await super()._getContent(session, url)

    @staticmethod
    def _athome_parse_maguchi(maguchi_info: str, setsudou_info: str):
        if maguchi_info:
            mag_match = re.search(_ATHOME_MAGUCHI_RE, maguchi_info)
            if mag_match:
                return Decimal(mag_match.group(1))
        if setsudou_info:
            mag_match = re.search(_ATHOME_MAGUCHI_IN_SETSUDOU_RE, setsudou_info)
            if mag_match:
                return Decimal(mag_match.group(1))
        return None

    @staticmethod
    def _athome_parse_road_width(road_info: str, setsudou_info: str):
        for text in (road_info, setsudou_info):
            if not text:
                continue
            width_match = re.search(_ATHOME_WIDTH_RE, text)
            if width_match:
                return width_match.group(0), Decimal(width_match.group(1))
            dir_width_match = re.search(_ATHOME_DIR_WIDTH_RE, text)
            if dir_width_match:
                return dir_width_match.group(0), Decimal(dir_width_match.group(1))
        return "", None

    @staticmethod
    def _athome_first_regex_group(*texts_and_pattern) -> str:
        *texts, pattern = texts_and_pattern
        for text in texts:
            if not text:
                continue
            m = re.search(pattern, text)
            if m:
                return m.group(1)
        return ""

    def _athome_apply_road_specs(self, item, specs: dict, *, default_struct: str = "中間地") -> None:
        road_info = specs.get("前面道路", "")
        setsudou_info = specs.get("接道状況", "")
        maguchi_info = specs.get("間口", "") or specs.get("接面", "")

        item.maguchiStr = maguchi_info
        maguchi = self._athome_parse_maguchi(maguchi_info, setsudou_info)
        if maguchi is not None:
            item.maguchi = maguchi

        road_width_str, road_width = self._athome_parse_road_width(road_info, setsudou_info)
        item.roadWidthStr = road_width_str
        if road_width is not None:
            item.roadWidth = road_width

        item.roadDirection = self._athome_first_regex_group(
            road_info, setsudou_info, _ATHOME_DIRECTION_RE
        )
        item.roadType = self._athome_first_regex_group(
            road_info, setsudou_info, _ATHOME_ROAD_TYPE_RE
        )
        struct = self._athome_first_regex_group(setsudou_info, _ATHOME_ROAD_STRUCT_RE)
        item.roadStructure = struct or default_struct

    def _athome_apply_okuyuki(self, item) -> None:
        if item.tochiMenseki and getattr(item, 'maguchi', None) and item.maguchi > 0:
            item.okuyuki = round(item.tochiMenseki / item.maguchi, 2)
            item.okuyukiStr = f"{item.okuyuki}m"

    def getRootDestUrl(self, link_url, base_domain=None):
        if not link_url:
            return ""
        if link_url.startswith('http'):
            return re.sub(r'(?<!:)//+', '/', link_url)
        base = base_domain or getattr(self, 'current_base_domain', None) or self.BASE_URL
        joined = urllib.parse.urljoin(base, link_url)
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
            response = BeautifulSoup(html_str, HTML_PARSER)

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
        if "RECOMMFLG=1" in href or "sref=nw_reco" in href:
            return False
        if "bkdetail" in href:
            return True
        ptype = getattr(self, "property_type", "")
        type_patterns = {
            "kodate": r'/(kodate|buy/kodate)/\d{6,}/?',
            "mansion": r'/(mansion|buy/mansion)/\d{6,}/?',
            "tochi": r'/(tochi|buy/tochi)/\d{6,}/?',
            "investmentapartment": r'/(buy_other|toushi|bldg|building|buy_toushi)/\d{6,}/?',
        }
        pattern = type_patterns.get(ptype, r'/(mansion|kodate|toushi|tochi|bldg|building|detail|buy_toushi|buy_other)/\d{6,}/?')
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
            sub_soup = BeautifulSoup(list_html, HTML_PARSER)
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
                parsed_next = urllib.parse.urlparse(next_page or "")
                if (
                    next_page
                    and parsed_next.scheme in ("http", "https")
                    and parsed_next.netloc in self.ATHOME_ALLOWED_HOSTS
                    and next_page not in visited_l_urls
                ):
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
            response = BeautifulSoup(html_str, HTML_PARSER)

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

    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        _ = specs
        for th in response.find_all("th"):
            text = th.get_text().strip()
            if "所在地" in text and th.find_next_sibling("td"):
                return th.find_next_sibling("td").get_text().strip().split('\n')[0].strip()
        return ""

    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        _ = specs
        for th in response.find_all("th"):
            text = th.get_text().strip()
            if "価格" in text and th.find_next_sibling("td"):
                return th.find_next_sibling("td").get_text().strip().split('\n')[0].strip()
        return ""

    def _parsePrice(self, response: BeautifulSoup, specs=None) -> int:
        pstr = self._parsePriceStr(response, specs)
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
            
        item.kaisuStr = specs.get(LABEL_KAIDATE_KAI, "")
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
        page_url = getattr(item, "pageUrl", "")
        name = self._parsePropertyName(response)
        if any(kw in page_url for kw in ("/buy_other/", "/toushi/", "/bldg/")) or any(kw in name for kw in ("一棟売アパート", "一棟売マンション")):
            raise SkipPropertyException(f"Non-kodate property skipped: {page_url} ({name})")
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs_table(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        item.kaisuStr = specs.get(LABEL_KAIDATE_KAI, "")
        item.tyusyajo = specs.get("駐車場", "")
        item.chimoku = self._parseChimoku(response, specs)
        item.kenpeiStr = specs.get("建ぺい率", "")
        item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        item.youseki = converter.parse_ratio(item.yousekiStr)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)

        self._athome_apply_road_specs(item, specs)
        self._athome_apply_okuyuki(item)

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

    async def parseRootPage(self, response):
        """Prefer buy_other / bldg / toushi details; skip mansion reco noise on invest hubs."""
        async for url in super().parseRootPage(response):
            path = urllib.parse.urlparse(url).path.lower()
            if any(tok in path for tok in ("/buy_other/", "/bldg/", "/building/", "/toushi/", "/buy_toushi/")):
                yield url

    def _athome_reject_residential_shumoku(self, shumoku: str) -> None:
        if not shumoku:
            return
        # 投資一覧に居住用が混在 — 利回り無しの区分/戸建/土地は次URLへ
        if "マンション" in shumoku and "一棟" not in shumoku:
            raise SkipPropertyException(
                f"Athome invest list mixed residential mansion: {shumoku}"
            )
        if (
            ("戸建" in shumoku or "テラス" in shumoku)
            and "一棟" not in shumoku
            and "収益" not in shumoku
        ):
            raise SkipPropertyException(
                f"Athome invest list mixed residential kodate: {shumoku}"
            )
        if "土地" in shumoku and "一棟" not in shumoku:
            raise SkipPropertyException(
                f"Athome invest list mixed residential tochi: {shumoku}"
            )

    def _athome_parse_yield_str(self, specs: dict, biko: str) -> str:
        yield_str = (
            specs.get("利回り", "")
            or specs.get("表面利回り", "")
            or specs.get("想定利回り", "")
        )
        if yield_str:
            return yield_str
        m = re.search(r"利回り[：:\s]*(\d+(?:\.\d+)?)\s*[％%]?", biko)
        return (m.group(1) + "%") if m else ""

    def _athome_parse_rent_str(self, specs: dict, biko: str) -> str:
        rent_str = (
            specs.get("想定賃料", "")
            or specs.get("想定年間収入", "")
            or specs.get("年間想定収入", "")
            or specs.get("満室想定年収", "")
            or specs.get("年間想定家賃収入", "")
        )
        if rent_str:
            return rent_str
        m = re.search(r"年間想定(?:家賃)?収入[：:\s]*([\d.,]+)\s*万円", biko)
        return (m.group(1) + "万円") if m else ""

    def _athome_derive_rent_from_yield(self, item) -> None:
        if not (item.grossYield and item.price and not item.annualRent):
            return
        try:
            gy = float(item.grossYield)
            if gy <= 0:
                return
            rent_val = int(float(item.price) * gy / 100.0)
            if rent_val > 0:
                item.annualRent = rent_val
                item.monthlyRent = rent_val // 12
        except (TypeError, ValueError) as err:
            logger.debug("Athome yield→rent derive skipped: %s", err)

    def _athome_fill_invest_areas(self, item, specs: dict) -> None:
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "") or specs.get("使用部分面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        item.soukosuStr = specs.get("総戸数", "")
        item.soukosu = converter.parse_number(item.soukosuStr)
        item.kaisuStr = specs.get(LABEL_KAIDATE_KAI, "")
        item.kenpeiStr = specs.get("建ぺい率", "")
        item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        item.youseki = converter.parse_ratio(item.yousekiStr)

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # 物件種目の動的判定と委譲処理 (Dynamic Dispatch)
        specs = self._get_specs_table(response)
        self._athome_reject_residential_shumoku(specs.get("物件種目", ""))

        item = super()._parsePropertyDetailPage(item, response)

        # 投資用固有情報（専用欄が無い場合は備考に利回り・想定家賃が埋まる）
        biko = specs.get("備考", "") or ""
        item.grossYield = converter.parse_ratio(self._athome_parse_yield_str(specs, biko))
        rent_str = self._athome_parse_rent_str(specs, biko)
        item.annualRent = converter.parse_price(rent_str)
        item.monthlyRent = int(item.annualRent / 12) if item.annualRent else 0
        self._athome_derive_rent_from_yield(item)
        if not item.grossYield or not item.annualRent:
            raise SkipPropertyException(
                f"Athome investment listing missing yield/rent: "
                f"{(getattr(item, 'propertyName', '') or '')[:60]}"
            )
        item.genkyo = self._parseCurrentStatus(response, specs)
        item.currentStatus = item.genkyo
        item.kouzou = (
            specs.get("建物構造", "")
            or specs.get("構造", "")
            or getattr(item, "kouzou", "")
        )
        self._athome_fill_invest_areas(item, specs)
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
        self._athome_apply_road_specs(item, specs)

        return item

import datetime
import logging
import re

from bs4 import BeautifulSoup

from package.models.smtrc import SmtrcInvestment, SmtrcKodate, SmtrcMansion, SmtrcTochi
from package.parser.baseParser import (
    InvestmentParserBase,
    KodateParserBase,
    ListItem,
    MansionParserBase,
    ParserBase,
    SkipPropertyException,
    TochiParserBase,
)
from package.utils import converter
from package.utils.property_type_detector import PropertyTypeDetector
from package.utils.selector_loader import SelectorLoader

logger = logging.getLogger(__name__)

_SMTRC_PLAYWRIGHT_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-infobars',
    '--window-position=0,0',
    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
]
_SMTRC_STEALTH_INIT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    window.chrome = { runtime: {} };
"""


class SmtrcParser(ParserBase):

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

    BASE_URL = 'https://smtrc.jp'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('smtrc', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, link_url):
        if link_url.startswith('http'):
            return link_url
        return self.BASE_URL + link_url

    async def parseNextPage(self, response: BeautifulSoup):
        # ページネーションリンクを探索
        for a in response.find_all("a"):
            text = a.get_text()
            if "次の" in text or "次へ" in text or "next" in text.lower():
                href = a.get("href")
                if href:
                    return self.getRootDestUrl(href)
        return ""

    async def parseRootPage(self, response):
        # 物件一覧ページから詳細リンクを抽出
        detail_links = set()
        for a in response.find_all("a", href=re.compile(r'/detail/CompareDetails')):
            href = a.get("href")
            if href:
                full_url = self.getRootDestUrl(href)
                import urllib.parse
                parsed = urllib.parse.urlparse(full_url)
                query = urllib.parse.parse_qs(parsed.query)
                code = query.get("propertyCode", [""])[0]
                if code:
                    normalized = f"{self.BASE_URL}/detail/CompareDetails?propertyCode={code}&pageId=D010"
                    if normalized not in detail_links:
                        detail_links.add(normalized)
                        price = self._extract_card_price(a)
                        yield ListItem(url=normalized, price=price)

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
        self._populateTraffic(item, "  ".join(traffic_lines))

        # 共通テーブルスペック
        specs = self._get_specs(response)
        item.biko = specs.get("備考", "")
        item.genkyo = specs.get("現況", "")
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引渡可能時期", "")
        item.tochikenri = specs.get("土地権利", "")
        item.torihiki = specs.get("取引態様", "")

        # 築年月（表記揺れ 建築年月 もサポート）
        item.chikunengetsuStr = specs.get("築年月") or specs.get("建築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        return item

    def _parsePriceStr(self, response: BeautifulSoup, specs=None):
        _ = specs
        price_elem = response.select_one(".price-value, .property-price")
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

    def _parseTrafficLines(self, response: BeautifulSoup):
        specs = self._get_specs(response)
        traffic_text = specs.get("交通", "")
        if not traffic_text:
            return []
        # 改行や「、」で分割
        lines = []
        for l in re.split(r'[\r\n、]+', traffic_text):
            l = l.strip()
            if l:
                lines.append(l)
        return lines

    async def _smtrc_fetch_with_playwright(self, url: str) -> bytes:
        from playwright.async_api import async_playwright

        logger.info("Playwright: fetching smtrc URL with stealth: %s...", url)
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=_SMTRC_PLAYWRIGHT_ARGS,
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
                    await context.add_init_script(_SMTRC_STEALTH_INIT)
                    page = await context.new_page()
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=2000)
                        except Exception as idle_err:
                            logger.debug("smtrc networkidle skipped: %s", idle_err)
                        await page.wait_for_timeout(500)
                        content_str = await page.content()
                    finally:
                        await page.close()
                finally:
                    await context.close()
            finally:
                await browser.close()
            content_bytes = content_str.encode('utf-8')
            logger.info("Playwright stealth fetch success: %s bytes for smtrc URL: %s", len(content_bytes), url)
            return content_bytes

    async def _getContent(self, session, url):
        """HTTPリクエストでWAF 403や微小レスポンス（<1000 bytes）が発生した場合、Playwrightステルス取得にフォールバック"""
        try:
            content = await super()._getContent(session, url)
            if len(content) >= 1000:
                return content
            logger.warning("smtrc small content (%s bytes) detected for %s, falling back to Playwright stealth...", len(content), url)
            pw_content = await self._smtrc_fetch_with_playwright(url)
            if len(pw_content) >= 1000:
                return pw_content
            # リトライ
            logger.warning("smtrc retry Playwright stealth for %s...", url)
            retried_content = await self._smtrc_fetch_with_playwright(url)
            if len(retried_content) < 1000:
                raise RuntimeError(f"smtrc Playwright fetch failed: content size too small ({len(retried_content)} bytes) for {url}")
            return retried_content
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                logger.warning("smtrc WAF 403 detected for %s, falling back to Playwright stealth...", url)
                fb_content = await self._smtrc_fetch_with_playwright(url)
                if len(fb_content) < 1000:
                    raise RuntimeError(f"smtrc Playwright fetch failed on WAF fallback: content size too small ({len(fb_content)} bytes) for {url}")
                return fb_content
            raise

class SmtrcMansionParser(SmtrcParser, MansionParserBase):
    def _parseFloor(self, response, specs=None):
        return super()._parseFloor(response, specs)

    def _parseYouseki(self, response, specs=None):
        return super()._parseYouseki(response, specs)

    def _parseSouKosu(self, response, specs=None):
        return super()._parseSouKosu(response, specs)

    def _parseSenyuMenseki(self, response, specs=None):
        return super()._parseSenyuMenseki(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseManagementFee(self, response, specs=None):
        return super()._parseManagementFee(response, specs)

    def _parseMadori(self, response, specs=None):
        return super()._parseMadori(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseKenpei(self, response, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseKouzou(self, response, specs=None):
        return super()._parseKouzou(response, specs)

    def _parseReserveFund(self, response, specs=None):
        return super()._parseReserveFund(response, specs)

    def _parseYoutoChiiki(self, response, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)

    property_type = 'mansion'

    def createEntity(self):
        return SmtrcMansion()

    @staticmethod
    def _parse_floor_spec(item, kaisu_str: str) -> None:
        if not kaisu_str:
            return
        item.floorType_kai = converter.parse_numeric(kaisu_str)
        chijo_match = re.search(r"地上\s*(\d+)階", kaisu_str)
        if chijo_match:
            item.floorType_chijo = int(chijo_match.group(1))
        chika_match = re.search(r"地下\s*(\d+)階", kaisu_str)
        if chika_match:
            item.floorType_chika = int(chika_match.group(1))

    @staticmethod
    def _parse_kouzou_spec(kouzou: str) -> str:
        if not kouzou:
            return ""
        if "鉄骨鉄筋コンクリート" in kouzou:
            return "ＳＲＣ造"
        if "鉄筋コンクリート" in kouzou:
            return "ＲＣ造"
        if "鉄骨" in kouzou:
            return "Ｓ造"
        if "木造" in kouzou:
            return "木造"
        return ""

    @staticmethod
    def _parse_kyutaishin_spec(chikunengetsu) -> int:
        if not chikunengetsu:
            return 0
        try:
            return 1 if chikunengetsu < datetime.date(1982, 1, 1) else 0
        except Exception:
            return 0

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "")
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)
            
        item.kaisuStr = (
            specs.get("所在階", "")
            or specs.get("所在階/階建", "")
            or specs.get("所在階／階建", "")
            or specs.get("階数", "")
        )
        self._parse_floor_spec(item, item.kaisuStr)

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
        item.kouzou = specs.get("構造", "")
        item.floorType_kouzou = self._parse_kouzou_spec(item.kouzou)
        item.kyutaishin = self._parse_kyutaishin_spec(item.chikunengetsu)

        item.bunjoKaisya = specs.get("分譲会社", "")
        item.sekouKaisya = specs.get("施工会社", "")
        
        return item


class SmtrcKodateParser(SmtrcParser, KodateParserBase):
    def _parseYouseki(self, response, specs=None):
        return super()._parseYouseki(response, specs)

    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseMadori(self, response, specs=None):
        return super()._parseMadori(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseKenpei(self, response, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseKouzou(self, response, specs=None):
        return super()._parseKouzou(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    def _parseSetsudou(self, response, specs=None):
        return super()._parseSetsudou(response, specs)

    def _parseYoutoChiiki(self, response, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)

    property_type = 'kodate'

    def createEntity(self):
        return SmtrcKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = (
            specs.get("建物面積", "")
            or specs.get("建物延面積", "")
            or specs.get("延床面積", "")
        )
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        item.kaisuStr = specs.get("階数", "") or specs.get("建物階数", "")
        item.madori = specs.get("間取り", "")
        item.kouzou = specs.get("構造", "") or specs.get("建物構造", "") or specs.get("構造/階建", "")
        if "/" in (item.kouzou or "") and not specs.get("構造"):
            # e.g. "木造/3階建" → structure only
            item.kouzou = item.kouzou.split("/", 1)[0].strip()

        # 都市計画関連
        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")
        
        # 建ぺい率・容積率
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        # 接道状況の抽出
        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")
        
        return item


class SmtrcTochiParser(SmtrcParser, TochiParserBase):
    def _parseYouseki(self, response, specs=None):
        return super()._parseYouseki(response, specs)

    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseMaguchi(self, response, specs=None):
        return super()._parseMaguchi(response, specs)

    def _parseChimoku(self, response, specs=None):
        return super()._parseChimoku(response, specs)

    def _parseKenpei(self, response, specs=None):
        return super()._parseKenpei(response, specs)

    def _parseSetsudou(self, response, specs=None):
        return super()._parseSetsudou(response, specs)

    def _parseYoutoChiiki(self, response, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)

    property_type = 'tochi'

    def createEntity(self):
        return SmtrcTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.kenchikuJoken = specs.get("建築条件", "") or specs.get("建築条件付土地", "")
        item.chimoku = specs.get("地目", "")
        item.youtoChiiki = specs.get("用途地域", "")
        item.kuiki = specs.get("都市計画", "")
        item.kokudoHou = specs.get("国土法届出", "") or specs.get("国土法", "")

        # 建ぺい率・容積率
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")

        return item


class SmtrcInvestmentParser(SmtrcParser, InvestmentParserBase):
    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseMonthlyRent(self, response, specs=None):
        return super()._parseMonthlyRent(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseGrossYield(self, response, specs=None):
        return super()._parseGrossYield(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseChimoku(self, response, specs=None):
        return super()._parseChimoku(response, specs)

    def _parseAnnualRent(self, response, specs=None):
        return super()._parseAnnualRent(response, specs)

    def _parseKouzou(self, response, specs=None):
        return super()._parseKouzou(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    def _parseSetsudou(self, response, specs=None):
        return super()._parseSetsudou(response, specs)

    def _parseYoutoChiiki(self, response, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)

    property_type = 'investment'

    def createEntity(self):
        return SmtrcInvestment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        self._apply_invest_yield_and_rent(item, specs)
        if not item.grossYield and not getattr(item, "annualRent", None):
            raise SkipPropertyException(
                f"Commercial/self-use listing without rent or yield on SMTRC: {getattr(item, 'pageUrl', '')}"
            )
        self._apply_invest_structure_and_counts(item, specs)
        self._apply_invest_areas_and_ratios(item, specs)

        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")
        item.chimoku = specs.get("地目", "")
        item.youtoChiiki = specs.get("用途地域", "")
        item.propertyType = PropertyTypeDetector.detect_investment_type(item.propertyName or "")
        return item

    @staticmethod
    def _apply_invest_yield_and_rent(item, specs: dict) -> None:
        gross_yield_str = (
            specs.get("利回り", "")
            or specs.get("表面利回り", "")
            or specs.get("想定利回り", "")
            or specs.get("現行利回り", "")
        )
        if gross_yield_str:
            item.grossYield = converter.parse_ratio(gross_yield_str)
        annual_rent_str = (
            specs.get("想定年間収入", "")
            or specs.get("年間想定収入", "")
            or specs.get("想定収入", "")
            or specs.get("現行年間収入", "")
        )
        if annual_rent_str:
            rent_val = converter.parse_rent(annual_rent_str)
            if rent_val:
                item.annualRent = rent_val
                item.monthlyRent = rent_val // 12

    @staticmethod
    def _apply_invest_structure_and_counts(item, specs: dict) -> None:
        item.currentStatus = specs.get("現況", "")
        item.kouzou = (
            specs.get("構造", "")
            or specs.get("建物構造", "")
            or specs.get("構造/階建", "")
        )
        if "/" in (item.kouzou or "") and not specs.get("構造"):
            # e.g. "木造/3階建" → structure only
            item.kouzou = item.kouzou.split("/", 1)[0].strip()
        item.soukosuStr = specs.get("総戸数", "") or specs.get("戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)
        item.kaisuStr = specs.get("階数", "") or specs.get("建物階数", "")

    @staticmethod
    def _apply_invest_areas_and_ratios(item, specs: dict) -> None:
        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)
        item.tatemonoMensekiStr = (
            specs.get("建物面積", "")
            or specs.get("建物延面積", "")
            or specs.get("延床面積", "")
        )
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)
        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)
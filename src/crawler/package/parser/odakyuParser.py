from decimal import Decimal
from typing import Optional
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import (
    InvestmentParserBase,
    KodateParserBase,
    ListingEndedException,
    MansionParserBase,
    ParserBase,
    SkipPropertyException,
    TochiParserBase,
)
from package.models.odakyu import OdakyuMansion, OdakyuKodate, OdakyuTochi, OdakyuInvestment
from package.utils.selector_loader import SelectorLoader
from package.utils import converter
from package.utils.property_type_detector import PropertyTypeDetector
import re
import urllib.parse

class OdakyuParser(ParserBase):

    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    BASE_URL = 'https://www.odakyu-chukai.com'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load('odakyu', self.property_type or 'mansion')

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        if linkUrl.startswith('/'):
            return self.BASE_URL + linkUrl
        return self.BASE_URL + '/' + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        # ページネーション内の「次へ」または `paging`, `pagenation-block` 領域内の a タグ
        for a in response.select(".paging a, .pager a, .pagenation-block a, .pagination a"):
            text = a.get_text()
            if "次" in text or "next" in text.lower() or ">" in text:
                href = a.get("href")
                if href:
                    return self.getRootDestUrl(href)
        return ""

    def _normalize_detail_url(self, href: str) -> Optional[str]:
        if self.property_type == 'investment':
            # 投資一覧は /mansion/detail/ID/ 等を返す。/detail/ID/ へ潰すと 404 になる (Issue #317)
            full_url = self.getRootDestUrl(href)
            m = re.search(
                r'/(?P<kind>mansion|house|kodate|land|tochi|invest)/detail/(?P<id>[A-Za-z0-9\-]+)',
                full_url,
            )
            if not m:
                return None
            return f"{self.BASE_URL}/{m.group('kind')}/detail/{m.group('id')}/"
        full_url = self.getRootDestUrl(href)
        path = urllib.parse.urlparse(full_url).path
        if not path.endswith('/'):
            path += '/'
        return f"{self.BASE_URL}{path}"

    async def parseRootPage(self, response: BeautifulSoup):
        detail_links = set()
        # 投資用と居住用でパターン分岐 (/mansion/detail/, /house/detail/, /land/detail/, /detail/)
        if self.property_type == 'investment':
            pattern = re.compile(
                r'/(?:mansion|house|kodate|land|tochi|invest)/detail/[A-Za-z0-9\-]+'
            )
        else:
            pattern = re.compile(r'/(?:mansion|house|kodate|land|tochi)/detail/[A-Za-z0-9\-]+')

        for a in response.find_all("a", href=pattern):
            href = a.get("href")
            if not href:
                continue
            normalized = self._normalize_detail_url(href)
            if normalized and normalized not in detail_links:
                detail_links.add(normalized)
                yield normalized

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # 不要なマップ・ボタンなどを取り除く
        for btn in response.find_all(class_=re.compile(r'btn|button|map', re.I)):
            btn.decompose()
            
        item = super()._parsePropertyDetailPage(item, response)

        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)

        # 住所分割
        if item.address:
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        # 交通
        traffic_lines = self._parseTrafficLines(response)
        self._populateTraffic(item, traffic_lines)

        # 共通スペック
        specs = self._get_specs(response)
        item.biko = specs.get("備考", "") or specs.get("その他", "")
        item.genkyo = self._parseCurrentStatus(response, specs)
        item.hikiwatashi = specs.get("引渡時期", "") or specs.get("引渡", "")
        item.tochikenri = self._parseRights(response, specs)
        item.torihiki = specs.get("取引態様", "")

        return self.clean_parsed_item(item)

    def _parsePropertyName(self, response: BeautifulSoup):
        title_el = response.find("h1") or response.select_one(".detailTitle h2")
        if title_el:
            return title_el.get_text().strip()
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
            parts = [p.strip() for p in re.split(r'[\r\n\t、\s]+', access_str) if p.strip()]
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
        for img in response.select(".photo img, .slideWrap img, .mainPhoto img"):
            src = img.get("src")
            if src:
                full_url = self.getRootDestUrl(src)
                if full_url not in images:
                    images.append(full_url)
        return images

class OdakyuMansionParser(OdakyuParser, MansionParserBase):
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
        raw = (
            specs.get("構造", "")
            or specs.get("建物構造", "")
            or specs.get("建物構造・階数", "")
            or super()._parseKouzou(response, specs)
        )
        # "軽量鉄骨 2階建て" / "RC造2階建て" — keep structure token.
        return str(raw or "").strip()

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
        self.ModelClass = OdakyuMansion

    def createEntity(self):
        return OdakyuMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = self._parseMadori(response, specs)
        item.senyuMensekiStr = specs.get("専有面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)

        item.kaisuStr = specs.get("所在階", "") or specs.get("階数", "")
        item.soukosuStr = specs.get("総戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.kanrihiStr = specs.get("管理費", "")
        if item.kanrihiStr:
            item.kanrihi = converter.parse_price(item.kanrihiStr)
        item.syuzenTsumitateStr = specs.get("修繕積立金", "")
        if item.syuzenTsumitateStr:
            item.syuzenTsumitate = converter.parse_price(item.syuzenTsumitateStr)

        item.kouzou = self._parseKouzou(response, specs)
        item.kanriKeitai = specs.get("管理形態", "")
        item.kanriKaisya = specs.get("管理会社", "")
        item.balconyMensekiStr = specs.get("バルコニー面積", "")
        item.saikou = specs.get("主要採光面", "")

        return item

class OdakyuKodateParser(OdakyuParser, KodateParserBase):
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
        raw = (
            specs.get("構造", "")
            or specs.get("建物構造", "")
            or specs.get("建物構造・階数", "")
            or super()._parseKouzou(response, specs)
        )
        # "軽量鉄骨 2階建て" / "RC造2階建て" — keep structure token.
        return str(raw or "").strip()

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
        self.ModelClass = OdakyuKodate

    def createEntity(self):
        return OdakyuKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        item.kouzou = self._parseKouzou(response, specs)
        item.kaisuStr = specs.get("階数", "")
        if item.kaisuStr:
            item.kaisu = converter.parse_numeric(item.kaisuStr)

        item.madori = self._parseMadori(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = self._parseSetsudou(response, specs)

        return item

class OdakyuTochiParser(OdakyuParser, TochiParserBase):
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
        self.ModelClass = OdakyuTochi

    def createEntity(self):
        return OdakyuTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.kenpeiStr = specs.get("建ぺい率", "")
        if item.kenpeiStr:
            item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.yousekiStr = specs.get("容積率", "")
        if item.yousekiStr:
            item.youseki = converter.parse_ratio(item.yousekiStr)

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kuiki = specs.get("都市計画", "")
        item.setsudou = self._parseSetsudou(response, specs)
        item.chimoku = self._parseChimoku(response, specs)
        item.kenchikuJoken = specs.get("建築条件", "")

        return item


class OdakyuInvestmentParser(OdakyuParser, InvestmentParserBase):
    # Site bug (2026-09): invest cards use href="//detail/V…//" which resolves to
    # host "detail" and all /{kind}/detail/V…/ patterns 404. Yield is only on the
    # list card (estate-info-catch). List-card parse is the production path until
    # detail pages are restored. kouzou is rarely on the card → not required here.
    EXPECTED_SPEC_FIELDS_BY_TYPE = {
        **getattr(ParserBase, "EXPECTED_SPEC_FIELDS_BY_TYPE", {}),
        "investment": ["price", "address", "grossYield", "annualRent"],
    }

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

    def __init__(self, params=None):
        super().__init__(params)
        self.ModelClass = OdakyuInvestment

    def createEntity(self):
        return OdakyuInvestment()

    @staticmethod
    def _focus_id_from_url(url: str) -> str:
        if not url:
            return ""
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        vals = qs.get("focus") or []
        if not vals:
            return ""
        return (vals[0] or "").strip()

    def _estate_block_has_yield(self, block) -> bool:
        catch = block.select_one(".estate-info-catch")
        text = (catch.get_text(" ", strip=True) if catch else "") + " " + block.get_text(" ", strip=True)[:200]
        return any(k in text for k in ("利回", "オーナーチェンジ", "収益", "賃貸中"))

    async def parseRootPage(self, response: BeautifulSoup):
        """Prefer invest list cards with yield; detail //detail/V* links are broken on-site."""
        detail_links = set()
        for block in response.select(".estate-block"):
            cb = block.select_one('input[name="ids[]"]')
            if cb is None:
                continue
            vid = (cb.get("value") or "").strip()
            if not vid:
                continue
            if not self._estate_block_has_yield(block):
                continue
            # V* / B* invest codes — list-card focus URL (detail pages 404).
            focus_url = f"{self.BASE_URL}/invest/list/?focus={urllib.parse.quote(vid)}"
            if focus_url not in detail_links:
                detail_links.add(focus_url)
                yield focus_url
        # Fallback: typed detail links (often residential mixed into invest list).
        pattern = re.compile(
            r"/(?:mansion|house|kodate|land|tochi|invest)/detail/[A-Za-z0-9\-]+"
        )
        for a in response.find_all("a", href=pattern):
            href = a.get("href")
            if not href:
                continue
            normalized = self._normalize_detail_url(href)
            if normalized and normalized not in detail_links:
                detail_links.add(normalized)
                yield normalized

    def _parse_invest_list_card(self, item, block, focus_id: str = ""):
        name_el = block.select_one(".estate-block-name a, .estate-block-name")
        item.propertyName = name_el.get_text(" ", strip=True) if name_el else ""
        price_el = block.select_one(".estate-price-item")
        price_str = price_el.get_text(" ", strip=True) if price_el else ""
        item.priceStr = price_str
        item.price = converter.parse_price(price_str) or 0
        addr_dd = None
        for dl in block.select(".estate-info-list dl.address"):
            dt = dl.find("dt")
            if dt and "所在地" in dt.get_text():
                addr_dd = dl.find("dd")
                break
        item.address = addr_dd.get_text(" ", strip=True) if addr_dd else ""
        if item.address:
            item.address1, item.address2, item.address3 = self._split_address(item.address)
        catch = block.select_one(".estate-info-catch")
        catch_text = catch.get_text(" ", strip=True) if catch else ""
        gy_m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*％", catch_text)
        if not gy_m:
            gy_m = re.search(r"利回り[：:\s]*約?([0-9]+(?:\.[0-9]+)?)", catch_text)
        if gy_m:
            item.grossYield = converter.parse_ratio(gy_m.group(1) + "%")
        # Derive annual rent when listing publishes yield but not rent.
        if item.grossYield and item.price and not getattr(item, "annualRent", None):
            try:
                gy = float(item.grossYield)
                if gy > 0:
                    rent_val = int(float(item.price) * gy / 100.0)
                    if rent_val > 0:
                        item.annualRent = rent_val
                        item.monthlyRent = rent_val // 12
            except (TypeError, ValueError):
                pass
        item.propertyType = PropertyTypeDetector.detect_investment_type(
            (item.propertyName or "") + " " + catch_text
        )
        if focus_id:
            item.pageUrl = f"{self.BASE_URL}/invest/list/?focus={urllib.parse.quote(focus_id)}"
        if not item.grossYield or not getattr(item, "annualRent", None):
            raise SkipPropertyException(
                f"Odakyu invest list card missing yield/rent: {item.propertyName[:60]}"
            )
        return item

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        focus = self._focus_id_from_url(getattr(item, "pageUrl", "") or getattr(self, "_last_url", ""))
        # List-card path: invest/list HTML with estate-block(+optional focus).
        blocks = response.select(".estate-block")
        if blocks:
            target = None
            if focus:
                for block in blocks:
                    cb = block.select_one('input[name="ids[]"]')
                    if cb and (cb.get("value") or "").strip() == focus:
                        target = block
                        break
                if target is None:
                    raise ListingEndedException(
                        f"Odakyu invest focus id not found on list page: {focus}"
                    )
            else:
                for block in blocks:
                    if self._estate_block_has_yield(block):
                        target = block
                        break
            if target is not None:
                return self._parse_invest_list_card(item, target, focus_id=focus)

        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 表面利回り
        gross_yield_str = specs.get("利回り", "") or specs.get("表面利回り", "")
        if gross_yield_str:
            item.grossYield = converter.parse_ratio(gross_yield_str)

        # 想定年間収入
        annual_rent_str = specs.get("想定年間収入", "") or specs.get("年間想定収入", "")
        if annual_rent_str:
            rent_val = converter.parse_price(annual_rent_str)
            if rent_val:
                item.annualRent = rent_val
                item.monthlyRent = rent_val // 12

        if item.grossYield and item.price and not getattr(item, "annualRent", None):
            try:
                gy = float(item.grossYield)
                if gy > 0:
                    rent_val = int(float(item.price) * gy / 100.0)
                    if rent_val > 0:
                        item.annualRent = rent_val
                        item.monthlyRent = rent_val // 12
            except (TypeError, ValueError):
                pass

        item.genkyo = self._parseCurrentStatus(response, specs)
        item.currentStatus = item.genkyo
        item.kouzou = (
            self._parseKouzou(response, specs)
            or specs.get("建物構造", "")
            or specs.get("構造", "")
        )

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        # 総戸数
        item.soukosuStr = specs.get("総戸数", "")
        if item.soukosuStr:
            item.soukosu = converter.parse_numeric(item.soukosuStr)

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

        if not item.grossYield or not getattr(item, "annualRent", None):
            raise SkipPropertyException(
                f"Odakyu investment listing missing yield/rent: {(item.propertyName or '')[:60]}"
            )

        return item
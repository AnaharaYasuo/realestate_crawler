import asyncio
import logging
import re
from typing import Optional
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup

from package.models.kenbiya import (
    KenbiyaInvestmentApartment,
    KenbiyaInvestmentBuilding,
    KenbiyaMansion,
    KenbiyaKodate,
    KenbiyaTochi,
)
from package.parser.baseParser import (
    ParserBase,
    ListItem,
    InvestmentParserBase,
    MansionParserBase,
    KodateParserBase,
    TochiParserBase,
    ListingEndedException,
    ServerBusyException,
    LoadPropertyPageException,
    ServerDownException,
    RateLimitedException,
)
from package.utils import converter

# SonarCloud S1192: Centralized string literal constants
INFO_GUIDE = "情報の見方"
INQUIRY_TEXT = "問い合わせる"
STRUCTURE_FLOOR = "建物構造/階数"
STRUCTURE_TEXT = "建物構造"
KENPEI_YOUSEKI_SLASH = "建ぺい/容積率"
KENPEI_YOUSEKI_FULL = "建ぺい率/容積率"
SOUKOSU_REGEX = r"総戸数(\d+)戸"
RATE_LIMITED_KENBIYA_PREFIX = "Rate limited (429) on Kenbiya: "


class KenbiyaParserBase(ParserBase):
    """
    健美家 (Kenbiya) 全種別共通基底パーサー
    共通HTTP通信、429対策ヘッダー、dl > dt / dd パースロジックを集約
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    ]
    _ua_counter = 0

    @classmethod
    def _get_next_user_agent(cls) -> str:
        ua = KenbiyaParserBase.USER_AGENTS[
            KenbiyaParserBase._ua_counter % len(KenbiyaParserBase.USER_AGENTS)
        ]
        KenbiyaParserBase._ua_counter += 1
        return ua

    def getCharset(self):
        return "utf-8"

    async def _handle_response(
        self,
        response: aiohttp.ClientResponse,
        url: str,
        attempt: int,
        max_timeouts: int,
    ) -> Optional[bytes]:
        status = response.status
        if status == 200:
            self.consecutive_timeouts = 0
            return await response.read()
        if status in (404, 410):
            raise ListingEndedException(
                f"Property page returned HTTP status {status}: {url}"
            )
        if status in (500, 502, 503, 504):
            raise ServerBusyException(
                f"Property page returned HTTP status {status}: {url}"
            )
        if status == 429:
            backoff = min(30, 2 ** (attempt + 1))
            logging.warning(
                f"{RATE_LIMITED_KENBIYA_PREFIX}{url}. Backing off {backoff}s"
            )
            if attempt == max_timeouts - 1:
                raise RateLimitedException(f"{RATE_LIMITED_KENBIYA_PREFIX}{url}")
            await asyncio.sleep(backoff)
            return None
        raise LoadPropertyPageException(f"Failed to fetch {url} with status {status}")

    async def _getContent(self, session: aiohttp.ClientSession, url: str) -> bytes:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        max_timeouts = getattr(self, "MAX_CONSECUTIVE_TIMEOUTS", 3)
        last_status = None
        for attempt in range(max_timeouts):
            headers["User-Agent"] = self._get_next_user_agent()
            try:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    last_status = response.status
                    content = await self._handle_response(
                        response, url, attempt, max_timeouts
                    )
                    if content is not None:
                        return content
            except (
                RateLimitedException,
                ListingEndedException,
                ServerBusyException,
                LoadPropertyPageException,
                ServerDownException,
            ):
                raise
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                self.consecutive_timeouts = getattr(self, "consecutive_timeouts", 0) + 1
                if self.consecutive_timeouts >= max_timeouts:
                    raise ServerDownException(
                        f"Kenbiya server unresponsive after {self.consecutive_timeouts} consecutive timeouts: {e}"
                    )
                await asyncio.sleep(1)
        if last_status == 429:
            raise RateLimitedException(f"{RATE_LIMITED_KENBIYA_PREFIX}{url}")
        raise LoadPropertyPageException(f"Exceeded max retries for {url}")

    BASE_URL = "https://www.kenbiya.com"

    async def parsePropertyListPage(self, response: BeautifulSoup):
        detail_links = set()
        for a in response.find_all("a", href=re.compile(r"/pp\d+/.*?/re_\w+/")):
            href = a.get("href")
            if not href:
                continue
            full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            if full_url not in detail_links:
                detail_links.add(full_url)
                price = self._extract_card_price(a)
                yield ListItem(url=full_url, price=price)

    def _find_next_by_text(self, response: BeautifulSoup) -> str:
        for a in response.find_all("a"):
            if a is None:
                continue
            text = a.get_text(strip=True)
            if ("次へ" in text or "次のページ" in text or text == ">") and a.has_attr(
                "href"
            ):
                href = str(a["href"])
                return urljoin(self.BASE_URL, href)
        return ""

    async def parseNextPage(self, response: BeautifulSoup):
        # ページネーション: li.next a, a[rel="next"], または「次へ」リンク
        next_tag = response.select_one('li.next a, a[rel="next"], a.next')
        if next_tag is not None:
            href = next_tag.get("href")
            if href:
                return urljoin(self.BASE_URL, str(href))
        return self._find_next_by_text(response)

    async def parseRootPage(self, response: BeautifulSoup):
        async for item in self.parsePropertyListPage(response):
            yield item

    @staticmethod
    def _clean_spec_value(text: str) -> str:
        """項目の見方・用語解説などのヘルプ文を除去または除外してスペック値を返す"""
        if not text:
            return ""
        clean = text.strip()
        # 1. ヘルプリンク「情報の見方を表示」「見方を表示」などの付加テキストを除去
        clean = re.sub(
            r"[\(（]?\s*(?:情報の見方を表示|見方を表示|マークを表示)\s*[\)）]?",
            "",
            clean,
        ).strip()
        # 2. それでも「〜を表示。」「〜を表示」など説明文そのものである場合は空文字を返す（スペック値ではない）
        if re.search(r"(?:を表示[。]?|マークを表示)$", clean):
            return ""
        return clean

    def _parse_dl_specs(self, response: BeautifulSoup, specs: dict) -> None:
        for dl in response.find_all("dl"):
            parent_classes = " ".join(dl.get("class", []) or [])
            if any(
                k in parent_classes
                for k in ["guide", "help", "glossary", "explanation"]
            ):
                continue
            for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
                key = dt.get_text(strip=True)
                val = dd.get_text(" ", strip=True)
                cleaned_val = self._clean_spec_value(val)
                if key and cleaned_val:
                    specs[key] = cleaned_val

    def _parse_tr_specs(self, response: BeautifulSoup, specs: dict) -> None:
        for tr in response.find_all("tr"):
            parent = tr.find_parent("table")
            if parent:
                parent_classes = " ".join(parent.get("class", []) or [])
                if any(
                    k in parent_classes
                    for k in ["guide", "help", "glossary", "explanation"]
                ):
                    continue
            th, td = tr.find("th"), tr.find("td")
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(" ", strip=True)
                cleaned_val = self._clean_spec_value(val)
                if key and cleaned_val:
                    specs[key] = cleaned_val

    def _get_specs(self, response: BeautifulSoup) -> dict:
        """dl > dt / dd または table から key-value スペック辞書を構築"""
        specs = {}
        if not response:
            return specs
        self._parse_dl_specs(response, specs)
        self._parse_tr_specs(response, specs)
        return specs

    # 共通パースメソッド群
    def _parsePrice(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("価格", "")
        return converter.parse_price(raw)

    def _parsePriceStr(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("価格", "")

    def _parseAddress(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("住所", "") or specs.get("所在地", "")
        for noise in ["地図", "周辺環境", "周辺地図"]:
            raw = raw.replace(noise, "").strip()
        return raw

    def _parsePropertyName(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        name = specs.get("物件名", "") or specs.get("名称", "")
        if not name:
            title = response.find("title")
            if title:
                title_text = title.get_text(strip=True)
                name = (
                    title_text.split("｜")[0].strip()
                    if "｜" in title_text
                    else title_text
                )
        return name

    def _parseTransport1(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("交通", "")

    def _parseRights(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("土地権利", "")

    def _parseSetsudou(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        status = specs.get("現況", "") or specs.get("入居状況", "")
        for noise in ["入居状況を問い合わせる", INFO_GUIDE]:
            status = status.replace(noise, "").strip()
        return status

    def _parseGenkyo(self, response: BeautifulSoup, specs=None):
        return self._parseCurrentStatus(response, specs)

    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("引渡", "")

    def _parseChimoku(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("地目", "")

    def _parseGrossYield(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = (
            specs.get("満室時利回り", "")
            or specs.get("表面利回り", "")
            or specs.get("利回り", "")
        )
        for noise in ["利回りの詳細を問い合わせる", INFO_GUIDE]:
            raw = raw.replace(noise, "").strip()
        return converter.parse_ratio(raw)

    def _parseAnnualRent(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        rent_str = (
            specs.get("満室時年収/月収", "")
            or specs.get("満室時年収", "")
            or specs.get("想定年収", "")
        )
        if "/" in rent_str:
            annual_part = rent_str.split("/")[0].strip()
        else:
            annual_part = rent_str
        for noise in [INFO_GUIDE, INQUIRY_TEXT]:
            annual_part = annual_part.replace(noise, "").strip()
        return converter.parse_price(annual_part)

    def _parseMonthlyRent(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        rent_str = specs.get("満室時年収/月収", "")
        if "/" in rent_str:
            monthly_part = rent_str.split("/")[1].strip()
            for noise in [INFO_GUIDE, INQUIRY_TEXT]:
                monthly_part = monthly_part.replace(noise, "").strip()
            val = converter.parse_price(monthly_part)
            if val:
                return val
        annual = self._parseAnnualRent(response, specs)
        return int(annual / 12) if annual else None

    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("築年月", "")
        return converter.parse_chikunengetsu(raw)

    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        kouzou = (
            specs.get(STRUCTURE_FLOOR, "")
            or specs.get(STRUCTURE_TEXT, "")
            or specs.get("構造", "")
        )
        if "総戸数" in kouzou:
            kouzou = kouzou.split("総戸数")[0]
        return kouzou.strip()

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("土地面積", "")
        return converter.parse_menseki(raw)

    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("建物面積", "") or specs.get("延床面積", "")
        return converter.parse_menseki(raw)

    def _parseKenpei(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = (
            specs.get(KENPEI_YOUSEKI_SLASH, "")
            or specs.get(KENPEI_YOUSEKI_FULL, "")
            or specs.get("建ぺい率", "")
        )
        if "/" in raw:
            parts = raw.split("/")
            return converter.parse_ratio(parts[0])
        return converter.parse_ratio(raw)

    def _parseYouseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = (
            specs.get(KENPEI_YOUSEKI_SLASH, "")
            or specs.get(KENPEI_YOUSEKI_FULL, "")
            or specs.get("容積率", "")
        )
        if "/" in raw:
            parts = raw.split("/")
            return converter.parse_ratio(parts[1])
        return converter.parse_ratio(raw)

    def _parse_traffic(self, item, traffic_text: str):
        """健美家の交通情報テキストから沿線・駅・徒歩分数を抽出"""
        matches = re.finditer(
            r"([^\s]+?(?:線|ライン|ライナー|鉄道|メトロ))\s+([^\s]+?駅)\s*(?:徒歩)?(\d+)分?",
            traffic_text,
        )
        idx = 1
        for m in matches:
            railway = m.group(1).strip()
            station = m.group(2).strip()
            if station.endswith("駅"):
                station = station[:-1].strip()
            walk = int(m.group(3))

            if idx == 1:
                item.railway1 = railway
                item.station1 = station
                item.railwayWalkMinute1 = walk
                item.walkMinutes1 = walk
            elif idx == 2:
                item.railway2 = railway
                item.station2 = station
                item.railwayWalkMinute2 = walk
                item.walkMinutes2 = walk
            elif idx == 3:
                item.railway3 = railway
                item.station3 = station
                item.railwayWalkMinute3 = walk
                item.walkMinutes3 = walk
            idx += 1

    def _populate_common_fields(self, item, response: BeautifulSoup, specs=None):
        """全種別共通プロパティの自動バインド（コード重複削減）"""
        specs = specs or self._get_specs(response)
        item.price = self._parsePrice(response, specs)
        item.priceStr = self._parsePriceStr(response, specs)
        item.address = self._parseAddress(response, specs)
        item.propertyName = self._parsePropertyName(response, specs)
        item.tochikenri = self._parseRights(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.currentStatus = self._parseCurrentStatus(response, specs)
        item.genkyo = item.currentStatus
        item.hikiwatashi = self._parseHikiwatashi(response, specs)
        item.chimoku = self._parseChimoku(response, specs)
        item.grossYield = self._parseGrossYield(response, specs)
        item.annualRent = self._parseAnnualRent(response, specs)

        traffic_text = specs.get("交通", "")
        if traffic_text:
            item.traffic = traffic_text
            self._parse_traffic(item, traffic_text)
        return specs

    def _populate_building_specs(self, item, response: BeautifulSoup, specs):
        """一棟アパート・一棟ビル共通スペックのバインド"""
        item.monthlyRent = self._parseMonthlyRent(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")

        raw_kouzou = specs.get(STRUCTURE_TEXT, "") or specs.get(STRUCTURE_FLOOR, "")
        item.kouzou = self._parseKouzou(response, specs)
        soukosu_match = re.search(SOUKOSU_REGEX, raw_kouzou)
        if soukosu_match:
            item.soukosu = int(soukosu_match.group(1))
            item.soukosuStr = f"{item.soukosu}戸"

        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.tochiMensekiStr = specs.get("土地面積", "")
        item.tatemonoMenseki = self._parseTatemonoMenseki(response, specs)
        item.tatemonoMensekiStr = specs.get("建物面積", "")

        item.kenpei = self._parseKenpei(response, specs)
        item.youseki = self._parseYouseki(response, specs)
        kenpei_youseki = specs.get(KENPEI_YOUSEKI_SLASH, "") or specs.get(
            KENPEI_YOUSEKI_FULL, ""
        )
        if "/" in kenpei_youseki:
            parts = kenpei_youseki.split("/")
            item.kenpeiStr = parts[0].strip()
            item.yousekiStr = parts[1].strip()

        item.madori = specs.get("間取り", "")


class KenbiyaInvestmentApartmentParser(KenbiyaParserBase, InvestmentParserBase):
    """
    健美家 (Kenbiya) 投資用一棟アパート向けパーサー (/pp2/)
    """

    property_type = "investmentapartment"

    def createEntity(self) -> KenbiyaInvestmentApartment:
        return KenbiyaInvestmentApartment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._populate_common_fields(item, response)
        self._populate_building_specs(item, response, specs)
        item.propertyType = "Apartment"
        return item


class KenbiyaInvestmentBuildingParser(KenbiyaParserBase, InvestmentParserBase):
    """
    健美家 (Kenbiya) 投資用一棟マンション・ビル向けパーサー (/pp3/, /pp4/)
    """

    property_type = "investmentbuilding"

    def createEntity(self) -> KenbiyaInvestmentBuilding:
        return KenbiyaInvestmentBuilding()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._populate_common_fields(item, response)
        self._populate_building_specs(item, response, specs)
        item.propertyType = "Building"
        return item


class KenbiyaMansionParser(KenbiyaParserBase, MansionParserBase):
    """
    健美家 (Kenbiya) 区分マンション向けパーサー (/pp1/)
    """

    property_type = "mansion"

    def createEntity(self) -> KenbiyaMansion:
        return KenbiyaMansion()

    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        val = specs.get("間取り", "")
        if not val:
            return ""
        for token in val.split():
            clean_tok = "".join(c for c in token if c.isalnum())
            if clean_tok in ("ワンルーム", "1R") or any(
                clean_tok.endswith(suffix)
                for suffix in ("R", "K", "DK", "LDK", "SLDK", "SK")
            ):
                return clean_tok
        return val.split()[0]

    def _parseSenyuMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("専有面積", "")
        if not val:
            return None
        val_main = val.split("（")[0].split("(")[0]
        return converter.parse_menseki(val_main.replace("m²", "㎡"))

    def _parseBalconyMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("専有面積", "") or specs.get("バルコニー面積", "")
        if "バルコニー" in val:
            b_part = val.split("バルコニー")[1].split("）")[0].split(")")[0]
            return converter.parse_menseki(b_part.replace("m²", "㎡"))
        return None

    def _parseFloor(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = (
            specs.get(STRUCTURE_FLOOR, "")
            or specs.get("階数", "")
            or specs.get("所在階", "")
        )
        if "/" in val:
            val = val.split("/")[0]
        digits = "".join(c for c in val if c.isdigit())
        return int(digits) if digits else None

    def _parseTotalFloor(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = (
            specs.get(STRUCTURE_FLOOR, "")
            or specs.get("階数", "")
            or specs.get("総階数", "")
        )
        if "/" in val:
            part = val.split("/")[1].split("階")[0]
            digits = "".join(c for c in part if c.isdigit())
            if digits:
                return int(digits)
        if "地上" in val:
            part = val.split("地上")[1].split("階")[0]
            digits = "".join(c for c in part if c.isdigit())
            if digits:
                return int(digits)
        return None

    def _parseSouKosu(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get(STRUCTURE_FLOOR, "") or specs.get("総戸数", "")
        m = re.search(SOUKOSU_REGEX, val)
        return int(m.group(1)) if m else None

    def _parseDirection(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        val = (
            specs.get("間取り", "")
            or specs.get("向き", "")
            or specs.get("主要採光面", "")
        )
        m = re.search(r"(南東|南西|北東|北西|東|西|南|北)向き", val)
        if m:
            return m.group(1)
        m2 = re.search(r"(南東|南西|北東|北西|東|西|南|北)", val)
        return m2.group(1) if m2 else ""

    def _parseManagementFee(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("管理費/修繕積立", "") or specs.get("管理費", "")
        if "/" in val:
            part = val.split("/")[0].strip()
            return converter.parse_yen(part)
        return converter.parse_yen(val) if val else None

    _parseMaintenanceFee = _parseManagementFee

    def _parseReserveFund(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = (
            specs.get("管理費/修繕積立", "")
            or specs.get("修繕積立金", "")
            or specs.get("修繕積立", "")
        )
        if "/" in val:
            part = val.split("/")[1].strip()
            return converter.parse_yen(part)
        return converter.parse_yen(val) if val else None

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._populate_common_fields(item, response)
        item.monthlyRent = self._parseMonthlyRent(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")

        item.kouzou = self._parseKouzou(response, specs)
        item.madori = self._parseMadori(response, specs)
        item.senyuMenseki = self._parseSenyuMenseki(response, specs)
        item.senyuMensekiStr = specs.get("専有面積", "")
        item.balconyMenseki = self._parseBalconyMenseki(response, specs)

        item.floor = self._parseFloor(response, specs)
        if item.floor:
            item.floorStr = f"{item.floor}階"
        item.totalFloor = self._parseTotalFloor(response, specs)
        if item.totalFloor:
            item.totalFloorStr = f"{item.totalFloor}階建"

        item.soukosu = self._parseSouKosu(response, specs)
        if item.soukosu:
            item.soukosuStr = f"{item.soukosu}戸"

        item.direction = self._parseDirection(response, specs)
        item.kanrihi = self._parseMaintenanceFee(response, specs)
        item.shuzenTsumitate = self._parseReserveFund(response, specs)

        item.kenpei = self._parseKenpei(response, specs)
        item.youseki = self._parseYouseki(response, specs)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.propertyType = "Mansion"

        return item


class KenbiyaKodateParser(KenbiyaParserBase, KodateParserBase):
    """
    健美家 (Kenbiya) 戸建賃貸向けパーサー (/pp8/)
    """

    property_type = "kodate"

    def createEntity(self) -> KenbiyaKodate:
        return KenbiyaKodate()

    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "")

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._populate_common_fields(item, response)
        item.monthlyRent = self._parseMonthlyRent(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")

        item.kouzou = self._parseKouzou(response, specs)
        item.madori = self._parseMadori(response, specs)
        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.tochiMensekiStr = specs.get("土地面積", "")
        item.tatemonoMenseki = self._parseTatemonoMenseki(response, specs)
        item.tatemonoMensekiStr = specs.get("建物面積", "")

        item.kenpei = self._parseKenpei(response, specs)
        item.youseki = self._parseYouseki(response, specs)
        item.propertyType = "Kodate"

        return item


class KenbiyaTochiParser(KenbiyaParserBase, TochiParserBase):
    """
    健美家 (Kenbiya) 投資用土地・事業用土地向けパーサー (/pp5/)
    """

    property_type = "tochi"

    def createEntity(self) -> KenbiyaTochi:
        return KenbiyaTochi()

    def _parseMaguchi(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("間口", "") or specs.get("接道状況", "")
        if "間口" in val:
            part = val.split("間口")[1].split("m")[0]
            return converter.parse_menseki(part)
        return None

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._populate_common_fields(item, response)
        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.tochiMensekiStr = specs.get("土地面積", "")

        item.kenpei = self._parseKenpei(response, specs)
        item.youseki = self._parseYouseki(response, specs)
        item.propertyType = "Tochi"

        return item

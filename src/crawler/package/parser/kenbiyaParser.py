# -*- coding: utf-8 -*-
import asyncio
import datetime
from decimal import Decimal
import logging
import re
import aiohttp
from bs4 import BeautifulSoup
from django.db import models

from package.models.kenbiya import KenbiyaInvestmentApartment
from package.parser.baseParser import (
    InvestmentParserBase,
    ListingEndedException,
    ServerBusyException,
    LoadPropertyPageException,
    ServerDownException,
)
from package.utils import converter


class KenbiyaInvestmentApartmentParser(InvestmentParserBase):
    """
    健美家 (Kenbiya) 投資用一棟アパート・マンション向けパーサー
    """
    property_type = 'investmentapartment'

    def getCharset(self):
        return "utf-8"

    def createEntity(self) -> models.Model:
        return KenbiyaInvestmentApartment()

    async def _getContent(self, session: aiohttp.ClientSession, url: str) -> bytes:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        max_timeouts = getattr(self, 'MAX_CONSECUTIVE_TIMEOUTS', 3)
        for attempt in range(max_timeouts):
            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status == 200:
                        self.consecutive_timeouts = 0
                        return await response.read()
                    elif response.status in (404, 410):
                        raise ListingEndedException(f"Property page returned HTTP status {response.status}: {url}")
                    elif response.status in (500, 502, 503, 504):
                        raise ServerBusyException(f"Property page returned HTTP status {response.status}: {url}")
                    elif response.status == 429:
                        logging.warning(f"Kenbiya 429 rate limit hit for URL: {url}")
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                    else:
                        raise LoadPropertyPageException(f"HTTP Status {response.status}: {url}")
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                cur_timeouts = getattr(self, 'consecutive_timeouts', 0) + 1
                self.consecutive_timeouts = cur_timeouts
                if cur_timeouts >= max_timeouts:
                    raise ServerDownException(f"Target server is down or timing out repeatedly ({cur_timeouts} times)") from e
                if attempt == self.MAX_CONSECUTIVE_TIMEOUTS - 1:
                    raise LoadPropertyPageException(f"Timeout after {attempt + 1} attempts for URL: {url}") from e
                await asyncio.sleep(1 * (attempt + 1))
        return b""

    def _get_specs(self, response: BeautifulSoup):
        """健美家物件ページの dl > dt / dd 定義リストからスペック辞書を構築"""
        specs = {}
        if not response:
            return specs
        for dl in response.find_all("dl"):
            for dt in dl.find_all("dt"):
                dd = dt.find_next_sibling("dd")
                if dd:
                    key = dt.get_text(strip=True)
                    val = dd.get_text(strip=True)
                    if key and key not in specs:
                        specs[key] = val
        return specs

    def _parsePrice(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        specs = specs or self._get_specs(response)
        price_str = specs.get("価格", "")
        return converter.parse_price(price_str)

    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("価格", "")

    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        addr = specs.get("住所", "") or specs.get("所在地", "")
        if addr.endswith("地図"):
            addr = addr[:-2].strip()
        return addr

    def _parsePropertyName(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        name = specs.get("物件名", "")
        if not name and response:
            h1 = response.find(["h1", "h2"])
            if h1:
                name = h1.get_text(strip=True)
        return name

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
        for noise in ["入居状況を問い合わせる", "情報の見方"]:
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
        raw = specs.get("満室時利回り", "") or specs.get("表面利回り", "") or specs.get("利回り", "")
        for noise in ["利回りの詳細を問い合わせる", "情報の見方"]:
            raw = raw.replace(noise, "").strip()
        return converter.parse_ratio(raw)

    def _parseAnnualRent(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        rent_str = specs.get("満室時年収/月収", "") or specs.get("満室時年収", "") or specs.get("想定年収", "")
        if "/" in rent_str:
            annual_part = rent_str.split("/")[0].strip()
        else:
            annual_part = rent_str
        for noise in ["情報の見方", "問い合わせる"]:
            annual_part = annual_part.replace(noise, "").strip()
        return converter.parse_price(annual_part)

    def _parseMonthlyRent(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        rent_str = specs.get("満室時年収/月収", "")
        if "/" in rent_str:
            monthly_part = rent_str.split("/")[1].strip()
            for noise in ["情報の見方", "問い合わせる"]:
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
        kouzou = specs.get("建物構造", "") or specs.get("構造", "")
        # "木造2階建 総戸数4戸" -> "木造2階建"
        m = re.match(r'^(.*?)(?:\s+総戸数\d+戸)?$', kouzou)
        return m.group(1).strip() if m else kouzou

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("土地面積", "")
        return converter.parse_menseki(raw)

    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("建物面積", "") or specs.get("延床面積", "")
        return converter.parse_menseki(raw)

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._get_specs(response)

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
        item.monthlyRent = self._parseMonthlyRent(response, specs)

        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")

        raw_kouzou = specs.get("建物構造", "")
        item.kouzou = self._parseKouzou(response, specs)
        soukosu_match = re.search(r'総戸数(\d+)戸', raw_kouzou)
        if soukosu_match:
            item.soukosu = int(soukosu_match.group(1))
            item.soukosuStr = f"{item.soukosu}戸"

        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.tochiMensekiStr = specs.get("土地面積", "")
        item.tatemonoMenseki = self._parseTatemonoMenseki(response, specs)
        item.tatemonoMensekiStr = specs.get("建物面積", "")

        kenpei_youseki = specs.get("建ぺい/容積率", "") or specs.get("建ぺい率/容積率", "")
        if "/" in kenpei_youseki:
            parts = kenpei_youseki.split("/")
            item.kenpei = converter.parse_ratio(parts[0])
            item.kenpeiStr = parts[0].strip()
            item.youseki = converter.parse_ratio(parts[1])
            item.yousekiStr = parts[1].strip()

        item.madori = specs.get("間取り", "")
        item.propertyType = "Apartment"

        # 交通情報の解析
        traffic_text = specs.get("交通", "")
        if traffic_text:
            item.traffic = traffic_text
            self._parse_traffic(item, traffic_text)

        return item

    def _parse_traffic(self, item, traffic_text: str):
        """健美家の交通情報テキストから沿線・駅・徒歩分数を抽出"""
        # 例: 東急世田谷線 宮の坂駅 徒歩12分小田急小田原線 経堂駅 徒歩13分
        matches = re.finditer(r'([^\s]+?(?:線|ライン|ライナー|鉄道|メトロ))\s+([^\s]+?駅)\s*(?:徒歩)?(\d+)分?', traffic_text)
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

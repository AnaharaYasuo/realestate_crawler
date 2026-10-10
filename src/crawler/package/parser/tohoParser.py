import logging
import re
from bs4 import BeautifulSoup
from decimal import Decimal

from package.parser.baseParser import (
    ParserBase,
    ListItem,
    MansionParserBase,
    KodateParserBase,
    TochiParserBase,
    ListingEndedException
)
from package.utils import converter
from package.models.mid_brokers import TohoMansion, TohoKodate, TohoTochi

logger = logging.getLogger(__name__)

def check_toho_listing_ended(response: BeautifulSoup, page_url: str = ""):
    title_text = response.title.get_text() if response.title else ""
    body_text = response.body.get_text() if response.body else ""
    all_text = f"{title_text} {body_text}"
    if any(msg in all_text for msg in ["成約済", "お探しの物件は見つかりませんでした", "掲載を終了"]):
        raise ListingEndedException(f"Toho listing ended: {page_url}")


class TohoBaseParser(ParserBase):
    BASE_URL = "https://www.toho-house.media"

    def getCharset(self):
        return "utf-8"

    async def parsePropertyListPage(self, response: BeautifulSoup):
        detail_links = set()
        for a in response.find_all("a", href=re.compile(r'/detail/[a-zA-Z0-9_-]+')):
            href = a.get("href")
            if not href:
                continue
            full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            if full_url not in detail_links:
                detail_links.add(full_url)
                price = self._extract_card_price(a)
                yield ListItem(url=full_url, price=price)

    def _get_specs(self, response: BeautifulSoup) -> dict[str, str]:
        cached = getattr(response, "_cached_specs", None)
        if cached is not None:
            return cached

        specs = {}
        for dl in response.find_all("dl"):
            dt = dl.find("dt")
            dd = dl.find("dd")
            if dt and dd:
                key = dt.get_text(strip=True)
                val = dd.get_text(" ", strip=True)
                specs[key] = val

        response._cached_specs = specs
        return specs

    def _parsePropertyName(self, response: BeautifulSoup, specs=None) -> str:
        h1 = response.find("h1")
        if h1:
            return h1.get_text(strip=True)
        if response.title:
            return response.title.get_text(strip=True).split("【")[0].strip()
        return ""

    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        if specs.get("価格"):
            return specs["価格"]
        el = response.find(class_=re.compile(r'price', re.I))
        if el is not None:
            return converter.extract_price_text(el.get_text(strip=True))
        return ""

    def _parsePrice(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        p_str = self._parsePriceStr(response, specs)
        return converter.parse_price(p_str) if p_str else None

    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("所在地", "")

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("交通", "")

    def _parseKenpei(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("建ぺい率", "") or specs.get("建蔽率", "")

    def _parseYouseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("容積率", "")

    def _parseRights(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利形態", "") or specs.get("土地権利", "")

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("引渡時期", "") or specs.get("引渡", "")

    def _parseGenkyo(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None) -> str:
        return self._parseGenkyo(response, specs)

    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("接道状況", "") or specs.get("接道", "")

    def _parseMaguchi(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("間口", "") or specs.get("接道状況", "")
        return converter.parse_menseki(val) if val else None


SPEC_KEY_STRUCTURE_FLOORS = "構造・階建て"


class TohoMansionParser(TohoBaseParser, MansionParserBase):
    def createEntity(self):
        return TohoMansion()

    def _parseSenyuMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("専有面積", "")
        return converter.parse_menseki(s) if s else None

    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "")

    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("築年月", "")
        return converter.parse_chikunengetsu(s) if s else None

    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get(SPEC_KEY_STRUCTURE_FLOORS, "") or specs.get("構造", "")

    def _parseFloor(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        raw = specs.get("所在階", "") or specs.get(SPEC_KEY_STRUCTURE_FLOORS, "")
        if "階" in raw:
            idx = raw.find("階")
            start = idx
            while start > 0 and raw[start - 1].isdigit():
                start -= 1
            if start < idx:
                return raw[start:idx + 1]
        return ""

    def _parseSouKosu(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("総戸数", "")
        m = re.search(r'(\d+)', s)
        return int(m.group(1)) if m else None

    def _parseManagementFee(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("管理費", "")
        return converter.parse_price(s) if s else None

    def _parseReserveFund(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("修繕積立金", "")
        return converter.parse_price(s) if s else None

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        check_toho_listing_ended(response, getattr(item, 'pageUrl', ''))
        specs = self._get_specs(response)
        item.propertyName = self._parsePropertyName(response, specs)
        item.priceStr = self._parsePriceStr(response, specs)
        item.price = self._parsePrice(response, specs) or 0
        item.address = self._parseAddress(response, specs)
        item.traffic = self._parseTransport1(response, specs)
        item.senyuMenseki = self._parseSenyuMenseki(response, specs)
        item.madori = self._parseMadori(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.kouzou = self._parseKouzou(response, specs)
        item.kaisu = self._parseFloor(response, specs)
        item.kanrihi = self._parseManagementFee(response, specs)
        item.syuzenTsumitate = self._parseReserveFund(response, specs)
        return item


class TohoKodateParser(TohoBaseParser, KodateParserBase):
    def createEntity(self):
        return TohoKodate()

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("土地面積", "")
        return converter.parse_menseki(s) if s else None

    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("建物面積", "")
        return converter.parse_menseki(s) if s else None

    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "")

    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("築年月", "")
        return converter.parse_chikunengetsu(s) if s else None

    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get(SPEC_KEY_STRUCTURE_FLOORS, "") or specs.get("構造", "")

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        check_toho_listing_ended(response, getattr(item, 'pageUrl', ''))
        specs = self._get_specs(response)
        item.propertyName = self._parsePropertyName(response, specs)
        item.priceStr = self._parsePriceStr(response, specs)
        item.price = self._parsePrice(response, specs) or 0
        item.address = self._parseAddress(response, specs)
        item.traffic = self._parseTransport1(response, specs)
        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.tatemonoMenseki = self._parseTatemonoMenseki(response, specs)
        item.madori = self._parseMadori(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.kouzou = self._parseKouzou(response, specs)
        return item


class TohoTochiParser(TohoBaseParser, TochiParserBase):
    def createEntity(self):
        return TohoTochi()

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("土地面積", "")
        return converter.parse_menseki(s) if s else None

    def _parseChimoku(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("地目", "")

    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("接道状況", "") or specs.get("接道", "")

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        check_toho_listing_ended(response, getattr(item, 'pageUrl', ''))
        specs = self._get_specs(response)
        item.propertyName = self._parsePropertyName(response, specs)
        item.priceStr = self._parsePriceStr(response, specs)
        item.price = self._parsePrice(response, specs) or 0
        item.address = self._parseAddress(response, specs)
        item.traffic = self._parseTransport1(response, specs)
        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kenpei = self._parseKenpei(response, specs)
        item.youseki = self._parseYouseki(response, specs)
        return item

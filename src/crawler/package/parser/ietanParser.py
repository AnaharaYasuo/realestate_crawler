import logging
import re
from bs4 import BeautifulSoup
from decimal import Decimal

from package.parser.baseParser import (
    ParserBase,
    MansionParserBase,
    KodateParserBase,
    TochiParserBase,
    ListingEndedException
)
from package.utils import converter
from package.models.mid_brokers import IetanMansion, IetanKodate, IetanTochi

logger = logging.getLogger(__name__)

def check_ietan_listing_ended(response: BeautifulSoup, page_url: str = ""):
    title_text = response.title.get_text() if response.title else ""
    body_text = response.body.get_text() if response.body else ""
    all_text = f"{title_text} {body_text}"
    if any(msg in all_text for msg in ["お探しの物件は見つかりませんでした", "掲載を終了いたしました", "掲載を終了しました", "指定された物件は掲載を終了"]):
        raise ListingEndedException(f"Ietan listing ended: {page_url}")


class IetanBaseParser(ParserBase):
    def getCharset(self):
        return "utf-8"

    def _get_specs(self, response: BeautifulSoup) -> dict[str, str]:
        cached = getattr(response, "_cached_specs", None)
        if cached is not None:
            return cached

        specs = {}
        section = response.find("section", class_="estateProfile")
        if section:
            for dt in section.find_all("dt"):
                dd = dt.find_next_sibling("dd")
                if dt and dd:
                    key = dt.get_text(strip=True).replace("物件情報の見方", "").strip()
                    val = dd.get_text(" ", strip=True)
                    specs[key] = val

        response._cached_specs = specs
        return specs

    def _parsePropertyName(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        if specs.get("物件名"):
            return specs["物件名"]
        h1 = response.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return ""

    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        el = response.find(class_=re.compile(r'price', re.I))
        if el is not None:
            return converter.extract_price_text(el.get_text(strip=True))
        return ""

    def _parsePrice(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        p_str = self._parsePriceStr(response, specs)
        return converter.parse_price(p_str) if p_str else None

    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        addr = specs.get("所在地", "")
        # Remove "周辺地図を見る"
        return addr.replace("周辺地図を見る", "").strip()

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("交通", "")

    def _parseKenpei(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseYouseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("容積率", "")

    def _parseRights(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("土地権利", "") or specs.get("権利", "")

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("引渡し", "") or specs.get("引渡時期", "") or specs.get("引渡", "")

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
        val = specs.get("間口", "") or specs.get("接道状況", "") or specs.get("接道", "")
        return converter.parse_menseki(val) if val else None


SPEC_KEY_STRUCTURE_FLOORS = "構造・階建"


class IetanMansionParser(IetanBaseParser, MansionParserBase):
    def createEntity(self):
        return IetanMansion()

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
        raw = specs.get(SPEC_KEY_STRUCTURE_FLOORS, "")
        if raw:
            parts = raw.split()
            return parts[0] if parts else raw
        return ""

    def _parseFloor(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        raw = specs.get(SPEC_KEY_STRUCTURE_FLOORS, "")
        if "階部分" in raw:
            idx = raw.find("階部分")
            start = idx
            while start > 0 and raw[start - 1].isdigit():
                start -= 1
            if start < idx:
                return raw[start:idx + len("階部分")]
        return ""

    def _parseSouKosu(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("総戸数", "")
        m = re.search(r'(\d+)', s)
        return int(m.group(1)) if m else None

    def _parseManagementFee(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("管理費", "")
        return converter.parse_yen(s) if s else None

    def _parseReserveFund(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("修繕積立金", "")
        return converter.parse_yen(s) if s else None

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        check_ietan_listing_ended(response, getattr(item, 'pageUrl', ''))
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


class IetanKodateParser(IetanBaseParser, KodateParserBase):
    def createEntity(self):
        return IetanKodate()

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
        return specs.get(SPEC_KEY_STRUCTURE_FLOORS, "") or specs.get("建物構造", "")

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        check_ietan_listing_ended(response, getattr(item, 'pageUrl', ''))
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


class IetanTochiParser(IetanBaseParser, TochiParserBase):
    def createEntity(self):
        return IetanTochi()

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
        check_ietan_listing_ended(response, getattr(item, 'pageUrl', ''))
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

import logging
import re
from bs4 import BeautifulSoup
from decimal import Decimal

from package.parser.baseParser import (
    ParserBase,
    KodateParserBase,
    TochiParserBase,
    ListingEndedException
)
from package.utils import converter
from package.models.mid_brokers import AdCastKodate, AdCastTochi

logger = logging.getLogger(__name__)

def check_adcast_listing_ended(response: BeautifulSoup, page_url: str = ""):
    title_text = response.title.get_text() if response.title else ""
    body_text = response.body.get_text() if response.body else ""
    all_text = f"{title_text} {body_text}"
    if any(msg in all_text for msg in ["成約済", "掲載終了", "お探しの物件は見つかりませんでした"]):
        raise ListingEndedException(f"AdCast listing ended: {page_url}")


class AdCastBaseParser(ParserBase):
    def getCharset(self):
        return "utf-8"

    def _get_specs(self, response: BeautifulSoup) -> dict[str, str]:
        cached = getattr(response, "_cached_specs", None)
        if cached is not None:
            return cached

        specs = {}
        for tr in response.find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(" ", strip=True)
                specs[key] = val

        response._cached_specs = specs
        return specs

    def _parsePropertyName(self, response: BeautifulSoup, specs=None) -> str:
        h1 = response.find("h1")
        if h1:
            return h1.get_text(strip=True)
        if response.title:
            return response.title.get_text(strip=True).split("｜")[0].strip()
        return ""

    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        el = response.find(class_=re.compile(r'price', re.I))
        if el:
            m = re.search(r'([\d,]+万円|[\d,.]+億円)', el.get_text(strip=True))
            if m:
                return m.group(1)
        specs = specs or self._get_specs(response)
        return specs.get("価格", "") or specs.get("販売価格", "")

    def _parsePrice(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        p_str = self._parsePriceStr(response, specs)
        return converter.parse_price(p_str) if p_str else None

    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        addr = specs.get("所在地", "")
        return addr.replace("地図で表示", "").strip()

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("交通", "")

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("土地面積", "")
        return converter.parse_menseki(s) if s else None

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
        return specs.get("現況", "")

    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None) -> str:
        return self._parseGenkyo(response, specs)

    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("接道状況", "") or specs.get("接道", "")

    def _parseMaguchi(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("間口", "") or specs.get("接道状況", "")
        return converter.parse_menseki(val) if val else None


class AdCastKodateParser(AdCastBaseParser, KodateParserBase):
    def createEntity(self):
        return AdCastKodate()

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
        return specs.get("構造", "") or specs.get("建物構造", "")

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        check_adcast_listing_ended(response, getattr(item, 'pageUrl', ''))
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
        item.kenpei = self._parseKenpei(response, specs)
        item.youseki = self._parseYouseki(response, specs)
        return item


class AdCastTochiParser(AdCastBaseParser, TochiParserBase):
    def createEntity(self):
        return AdCastTochi()

    def _parseChimoku(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("地目", "")

    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("接道状況", "") or specs.get("接道", "")

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        check_adcast_listing_ended(response, getattr(item, 'pageUrl', ''))
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

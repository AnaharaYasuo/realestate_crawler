import logging
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from decimal import Decimal

from package.parser.baseParser import (
    ParserBase,
    KodateParserBase,
    ListItem,
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
    BASE_URL = "https://www.ad-cast.info"

    def getCharset(self):
        return "utf-8"

    async def parsePropertyListPage(self, response: BeautifulSoup):
        detail_links = set()
        for a in response.find_all("a", href=re.compile(r'(/sch/detail\.php\?|/detail/[a-zA-Z0-9_-]+)')):
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
            if ("次へ" in text or "次のページ" in text or text == ">") and a.has_attr("href"):
                href = str(a["href"])
                return urljoin(self.BASE_URL, href)
        return ""

    async def parseNextPage(self, response: BeautifulSoup):
        next_tag = response.select_one('li.next a, a[rel="next"], a.next, .pager a.next')
        if next_tag is not None:
            href = next_tag.get("href")
            if href:
                return urljoin(self.BASE_URL, str(href))
        return self._find_next_by_text(response)

    async def parseRootPage(self, response: BeautifulSoup):
        async for item in self.parsePropertyListPage(response):
            yield item

    def _get_specs(self, response: BeautifulSoup) -> dict[str, str]:
        cached = getattr(response, "_cached_specs", None)
        if cached is not None:
            return cached

        specs = {}
        for tr in response.find_all("tr"):
            ths = tr.find_all("th")
            tds = tr.find_all("td")
            for th, td in zip(ths, tds):
                key = th.get_text(strip=True)
                val = td.get_text(" ", strip=True)
                specs[key] = val
        for dl in response.find_all("dl"):
            dt = dl.find("dt")
            dd = dl.find("dd")
            if dt and dd:
                key = dt.get_text(strip=True)
                val = dd.get_text(" ", strip=True)
                if key not in specs:
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
        specs = specs or self._get_specs(response)
        spec_price = specs.get("価格", "") or specs.get("販売価格", "") or specs.get("物件価格", "")
        if spec_price:
            return spec_price
        for el in response.find_all(class_=re.compile(r'price', re.I)):
            if not self._is_valid_selling_price_element(el):
                continue
            txt = el.get_text(strip=True)
            price_text = converter.extract_price_text(txt)
            if price_text:
                return price_text
        return ""

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
        item.tochiMensekiStr = specs.get("土地面積", "")
        item.tatemonoMenseki = self._parseTatemonoMenseki(response, specs)
        item.tatemonoMensekiStr = specs.get("建物面積", "")
        item.madori = self._parseMadori(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")
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
        item.tochiMensekiStr = specs.get("土地面積", "")
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.kenpei = self._parseKenpei(response, specs)
        item.youseki = self._parseYouseki(response, specs)
        return item

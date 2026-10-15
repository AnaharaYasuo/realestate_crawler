from decimal import Decimal
import re
import urllib.parse
from bs4 import BeautifulSoup
from package.api.differential import ListItem
from package.models.reguide import ReguideInvestment
from package.parser.investmentParser import InvestmentParser
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

DIGIT_REGEX = re.compile(r"(\d+)")


class ReguideInvestmentParser(InvestmentParser):
    property_type = "investment"
    BASE_URL = "https://re-guide.jp"

    def __init__(self, params=None):
        super().__init__()
        self.selectors = SelectorLoader.load("reguide", self.property_type)

    @staticmethod
    def _is_current_page_li(li) -> bool:
        return not li.find("a") and bool(re.match(r"^\[\d+\]$", li.get_text(strip=True)))

    @staticmethod
    def _extract_page_link_href(li) -> str:
        a_tag = li.find("a")
        if not a_tag or not a_tag.get("href"):
            return ""
        href = a_tag["href"]
        decoded_href = urllib.parse.unquote(href)
        if "pager[p]=" in decoded_href and re.match(r"^\[\d+\]$", a_tag.get_text(strip=True)):
            return href
        return ""

    def _is_valid_reguide_url(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        return (
            parsed.scheme in ("http", "https")
            and (parsed.netloc == "re-guide.jp" or parsed.netloc.endswith(".re-guide.jp"))
        )

    async def parseNextPage(self, response: BeautifulSoup) -> str:
        """
        一覧ページから次ページの絶対URLを抽出する。
        ul.pager 内の現在ページ [N] の直後にあるリンクを取得。
        """
        pager_ul = response.select_one("ul.pager")
        if not pager_ul:
            return ""

        lis = pager_ul.find_all("li")
        for i, li in enumerate(lis):
            if not self._is_current_page_li(li):
                continue
            if i + 1 < len(lis):
                href = self._extract_page_link_href(lis[i + 1])
                if href:
                    base_url = getattr(response, "url", None) or f"{self.BASE_URL}/investment/list/"
                    candidate_url = urllib.parse.urljoin(base_url, href)
                    if self._is_valid_reguide_url(candidate_url):
                        return candidate_url
            break
        return ""

    async def parseRootPage(self, response: BeautifulSoup):
        """
        一覧ページのSoupから詳細ページのListItemを順次yieldする。
        """
        html_content = str(response)
        for url in self.extract_detail_urls(html_content):
            yield ListItem(url=url)

    def createEntity(self):
        """
        Entity factory for RE-Guide investment property.
        """
        return ReguideInvestment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._get_specs(response)
        item.propertyName = self._parsePropertyName(response, specs)
        item.price = self._parsePrice(response, specs)
        item.priceStr = self._parsePriceStr(response, specs)
        item.address = self._parseAddress(response, specs)
        item.traffic = self._parseTransport1(response, specs)
        item.grossYield = self._parseGrossYield(response, specs)
        item.annualRent = self._parseAnnualRent(response, specs)
        item.monthlyRent = self._parseMonthlyRent(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")
        item.kouzou = self._parseKouzou(response, specs)
        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.tochiMensekiStr = specs.get("土地面積", "")
        item.tatemonoMenseki = self._parseTatemonoMenseki(response, specs)
        item.tatemonoMensekiStr = specs.get("建物面積", "")
        item.genkyo = self._parseGenkyo(response, specs)
        item.currentStatus = self._parseCurrentStatus(response, specs)
        item.tochikenri = self._parseRights(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.chimoku = self._parseChimoku(response, specs)
        item.hikiwatashi = self._parseHikiwatashi(response, specs)
        return item

    def getCharset(self):
        return "euc-jp"

    @staticmethod
    def _extract_row_specs(tr, specs: dict) -> None:
        ths = tr.find_all("th")
        tds = tr.find_all("td")
        if len(ths) == len(tds) and len(ths) > 0:
            for th, td in zip(ths, tds):
                key = th.get_text(strip=True)
                val = td.get_text(" ", strip=True)
                if key and val and key not in specs:
                    specs[key] = val
        elif len(ths) == 1 and len(tds) >= 1:
            key = ths[0].get_text(strip=True)
            val = tds[0].get_text(" ", strip=True)
            if key and val and key not in specs:
                specs[key] = val

    def _get_specs(self, response: BeautifulSoup) -> dict:
        """
        詳細ページのスペックテーブル (th / td) を辞書化する。
        同一行に複数の th/td ペアが存在するテーブルレイアウトに対応。
        """
        specs = {}
        for table in response.find_all("table"):
            for tr in table.find_all("tr"):
                self._extract_row_specs(tr, specs)
        return specs

    def _parsePropertyName(self, response: BeautifulSoup, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        if target_specs.get("物件名"):
            return target_specs["物件名"]
        h1 = response.find("h1")
        if h1 is not None:
            # Remove badge tags like <span id="new_icon">
            for span in h1.find_all(["span", "img"]):
                span.decompose()
            text = h1.get_text(strip=True)
            if text:
                return text
        return super()._parsePropertyName(response, specs)

    def _parsePrice(self, response: BeautifulSoup, specs=None):
        price_str = self._parsePriceStr(response, specs)
        if not price_str:
            return None
        return converter.parse_price(price_str)

    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        price_str = target_specs.get("価格(税込)", "") or target_specs.get("価格", "")
        if price_str:
            return price_str
        price_el = response.select_one(".price")
        if price_el:
            return price_el.get_text(strip=True)
        return ""

    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        return target_specs.get("所在地", "") or super()._parseAddress(response, specs)

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        return target_specs.get("交通", "") or super()._parseTransport1(response, specs)

    def _parseGrossYield(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        yield_str = (
            target_specs.get("満室想定表面利回り", "")
            or target_specs.get("利回り", "")
            or target_specs.get("想定表面利回り", "")
        )
        if not yield_str:
            return None
        match = re.search(r"([\d\.]+)", yield_str)
        if match:
            try:
                return Decimal(match.group(1)).quantize(Decimal("0.01"))
            except Exception:
                return None
        return None

    def _parseAnnualRent(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        rent_str = target_specs.get("満室想定年間収入", "") or target_specs.get("年間予定賃料収入", "")
        if not rent_str:
            return None
        if "万" in rent_str and "円" in rent_str:
            val = converter._extract_man_yen_part(rent_str.replace(" ", "").split("万"))
            if val is not None:
                return val
        return converter.parse_price(rent_str)

    def _parseMonthlyRent(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        rent_str = target_specs.get("月額賃料", "") or target_specs.get("月額予定賃料", "") or target_specs.get("賃料", "")
        if not rent_str:
            return None
        return converter.parse_price(rent_str)

    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        chiku_str = target_specs.get("築年月", "")
        if not chiku_str:
            return None
        return converter.parse_chikunengetsu(chiku_str)

    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        target_specs = specs or self._get_specs(response)
        return target_specs.get("構造", "") or target_specs.get("建物構造", "")

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        tochi_str = target_specs.get("土地面積", "")
        if not tochi_str:
            return None
        return converter.parse_menseki(tochi_str)

    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        tatemono_str = target_specs.get("建物面積", "")
        if not tatemono_str:
            return None
        return converter.parse_menseki(tatemono_str)

    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        return target_specs.get("現況", "") or super()._parseCurrentStatus(response, specs)

    def _parseGenkyo(self, response: BeautifulSoup, specs=None):
        return self._parseCurrentStatus(response, specs)

    def _parseRights(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        return target_specs.get("土地権利", "") or target_specs.get("権利", "") or super()._parseRights(response, specs)

    def _parseSetsudou(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        return target_specs.get("接道状況", "") or target_specs.get("接道", "") or super()._parseSetsudou(response, specs)

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        return target_specs.get("用途地域", "") or super()._parseYoutoChiiki(response, specs)

    def _parseChimoku(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        return target_specs.get("地目", "") or super()._parseChimoku(response, specs)

    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None):
        target_specs = specs or self._get_specs(response)
        return target_specs.get("引渡時期", "") or target_specs.get("引渡し", "") or super()._parseHikiwatashi(response, specs)

    def extract_detail_urls(self, html_content: str) -> list[str]:
        """
        一覧ページのHTMLから詳細ページの絶対URL一覧を抽出する。
        同一ドメイン (re-guide.jp) のみ許可。
        """
        soup = BeautifulSoup(html_content, "html.parser")
        urls = set()
        container = soup.select_one("ul#result_list") or soup
        for a_tag in container.find_all("a", href=True):
            href = a_tag["href"]
            abs_url = urllib.parse.urljoin(self.BASE_URL, href)
            parsed = urllib.parse.urlparse(abs_url)
            if (
                parsed.scheme in ("http", "https")
                and (parsed.netloc == "re-guide.jp" or parsed.netloc.endswith(".re-guide.jp"))
                and re.match(r"^/investment/\d+/?", parsed.path)
            ):
                urls.add(abs_url)
        return sorted(urls)

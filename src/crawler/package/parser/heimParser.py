import re
import logging
import urllib.parse
from bs4 import BeautifulSoup

from package.models.heim import HeimMansion, HeimKodate, HeimTochi
from package.parser.baseParser import (
    KodateParserBase,
    MansionParserBase,
    ParserBase,
    SkipPropertyException,
    TochiParserBase,
)
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

class HeimParser(ParserBase):

    def _parseCurrentStatus(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    def _parseRights(self, response, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    BASE_URL = 'https://www.sumu-heim.jp'
    property_type = ""

    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('heim', self.property_type)

    async def getResponseBs(self, session, url, charset=None) -> BeautifulSoup:
        return await super().getResponseBs(session, url, charset)


    def getCharset(self):
        return "utf-8"

    def _parsePrice(self, response: BeautifulSoup):
        return super()._parsePrice(response)

    def _parseAddress(self, response: BeautifulSoup):
        return super()._parseAddress(response)


    def getRootDestUrl(self, link_url):
        if link_url.startswith('http'):
            return link_url
        return self.BASE_URL + link_url

    async def parseNextPage(self, response: BeautifulSoup):
        next_a = response.select_one(".pagination .next a, .pager .next a, a.next, li.next a")
        if next_a:
            href = next_a.get("href")
            if href:
                return self.getRootDestUrl(href)
        return ""

    async def parseRootPage(self, response: BeautifulSoup):
        detail_links = set()
        base_domain = "https://www.tokyo816.jp"

        for a in response.find_all("a"):
            href = a.get("href")
            if not href:
                continue
            # Prefer lot-level plan_detail pages (have 間取り/面積); property index is a hub.
            if "/plan_detail/" in href or "/bunjou/property/" in href or "detail.php" in href:
                full_url = urllib.parse.urljoin(base_domain, href)
                parsed = urllib.parse.urlparse(full_url)
                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if normalized.endswith("/"):
                    normalized = normalized[:-1]
                if normalized in detail_links or normalized.endswith("/bunjou"):
                    continue
                # Defer property hubs without plan_detail — smoke expands them.
                detail_links.add(normalized)
                logging.info(f"[Heim] Match detail link: {normalized}")
                yield normalized



    def _get_specs(self, response: BeautifulSoup) -> dict:
        specs = {}
        self._heim_specs_from_b_table(response, specs)
        self._heim_specs_from_table_rows(response, specs)
        self._heim_specs_from_plan_tbl(response, specs)
        self._heim_specs_from_outline_cards(response, specs)
        self._heim_normalize_spec_aliases(specs)
        self._heim_specs_from_dl(response, specs)
        return specs

    @staticmethod
    def _heim_specs_from_b_table(response: BeautifulSoup, specs: dict) -> None:
        # Legacy: すむハイムのスペック表コンテナ .b_table .tr
        table = response.select_one(".b_table")
        if not table:
            return
        for row in table.select(".tr"):
            th = row.select_one(".th")
            td = row.select_one(".td")
            if th and td:
                specs[th.get_text().strip()] = td.get_text().strip()

    @staticmethod
    def _heim_is_header_only_row(k: str, v: str) -> bool:
        header_keys = ("種別", "区画", "販売価格", "価格", "土地面積", "建物面積", "間取り", "間取")
        header_vals = ("区画", "販売価格", "土地面積", "建物面積", "間取り", "間取", "")
        return k in header_keys and v in header_vals

    def _heim_specs_from_table_rows(self, response: BeautifulSoup, specs: dict) -> None:
        # plan_detail / standard tables (th+td or td+td label/value pairs)
        for tr in response.select("table tr"):
            if self._heim_ingest_th_td_row(tr, specs):
                continue
            self._heim_ingest_cell_pair_row(tr, specs)

    @staticmethod
    def _heim_ingest_th_td_row(tr, specs: dict) -> bool:
        th, td = tr.find("th"), tr.find("td")
        if not (th and td):
            return False
        k = th.get_text(" ", strip=True)
        if k and k not in specs:
            specs[k] = td.get_text(" ", strip=True)
        return True

    def _heim_ingest_cell_pair_row(self, tr, specs: dict) -> None:
        cells = tr.find_all(["th", "td"])
        if len(cells) < 2:
            return
        k = cells[0].get_text(" ", strip=True)
        v = cells[1].get_text(" ", strip=True)
        # Skip header-only rows like 種別|区画|販売価格|...
        if self._heim_is_header_only_row(k, v):
            return
        if k and k not in specs and v:
            specs[k] = v

    _HEIM_LABEL_RE = re.compile(
        r"^(?:種別|区画|販売価格|価格|土地面積|建物面積|間取り|間取)\s+([^\r\n]+)$"
    )


    def _heim_specs_from_plan_tbl(self, response: BeautifulSoup, specs: dict) -> None:
        # planTblWrap hub tables: each cell is "ラベル 値"
        for tr in response.select("table.planTblWrap tr, .planTblWrap tr"):
            row_specs = {}
            for cell in tr.find_all(["th", "td"]):
                txt = " ".join(cell.get_text(" ", strip=True).split())
                m = self._HEIM_LABEL_RE.match(txt)
                if m:
                    row_specs[m.group(1)] = m.group(2).strip()
            if not row_specs.get("種別"):
                continue
            # Prefer first complete data row
            if "価格" not in specs and "販売価格" not in specs:
                specs.update(row_specs)
            else:
                for k, v in row_specs.items():
                    specs.setdefault(k, v)

    def _heim_specs_from_outline_cards(self, response: BeautifulSoup, specs: dict) -> None:
        # plan_detail outline cards: "価格 6,295 万円" style cells (not classic th/td).
        for cell in response.select(
            ".outline__tbl th, .outline__tbl td, .outline__tbl li, .outline__tbl div, .planDetail *"
        ):
            txt = " ".join(cell.get_text(" ", strip=True).split())
            if len(txt) > 80:
                continue
            m = self._HEIM_LABEL_RE.match(txt)
            if not m:
                continue
            key, val = m.group(1), m.group(2).strip()
            if key and val and key not in specs:
                specs[key] = val

    @staticmethod
    def _heim_normalize_spec_aliases(specs: dict) -> None:
        if "価格" not in specs and specs.get("販売価格"):
            specs["価格"] = specs["販売価格"]
        if "間取り" not in specs and specs.get("間取"):
            specs["間取り"] = specs["間取"]

    @staticmethod
    def _heim_specs_from_dl(response: BeautifulSoup, specs: dict) -> None:
        for dl in response.select("dl"):
            for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
                k = dt.get_text(" ", strip=True)
                if k and k not in specs:
                    specs[k] = dd.get_text(" ", strip=True)


    def _split_address(self, address):
        return super()._split_address(address)

    def _parsePropertyName(self, response: BeautifulSoup, specs=None) -> str:
        title_el = response.select_one("div.title_header > h2, h1, .property__header h1, h2.title")
        if title_el:
            return title_el.get_text().strip()
        specs = specs or self._get_specs(response)
        return specs.get("物件名", "") or specs.get("名称", "") or super()._parsePropertyName(response, specs)

    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        for el in response.select("div.price_box > h5 > span, td.item, .price, .money, td, span, div"):
            txt = el.get_text().strip()
            if "万円" in txt and len(txt) < 40:
                p_val = converter.parse_price(txt)
                if p_val is not None and p_val > 0:
                    return txt
        return specs.get("価格", "") or specs.get("販売価格", "") or specs.get("物件価格", "")

    def _parsePrice(self, response: BeautifulSoup, specs=None):
        price_str = self._parsePriceStr(response, specs)
        if price_str:
            p_val = converter.parse_price(price_str)
            if p_val is not None and p_val > 0:
                return p_val
        return 0

    def _heim_address_from_heading(self, response: BeautifulSoup) -> str:
        h1 = response.select_one("h1, div.title_header h2, h2")
        if not h1:
            return ""
        h1t = h1.get_text(" ", strip=True)
        m = re.search(
            r"((?:東京都|神奈川県|埼玉県|千葉県|山梨県)?[^\s\d]{2,20}?[市区町村][^\s\d]{0,20})",
            h1t,
        )
        return m.group(1).strip() if m else ""

    def _heim_address_from_page_text(self, response: BeautifulSoup) -> str:
        full_text = response.get_text()
        match = re.search(
            r'(東京都[^\s\d]+?[市区町村][^\s\d<>\)]+)',
            full_text,
        )
        return match.group(1).strip() if match else ""


    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        addr_p = response.select_one("p.place, .address")
        if addr_p:
            for a in addr_p.find_all("a"):
                a.decompose()
            return addr_p.get_text().strip()

        addr = specs.get("所在地", "") or specs.get("住所", "") or specs.get("分譲地住所", "")
        if addr or not response:
            return addr
        addr = self._heim_address_from_heading(response)
        if not addr:
            addr = self._heim_address_from_page_text(response)
        return addr

    def _heim_traffic_from_page_text(self, response: BeautifulSoup) -> str:
        full_text = response.get_text()
        patterns = (
            r'([^\n<>\s"\'「」]{2,15}?(?:線|本線|東武|西武|小田急|京王|JR|地下鉄)[^\n<>\s"\'「」]{0,10}?駅[^\n<>\s"\'「」]{0,15}?(?:徒歩|直通|バス)[^\n<>\s"\'「」]{1,10}?\d+分)',
            r'(「?[^\n<>\s"\'「」]{2,10}?駅」?[^\n<>\s"\'「」]{0,15}?(?:徒歩|直通|バス)[^\n<>\s"\'「」]{1,10}?\d+分)',
            r'(「?[^\n<>\s"\'「」]{2,10}?駅」?)',
        )
        for pat in patterns:
            match = re.search(pat, full_text)
            if match:
                return match.group(1).strip()
        return ""

    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        traffic_str = specs.get("交通", "") or specs.get("アクセス", "")
        if traffic_str or not response:
            return traffic_str
        return self._heim_traffic_from_page_text(response)

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)
        
        item.propertyName = self._parsePropertyName(response, specs)
        item.priceStr = self._parsePriceStr(response, specs)
        item.price = self._parsePrice(response, specs)
        item.address = self._parseAddress(response, specs)

        if item.address:
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        traffic_str = self._parseTransport1(response, specs)
        if traffic_str:
            traffic_lines = re.split(r'\s{2,}', traffic_str)
            if len(traffic_lines) <= 1:
                traffic_lines = traffic_str.split(" ")
            self._populateTraffic(item, [t.strip() for t in traffic_lines if t.strip()])

    def _parseBiko(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("備考", "")

    def _parseGenkyo(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("現況", "")

    def _parseTochikenri(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("土地権利", "")

    def _parseTorihiki(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("取引態様", "")

    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("引渡時期", "") or specs.get("引渡時期/現況", "")

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)
        
        item.propertyName = self._parsePropertyName(response, specs)
        item.priceStr = self._parsePriceStr(response, specs)
        item.price = self._parsePrice(response, specs)
        item.address = self._parseAddress(response, specs)

        if item.address:
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        traffic_str = self._parseTransport1(response, specs)
        if traffic_str:
            traffic_lines = re.split(r'\s{2,}', traffic_str)
            if len(traffic_lines) <= 1:
                traffic_lines = traffic_str.split(" ")
            self._populateTraffic(item, [t.strip() for t in traffic_lines if t.strip()])

        item.biko = self._parseBiko(response, specs)
        item.genkyo = self._parseGenkyo(response, specs)
        item.tochikenri = self._parseTochikenri(response, specs)
        item.torihiki = self._parseTorihiki(response, specs)
        item.hikiwatashi = self._parseHikiwatashi(response, specs)

        return item


class HeimMansionParser(HeimParser, MansionParserBase):
    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseYoutoChiiki(self, response, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


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
        return HeimMansion()

    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "")

    def _parseSenyuMensekiStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("専有面積", "") or specs.get("建物面積", "")

    def _parseSenyuMenseki(self, response: BeautifulSoup, specs=None):
        val_str = self._parseSenyuMensekiStr(response, specs)
        return converter.parse_menseki(val_str) if val_str else None

    def _parseKaisuStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("階建/所在階", "") or specs.get("階数", "")

    def _parseChikunengetsuStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("築年月", "") or specs.get("完成年月", "") or specs.get("完成時期", "")

    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        val_str = self._parseChikunengetsuStr(response, specs)
        return converter.parse_chikunengetsu(val_str) if val_str else None

    def _parseBalconyMensekiStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("バルコニー面積", "")

    def _parseBalconyMenseki(self, response: BeautifulSoup, specs=None):
        val_str = self._parseBalconyMensekiStr(response, specs)
        return converter.parse_menseki(val_str) if val_str else None

    def _parseSoukosuStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("総戸数", "")


    def _parseKanrihiStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("管理費", "")

    def _parseKanrihi(self, response: BeautifulSoup, specs=None):
        val_str = self._parseKanrihiStr(response, specs)
        return converter.parse_rent(val_str) if val_str else None

    def _parseSyuzenTsumitateStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("修繕積立金", "")

    def _parseSyuzenTsumitate(self, response: BeautifulSoup, specs=None):
        val_str = self._parseSyuzenTsumitateStr(response, specs)
        return converter.parse_rent(val_str) if val_str else None

    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("建物構造", "") or specs.get("構造", "")

    def _parseKanriKeitai(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("管理形態", "")

    def _parseKanriKaisya(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("管理会社", "")

    def _parseSaikou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("主要採光面", "") or specs.get("向き", "")

    def _parseSaikouKadobeya(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("角部屋", "")

    def _heim_apply_tatemono_as_senyu(self, item, specs: dict) -> None:
        # 建売 pages publish 建物面積 instead of 専有面積
        if item.senyuMenseki:
            return
        tatemono_str = specs.get("建物面積", "")
        if not tatemono_str:
            return
        item.senyuMensekiStr = tatemono_str
        item.senyuMenseki = converter.parse_menseki(tatemono_str)

    def _heim_parse_floor_types(self, item) -> None:
        if not item.kaisuStr:
            return
        m = re.search(r'(\d+)階部分', item.kaisuStr)
        if m:
            item.floorType_kai = int(m.group(1))
        m = re.search(r'地上(\d+)階', item.kaisuStr)
        if m:
            item.floorType_chijo = int(m.group(1))
        m = re.search(r'地下(\d+)階', item.kaisuStr)
        if m:
            item.floorType_chika = int(m.group(1))

    def _heim_require_senyu_and_madori(self, item) -> None:
        if not getattr(item, "senyuMenseki", None) or not str(
            getattr(item, "madori", "") or ""
        ).strip():
            raise SkipPropertyException(
                "Heim mansion/建売 plan missing senyuMenseki/madori"
            )

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._get_specs(response)
        shubetsu = str(specs.get("種別", "") or specs.get("物件種別", "") or "")
        # tokyo816 inventory is 建売/土地 only (no condominiums). Use 建売 as the
        # mansion-job candidate and map 建物面積 → 専有面積; skip pure 土地 lots.
        if shubetsu and "土地" in shubetsu and "建売" not in shubetsu:
            raise SkipPropertyException(f"Non-mansion Heim land lot skipped: {shubetsu}")
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = self._parseMadori(response, specs)
        item.senyuMensekiStr = self._parseSenyuMensekiStr(response, specs)
        item.senyuMenseki = self._parseSenyuMenseki(response, specs)
        self._heim_apply_tatemono_as_senyu(item, specs)
        item.kaisuStr = self._parseKaisuStr(response, specs)
        self._heim_parse_floor_types(item)

        item.chikunengetsuStr = self._parseChikunengetsuStr(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.balconyMensekiStr = self._parseBalconyMensekiStr(response, specs)
        item.balconyMenseki = self._parseBalconyMenseki(response, specs)
        item.soukosuStr = self._parseSoukosuStr(response, specs)
        item.soukosu = self._parseSouKosu(response, specs)

        item.kanrihiStr = self._parseKanrihiStr(response, specs)
        item.kanrihi = self._parseKanrihi(response, specs)
        item.syuzenTsumitateStr = self._parseSyuzenTsumitateStr(response, specs)
        item.syuzenTsumitate = self._parseSyuzenTsumitate(response, specs)

        item.kouzou = self._parseKouzou(response, specs)
        item.kanriKeitai = self._parseKanriKeitai(response, specs)
        item.kanriKaisya = self._parseKanriKaisya(response, specs)

        item.saikou = self._parseSaikou(response, specs)
        item.saikouMuki = item.saikou
        item.saikouMukiStr = item.saikou
        item.saikouKadobeya = self._parseSaikouKadobeya(response, specs)
        item.kadobeya = item.saikouKadobeya
        self._heim_require_senyu_and_madori(item)

        return item

class HeimKodateParser(HeimParser, KodateParserBase):
    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseRights(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or super()._parseRights(response, specs)

    property_type = 'kodate'

    def createEntity(self):
        return HeimKodate()

    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "")

    def _parseTochiMensekiStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        val_str = self._parseTochiMensekiStr(response, specs)
        return converter.parse_menseki(val_str) if val_str else None

    def _parseTatemonoMensekiStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("建物面積", "") or specs.get("延床面積", "")

    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None):
        val_str = self._parseTatemonoMensekiStr(response, specs)
        return converter.parse_menseki(val_str) if val_str else None

    def _parseChikunengetsuStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("築年月", "") or specs.get("完成年月", "") or specs.get("完成時期", "")

    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        val_str = self._parseChikunengetsuStr(response, specs)
        return converter.parse_chikunengetsu(val_str) if val_str else None

    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("建物構造", "") or specs.get("構造", "")

    def _parseKaisuStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("階数", "")

    def _parseKaisu(self, response: BeautifulSoup, specs=None):
        val_str = self._parseKaisuStr(response, specs)
        return converter.parse_numeric(val_str) if val_str else None

    def _parseKenpeiStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response: BeautifulSoup, specs=None):
        val_str = self._parseKenpeiStr(response, specs)
        return converter.parse_ratio(val_str) if val_str else None

    def _parseYousekiStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response: BeautifulSoup, specs=None):
        val_str = self._parseYousekiStr(response, specs)
        return converter.parse_ratio(val_str) if val_str else None

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("接道状況", "")

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._get_specs(response)
        shubetsu = str(specs.get("種別", "") or "")
        if shubetsu and "土地" in shubetsu and "建売" not in shubetsu:
            raise SkipPropertyException(f"Non-kodate Heim land lot skipped: {shubetsu}")
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = self._parseMadori(response, specs)
        item.tochiMensekiStr = self._parseTochiMensekiStr(response, specs)
        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.tatemonoMensekiStr = self._parseTatemonoMensekiStr(response, specs)
        item.tatemonoMenseki = self._parseTatemonoMenseki(response, specs)

        item.chikunengetsuStr = self._parseChikunengetsuStr(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.kouzou = self._parseKouzou(response, specs)
        item.kaisuStr = self._parseKaisuStr(response, specs)
        item.kaisu = self._parseKaisu(response, specs)

        item.kenpeiStr = self._parseKenpeiStr(response, specs)
        item.kenpei = self._parseKenpei(response, specs)
        item.yousekiStr = self._parseYousekiStr(response, specs)
        item.youseki = self._parseYouseki(response, specs)

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)
        # Incomplete plan lots omit 建物面積/間取り — skip to next candidate.
        if not getattr(item, "tatemonoMenseki", None) or not str(
            getattr(item, "madori", "") or ""
        ).strip():
            raise SkipPropertyException(
                "Heim kodate plan missing tatemonoMenseki/madori"
            )

        return item

class HeimTochiParser(HeimParser, TochiParserBase):
    def _parseMaguchi(self, response, specs=None):
        return super()._parseMaguchi(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)


    def _parseRights(self, response, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or super()._parseRights(response, specs)

    property_type = 'tochi'

    def createEntity(self):
        return HeimTochi()

    def _parseTochiMensekiStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("土地面積", "")

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        val_str = self._parseTochiMensekiStr(response, specs)
        return converter.parse_menseki(val_str) if val_str else None

    def _parseKenchikuJoken(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("建築条件", "")

    def _parseChimoku(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("地目", "")

    def _parseKenpeiStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("建ぺい率", "")

    def _parseKenpei(self, response: BeautifulSoup, specs=None):
        val_str = self._parseKenpeiStr(response, specs)
        return converter.parse_ratio(val_str) if val_str else None

    def _parseYousekiStr(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("容積率", "")

    def _parseYouseki(self, response: BeautifulSoup, specs=None):
        val_str = self._parseYousekiStr(response, specs)
        return converter.parse_ratio(val_str) if val_str else None

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("接道状況", "")

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._get_specs(response)
        shubetsu = str(specs.get("種別", "") or "")
        # Pure house lots without land area belong to kodate; land-bearing 建売
        # plans are valid tochi inventory on tokyo816 (建築条件付き土地相当).
        if (
            shubetsu
            and "建売" in shubetsu
            and "土地" not in shubetsu
            and not (specs.get("土地面積") or specs.get("敷地面積"))
        ):
            raise SkipPropertyException(f"Non-tochi Heim house lot skipped: {shubetsu}")
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = self._parseTochiMensekiStr(response, specs)
        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.kenchikuJoken = self._parseKenchikuJoken(response, specs)
        item.chimoku = self._parseChimoku(response, specs)
        
        item.kenpeiStr = self._parseKenpeiStr(response, specs)
        item.kenpei = self._parseKenpei(response, specs)
        item.yousekiStr = self._parseYousekiStr(response, specs)
        item.youseki = self._parseYouseki(response, specs)

        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)

        return item
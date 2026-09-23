import chardet
import aiohttp
from bs4 import BeautifulSoup
import json
import logging
import re

from abc import ABCMeta, abstractmethod
from decimal import Decimal
from typing import Any, Optional
from builtins import Exception

import asyncio
from django.db import models
from package.utils import converter
from package.utils.property_type_detector import PropertyTypeDetector
from package.utils.url_router import UrlRouter


class ReadPropertyNameException(Exception):

    def __init__(self, msg='Can not read property name'):
        super().__init__(msg)
        logging.info(msg)


class LoadPropertyPageException(Exception):

    def __init__(self, msg='Can not load property page'):
        super().__init__(msg)
        logging.info(msg)


class SkipPropertyException(Exception):
    """Base exception to skip a property without logging an error."""
    pass


class ListingEndedException(SkipPropertyException):
    """Raised when a property listing has ended."""
    pass


class ServerBusyException(SkipPropertyException):
    """Raised when the server is busy."""
    pass


class RateLimitedException(Exception):
    """Raised when target server returns HTTP 429 Too Many Requests."""
    pass


class ServerDownException(Exception):
    """Raised when target server is down or timing out repeatedly."""
    pass


class ParserBase(metaclass=ABCMeta):
    property_type = ''

    EXPECTED_SPEC_FIELDS_BY_TYPE = {
        'mansion': ['price', 'address', 'senyuMenseki', 'madori', 'chikunengetsuStr', 'kouzou'],
        'kodate': ['price', 'address', 'tochiMenseki', 'tatemonoMenseki', 'madori', 'chikunengetsuStr', 'kouzou'],
        'tochi': ['price', 'address', 'tochiMenseki'],
        'investment': ['price', 'address', 'grossYield', 'annualRent', 'kouzou'],
    }

    OPTIONAL_OR_METADATA_FIELDS = {
        'id', 'pageUrl', 'propertyName', 'priceStr', 'traffic', 'transport1',
        'inputDate', 'inputDateTime', 'updateDateTime',
        'transfer1', 'railway1', 'station1', 'railwayWalkMinute1Str', 'railwayWalkMinute1', 'busStation1', 'busWalkMinute1Str', 'busWalkMinute1',
        'transfer2', 'railway2', 'station2', 'railwayWalkMinute2Str', 'railwayWalkMinute2', 'busStation2', 'busWalkMinute2Str', 'busWalkMinute2',
        'transfer3', 'railway3', 'station3', 'railwayWalkMinute3Str', 'railwayWalkMinute3', 'busStation3', 'busWalkMinute3Str', 'busWalkMinute3',
        'transfer4', 'railway4', 'station4', 'railwayWalkMinute4Str', 'railwayWalkMinute4', 'busStation4', 'busWalkMinute4Str', 'busWalkMinute4',
        'transfer5', 'railway5', 'station5', 'railwayWalkMinute5Str', 'railwayWalkMinute5', 'busStation5', 'busWalkMinute5Str', 'busWalkMinute5',
        'railwayCount', 'busUse1', 'busUse2', 'busUse3', 'busUse4', 'busUse5',
        'senyuMensekiStr', 'chikunengetsu', 'kanrihiStr', 'kanrihi', 'syuzenTsumitateStr', 'syuzenTsumitate',
        'balconyMensekiStr', 'balconyMenseki', 'kaisu', 'kaisuStr', 'soukosu', 'soukosuStr',
        'saikou', 'kanriKeitai', 'kanriKaisya', 'tyusyajo',
        'tochiMensekiStr', 'tatemonoMensekiStr', 'chikunen', 'genkyo', 'currentStatus', 'tochikenri',
        'hikiwatashi', 'biko', 'setsudou', 'chimoku', 'youtoChiiki', 'kenpei', 'kenpeiStr', 'youseki', 'yousekiStr',
        'maguchi', 'maguchiStr', 'okuyuki', 'okuyukiStr', 'roadWidth', 'roadWidthStr', 'roadDirection', 'roadType', 'roadStructure',
        'monthlyRent', 'propertyType', 'notes', 'rawSpecs', 'chidai', 'chidaiStr', 'douroMuki',
        'address1', 'address2', 'address3', 'addressKyoto', 'bikeokiba', 'boukaChiiki', 'buildingCondition', 'bunjoKaisya',
        'chiikiChiku', 'chimokuChisei', 'chisei', 'cityPlanning', 'deliveryDate', 'direction', 'douro', 'douroHaba', 'douroKubun',
        'facilities', 'floor', 'floorStr', 'floorType_chijo', 'floorType_chika', 'floorType_kai', 'floorType_kouzou',
        'isSoldout', 'kadobeya', 'kaisuKouzou', 'kakuninBango', 'kanriKeitaiKaisya', 'kanrihi_p_heibei', 'kenchikuJoken',
        'kenpeiYousekiStr', 'kokudoHou', 'kuiki', 'kyutaishin', 'manager', 'neighborhood', 'nextUpdateAt', 'nextUpdateDate',
        'otherArea', 'otherFees', 'privateRoadBurden', 'privateRoadFee', 'roofBarukoniMenseki', 'saikenchiku',
        'saikouKadobeya', 'saikouMuki', 'saikouMukiStr', 'saikouSaiteki', 'saikouSaitekiStr', 'schoolDistrict',
        'sekouKaisya', 'senyouNiwaMenseki', 'setback', 'setsumen', 'shidoMenseki', 'shidoMensekiStr', 'shuzenTsumitate',
        'sonotaChiiki', 'sonotaHiyouStr', 'startRoad', 'syuzenTsumitate_p_heibei', 'tatemonoKaisu', 'torihiki',
        'totalFloor', 'totalFloorStr', 'transactionType', 'updateDate', 'updatedAt', 'urbanPlanning'
    }

    @classmethod
    def get_classified_fields(cls, prop_type: str = None) -> set:
        """検証対象(Fatal/Expected)および任意・メタ項目として分類済みの全フィールド集合"""
        classified = set(cls.OPTIONAL_OR_METADATA_FIELDS)
        if prop_type:
            classified.update(cls.EXPECTED_SPEC_FIELDS_BY_TYPE.get(prop_type, []))
        else:
            for fields in cls.EXPECTED_SPEC_FIELDS_BY_TYPE.values():
                classified.update(fields)
        return classified

    def _get_field_selector(self, selectors: dict, field: str) -> str:
        if not selectors:
            return ""
        if field in selectors:
            return str(selectors[field])
        s_name = re.sub(r'(?<!^)(?=[A-Z])', '_', field).lower()
        for candidate in [s_name, f"{s_name}_key", f"{s_name}_selector", f"{field}_key", f"{field}_selector"]:
            if candidate in selectors:
                return str(selectors[candidate])
        return ""

    def __init__(self):
        self._specs_cache = {}
        self.selectors = {}
        self.consecutive_timeouts = 0
        self.MAX_CONSECUTIVE_TIMEOUTS = 3
        self.MAX_PAGES_PER_JOB = 30
        self.MAX_PROPERTIES_PER_JOB = 600

    @abstractmethod
    def getCharset(self):
        pass

    @abstractmethod
    def createEntity(self) -> models.Model:
        return None

    # ==============================================================================
    # 1. 全物件種別 共通基本抽出メソッド (全種別共通項目・アブストラクト宣言)
    # ==============================================================================
    @abstractmethod
    def _parsePrice(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        """価格(数値)の抽出"""
        specs = specs or self._get_specs(response)
        price_str = specs.get("価格", "") or specs.get("販売価格", "") or specs.get("物件価格", "")
        if not price_str and response:
            tag = self._getValueByLabel(response, "価格") or self._getValueByLabel(response, "販売価格")
            if tag:
                price_str = tag.get_text(strip=True) if hasattr(tag, 'get_text') else str(tag)
        if not price_str and response:
            el = response.select_one(".price, .mod-price, span.priceNum, td.price, .priceText")
            if el:
                price_str = el.get_text(strip=True)
        return converter.parse_price(price_str)

    @abstractmethod
    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        """価格(文字列)の抽出"""
        specs = specs or self._get_specs(response)
        price_str = specs.get("価格", "") or specs.get("販売価格", "") or specs.get("物件価格", "")
        if not price_str and response:
            el = response.select_one(".price, .mod-price, span.priceNum, td.price")
            if el:
                price_str = el.get_text(strip=True)
        return price_str

    @abstractmethod
    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        """所在地(住所)の抽出"""
        specs = specs or self._get_specs(response)
        addr = specs.get("所在地", "") or specs.get("住所", "")
        if not addr and response:
            tag = self._getValueByLabel(response, "所在地") or self._getValueByLabel(response, "住所")
            if tag:
                addr = tag.get_text(strip=True) if hasattr(tag, 'get_text') else str(tag)
        if not addr and response:
            el = response.select_one(".address, .mod-address, td.address")
            if el:
                addr = el.get_text(strip=True)
        return addr

    @abstractmethod
    def _parsePropertyName(self, response: BeautifulSoup, specs=None) -> str:
        """物件名の抽出"""
        specs = specs or self._get_specs(response)
        name = specs.get("物件名", "") or specs.get("名称", "") or specs.get("物件名称", "")
        if not name and response:
            # Prefer first non-empty heading (some sites render empty <h1> before <h2>).
            for title_el in response.find_all(["h1", "h2"], limit=5):
                candidate = title_el.get_text(strip=True)
                if candidate:
                    name = candidate
                    break
        return name

    @abstractmethod
    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        """最寄り駅・交通アクセスの抽出"""
        specs = specs or self._get_specs(response)
        return specs.get("交通", "") or specs.get("最寄り駅", "") or specs.get("沿線・駅", "")

    @abstractmethod
    def _parsePropertyDetailPage(self, item: models.Model, response: BeautifulSoup) -> models.Model:
        return item

    def _parseChidaiStr(self, response: BeautifulSoup, specs=None) -> str:
        """地代（文字列）の抽出"""
        specs = specs or self._get_specs(response)
        # 優先キー
        for key in ["借地期間・地代（月額）", "借地期間・地代", "地代（月額）", "地代等", "地代", "借地料（月額）", "借地料", "月額地代", "土地地代"]:
            if key in specs and specs[key]:
                return specs[key]
        for k, v in specs.items():
            if any(term in k for term in ["地代", "借地料"]):
                return v
        if response:
            tag = self._getValueByLabel(response, "地代") or self._getValueByLabel(response, "借地料")
            if tag:
                return tag.get_text(strip=True) if hasattr(tag, 'get_text') else str(tag)
        return ""

    def _parseChidai(self, response: BeautifulSoup, specs=None) -> int | None:
        """地代（月額・数値円）の抽出"""
        chidai_str = self._parseChidaiStr(response, specs)
        return converter.parse_chidai(chidai_str)

    async def parsePropertyListPage(self, response):
        return
        yield

    def _get_specs(self, response: BeautifulSoup) -> dict:
        """HTML内のth/td, dt/dd, .table-rowテーブルを標準解析し辞書として取得"""
        if not response:
            return {}
        specs = {}
        for tr in response.find_all("tr"):
            ths = tr.find_all("th")
            tds = tr.find_all("td")
            if ths and tds:
                if len(ths) == len(tds):
                    for th, td in zip(ths, tds):
                        k = th.get_text(strip=True)
                        v = td.get_text(strip=True)
                        if k:
                            specs[k] = v
                else:
                    k = ths[0].get_text(strip=True)
                    v = tds[0].get_text(strip=True)
                    if k:
                        specs[k] = v
        for dl in response.find_all("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                k = dt.get_text(strip=True)
                v = dd.get_text(strip=True)
                if k:
                    specs[k] = v
        for row in response.select(".table-row, div.row, tr.table-row"):
            lbl = row.select_one(".label, .table-header, th, dt")
            val = row.select_one(".content, .table-data")
            if not val or val == lbl:
                candidates = [el for el in row.find_all(["td", "dd"]) if el != lbl]
                val = candidates[0] if candidates else None
            if lbl and val and lbl != val:
                k = lbl.get_text(strip=True)
                v = val.get_text(strip=True)
                if k and k not in specs:
                    specs[k] = v
        return specs

    def _scrape_specs(self, response: BeautifulSoup) -> dict:
        return self._get_specs(response)

    def _scrape_to_dict(self, response: BeautifulSoup) -> dict:
        return self._get_specs(response)

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        """Default base detail page parse returning the item entity."""
        return item

    async def _parsePageCore(self, response: BeautifulSoup, xpath_fn=None, dest_url_fn=None):
        if not dest_url_fn:
            return
        xpath_pattern = xpath_fn() if callable(xpath_fn) else ""
        for link in response.find_all("a"):
            href = link.get("href")
            if not href or href == "#":
                continue
            if href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
                continue
            if "/inquiry" in href or "/contact" in href or "/shiritai/" in href or "/360/" in href or "/benefit/" in href:
                continue
            # If target pattern expects property details, filter out non-detail URLs and wrong categories (e.g. /rent/, /chintai/)
            if xpath_pattern:
                str_xpath = str(xpath_pattern)
                # Filter out rental links for buy/sale crawlers
                if "/chintai/" not in str_xpath and "/rent/" not in str_xpath:
                    if "/chintai/" in href or "/rent/" in href or "/chintai_" in href:
                        continue
                if "bkdetail" in str_xpath or "detail" in str_xpath:
                    if "bkdetail" not in href and "detail" not in href and "room" not in href:
                        continue
                    if "/buy/" in str_xpath and "/buy/" not in href:
                        continue
                # Extract negative substrings from xpath not(contains(@href, '...'))
                excluded_subs = re.findall(r'not\s*\(\s*contains\s*\(\s*@href\s*,\s*["\']([^"\']+)["\']\s*\)\s*\)', str_xpath)
                if excluded_subs and any(sub in href for sub in excluded_subs):
                    continue
                # Extract required positive substrings from xpath (excluding those inside not())
                clean_xpath = re.sub(r'not\s*\([^)]+\)', '', str_xpath)
                required_subs = re.findall(r'contains\s*\(\s*@href\s*,\s*["\']([^"\']+)["\']\s*\)', clean_xpath)
                if required_subs and not all(sub in href for sub in required_subs):
                    continue
                starts_with_subs = re.findall(r'starts-with\s*\(\s*@href\s*,\s*["\']([^"\']+)["\']\s*\)', clean_xpath)
                if starts_with_subs and not any(href.startswith(sub) for sub in starts_with_subs):
                    continue
            try:
                dest_url = dest_url_fn(href) if callable(dest_url_fn) else href
            except Exception:
                dest_url = None
            if dest_url and isinstance(dest_url, str) and dest_url.startswith("http"):
                if "javascript:" in dest_url or "void(0)" in dest_url or "/inquiry" in dest_url or "/contact" in dest_url:
                    continue
                yield dest_url

    def _split_address(self, address_str: str):
        """都道府県・市区町村・町名の自動分割ユーティリティ (市川市・市原市・町田市・武蔵村山市等対応)"""
        if not address_str:
            return "", "", ""
        pref_match = re.match(r'^(東京都|北海道|(?:京都|大阪)府|.{2,3}県)', address_str)
        pref = pref_match.group(1) if pref_match else ""
        rest = address_str[len(pref):] if pref else address_str
        
        # 1. 郡+町村 / 政令指定都市 (市+区) / 特殊包含市名 / 東京23区 (特別区) / 一般市区町村
        city_match = re.match(
            r'^('
            r'.+?郡.+?[町村]|'  # 郡+町村 (例: 余市郡余市町)
            r'[^市区町村]+市[^市区町村]+区|'  # 政令指定都市区 (例: 川崎市中原区, 横浜市港北区)
            r'(?:市川|市原|八日市|四日市|今市|武蔵村山|東村山|村山|羽村|大村|村上|十日町|大町|町田)市|'  # 特殊文字包含市名プレフィックス
            r'(?:千代田|中央|港|新宿|文京|台東|墨田|江東|品川|目黒|大田|世田谷|渋谷|中野|杉並|豊島|北|荒川|板橋|練馬|足立|葛飾|江戸川)区|'  # 東京23特別区
            r'[^市区町村]+[市区町村]|'  # 一般市区町村
            r'[市区町村][^市区町村]+[市区町村]'  # 市/町/村で始まる市区町村 (市原市, 町田市等)
            r')', rest
        )
        city = city_match.group(1) if city_match else ""
        town = rest[len(city):] if city else rest

        # 都道府県名が含まれていない場合の主要市町村自動補完
        if not pref and city:
            CITY_PREF_MAP = {
                "伊勢原市": "神奈川県",
                "市原市": "千葉県",
                "市川市": "千葉県",
                "世田谷区": "東京都",
                "町田市": "東京都",
                "武蔵村山市": "東京都",
                "東村山市": "東京都",
                "羽村市": "東京都",
                "荒川区": "東京都",
                "横浜市中区": "神奈川県",
            }
            pref = CITY_PREF_MAP.get(city, "")

        return pref, city, town

    def _populateTraffic(self, item: models.Model, traffic_str: str | list) -> models.Model:
        """交通アクセスの自動パース・モデルフィールド設定ユーティリティ"""
        if not traffic_str:
            return item
        if isinstance(traffic_str, list):
            traffic_text = "\n".join([str(x) for x in traffic_str if x])
        else:
            traffic_text = traffic_str
        item.transport1 = traffic_text
        
        # 1. ブラケット形式: 沿線名「駅名」徒歩分 (例: 東京メトロ有楽町線「麹町」駅 徒歩3分)
        m = re.search(r'([^\s「」]+?(?:線|ライン|ライナー|鉄道|本線|空港線|地下鉄|メトロ|新幹線)?)\s*「([^「」]+?)」\s*(?:駅|停留所|バス停)?\s*(?:徒歩|バス|車)?\s*(\d+)?\s*分?', traffic_text)
        if m:
            railway = m.group(1).strip()
            station = m.group(2).strip("『』「」 ").strip()
            if station.endswith('駅'):
                station = station[:-1].strip()
            walk_min = m.group(3)
            
            if hasattr(item, 'railway1') and not getattr(item, 'railway1', None) and railway:
                item.railway1 = railway
            if hasattr(item, 'station1') and not getattr(item, 'station1', None):
                item.station1 = station
            if hasattr(item, 'walkMinutes1') and walk_min:
                try:
                    item.walkMinutes1 = int(walk_min)
                except Exception:
                    pass
            if hasattr(item, 'railwayWalkMinute1') and walk_min:
                try:
                    item.railwayWalkMinute1 = int(walk_min)
                except Exception:
                    pass
            return item

        # 2. スペース区切り形式: 沿線名 駅名 徒歩分 (例: JR山手線 新宿駅 徒歩5分)
        m = re.search(r'([^\s「」\/]+?(?:線|ライン|ライナー|鉄道|本線|空港線|地下鉄|メトロ|新幹線))\s+([^\s「」\/]+?駅)\s*(?:徒歩|バス|車)?\s*(\d+)?\s*分?', traffic_text)
        if m:
            railway = m.group(1).strip()
            station = m.group(2).strip("『』「」 ").strip()
            if station.endswith('駅'):
                station = station[:-1].strip()
            walk_min = m.group(3)
            
            if hasattr(item, 'railway1') and not getattr(item, 'railway1', None):
                item.railway1 = railway
            if hasattr(item, 'station1') and not getattr(item, 'station1', None):
                item.station1 = station
            if hasattr(item, 'walkMinutes1') and walk_min:
                try:
                    item.walkMinutes1 = int(walk_min)
                except Exception:
                    pass
            if hasattr(item, 'railwayWalkMinute1') and walk_min:
                try:
                    item.railwayWalkMinute1 = int(walk_min)
                except Exception:
                    pass
            return item

        # 3. フォールバック: 駅名 徒歩分 (例: 新宿駅 徒歩5分)
        m = re.search(r'([^\s「」]+?(?:駅|停留所|バス停))\s*(?:徒歩|バス|車)?\s*(\d+)?\s*分?', traffic_text)
        if m:
            station = m.group(1).strip()
            walk_min = m.group(2)
            if hasattr(item, 'station1') and not getattr(item, 'station1', None):
                item.station1 = station
            if hasattr(item, 'walkMinutes1') and walk_min and getattr(item, 'walkMinutes1', None) is None:
                try:
                    item.walkMinutes1 = int(walk_min)
                except Exception:
                    pass
            return item

        return item

    async def getResponseBs(self, session, url: str, charset: str | None = None) -> BeautifulSoup:
        """指定URLのコンテンツを取得し BeautifulSoup (lxml/html.parser) として返す"""
        content = await self._getContent(session, url)
        encoding = charset or self.getCharset() or chardet.detect(content[:4096])["encoding"] or "utf-8"
        if encoding and str(encoding).lower() in ("shift_jis", "sjis", "shift-jis", "windows-31j"):
            encoding = "cp932"
        try:
            soup = BeautifulSoup(content, "lxml", from_encoding=encoding)
            if not soup.find() or len(str(soup)) < 100:
                soup = BeautifulSoup(content, "html.parser", from_encoding=encoding)
            return soup
        except Exception:
            return BeautifulSoup(content, "html.parser", from_encoding=encoding)

    async def getResponse(self, session, url: str, charset: str | None = None) -> BeautifulSoup:
        return await self.getResponseBs(session, url, charset=charset)

    async def parseNextPage(self, response):
        return ""

    def _getValueByLabel(self, soup: BeautifulSoup, label: str):
        if not soup:
            return None
        for tag in soup.find_all(["th", "dt", "span", "td", "div"]):
            txt = tag.get_text(strip=True)
            if label in txt:
                nxt = tag.find_next_sibling(["td", "dd", "span", "div"])
                if nxt:
                    return nxt
        return None

    def _resolve_validation_property_type(self, item: models.Model) -> str:
        pt = (getattr(self, 'property_type', '') or '').lower()
        if 'mansion' in pt:
            return 'mansion'
        if 'kodate' in pt and 'invest' not in pt:
            return 'kodate'
        if 'tochi' in pt:
            return 'tochi'
        if 'invest' in pt or 'apartment' in pt:
            return 'investment'

        mname = item.__class__.__name__.lower()
        if 'mansion' in mname or hasattr(item, 'senyuMenseki'):
            return 'mansion'
        if 'invest' in mname or 'apartment' in mname or hasattr(item, 'grossYield'):
            return 'investment'
        if 'kodate' in mname or hasattr(item, 'tatemonoMenseki'):
            return 'kodate'
        if 'tochi' in mname or hasattr(item, 'tochiMenseki'):
            return 'tochi'
        return 'general'

    @staticmethod
    def _validate_numeric_field_val(val: Any) -> tuple[bool, str]:
        if val is None:
            return True, "value is None"
        if isinstance(val, (int, float, Decimal)) and val <= 0:
            return True, f"invalid non-positive value ({val})"
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ['', 'none', 'null']:
                return True, "empty string"
            try:
                if float(s) <= 0:
                    return True, f"invalid non-positive value string ({val})"
            except ValueError:
                pass
        return False, ""

    @staticmethod
    def _validate_rent_field_val(item: models.Model, rent_val: Any) -> tuple[bool, str]:
        m_rent = getattr(item, 'monthlyRent', None)
        has_rent = False
        if rent_val is not None:
            try:
                if float(rent_val) > 0:
                    has_rent = True
            except (ValueError, TypeError):
                pass
        if not has_rent and m_rent is not None:
            try:
                if float(m_rent) > 0:
                    has_rent = True
            except (ValueError, TypeError):
                pass
        if not has_rent:
            return True, f"annualRent and monthlyRent are both missing or zero (annualRent={rent_val}, monthlyRent={m_rent})"
        return False, ""

    @staticmethod
    def _validate_general_field_val(val: Any) -> tuple[bool, str]:
        if val is None:
            return True, "value is None"
        if isinstance(val, str) and val.strip().lower() in ['', 'none', 'null']:
            return True, "empty string"
        return False, ""

    def _validate_item_field(self, item: models.Model, field: str) -> Optional[dict]:
        if not hasattr(item, field):
            return None
        val = getattr(item, field, None)

        # Under-construction listings often omit building area / year yet.
        genkyo = str(
            getattr(item, "genkyo", "")
            or getattr(item, "currentStatus", "")
            or ""
        )
        if any(tok in genkyo for tok in ("未完成", "建築中", "新築（未完成）")):
            if field in ("tatemonoMenseki", "chikunengetsuStr"):
                return None

        # Numeric specs are often stored first as *Str; reparse Str when numeric is empty.
        str_fallback = {
            "senyuMenseki": "senyuMensekiStr",
            "tochiMenseki": "tochiMensekiStr",
            "tatemonoMenseki": "tatemonoMensekiStr",
        }.get(field)
        if str_fallback and hasattr(item, str_fallback):
            str_val = getattr(item, str_fallback, None)
            if isinstance(str_val, str) and str_val.strip():
                num_invalid, _ = self._validate_numeric_field_val(val)
                if not num_invalid:
                    return None
                parsed = converter.parse_menseki(str_val)
                if parsed is not None:
                    setattr(item, field, parsed)
                    return None

        if field in ['price', 'senyuMenseki', 'tochiMenseki', 'tatemonoMenseki', 'grossYield']:
            is_invalid, reason = self._validate_numeric_field_val(val)
        elif field == 'annualRent':
            is_invalid, reason = self._validate_rent_field_val(item, val)
        else:
            is_invalid, reason = self._validate_general_field_val(val)

        if is_invalid:
            return {
                "field": field,
                "value": str(val) if isinstance(val, Decimal) else val,
                "reason": reason,
                "selector": self._get_field_selector(getattr(self, 'selectors', {}) or {}, field),
            }
        return None

    def validate_extracted_fields(self, item: models.Model) -> list[dict]:
        """
        全サイト全項目のスクレイピング抽出結果検証 (Issue #209)
        重要・必須スペック項目が未抽出(None/空文字)または不正な0値に補完されていないかを検証し、
        問題がある場合は [PARSER_EXTRACTION_ERROR] をエラーログとして出力する。
        """
        prop_type = self._resolve_validation_property_type(item)
        expected_fields = self.EXPECTED_SPEC_FIELDS_BY_TYPE.get(prop_type, ['price', 'address'])
        errors: list[dict] = []

        for field in expected_fields:
            err = self._validate_item_field(item, field)
            if err:
                errors.append(err)

        if errors and not getattr(item, '_extraction_error_logged', False):
            item._extraction_error_logged = True
            self._log_extraction_errors(item, prop_type, errors)

        return errors

    def _log_extraction_errors(self, item: models.Model, prop_type: str, errors: list[dict]):
        url = getattr(item, 'pageUrl', '') or 'unknown'
        model_name = item.__class__.__name__
        company = getattr(self, 'company', '') or getattr(self, '__class__', type(self)).__name__
        selectors = getattr(self, 'selectors', {}) or {}
        log_payload = {
            "event": "PARSER_EXTRACTION_ERROR",
            "url": url,
            "propertyName": getattr(item, "propertyName", "") or "",
            "company": company,
            "model": model_name,
            "property_type": prop_type,
            "failed_count": len(errors),
            "failed_fields": [e["field"] for e in errors],
            "details": errors,
            "selectors": selectors,
        }
        logging.error(
            f"[PARSER_EXTRACTION_ERROR] Property extraction failed for URL: {url} | Payload: {json.dumps(log_payload, ensure_ascii=False, default=str)}"
        )

    def clean_parsed_item(self, item: models.Model) -> models.Model:
        # Issue #209: 全サイト全項目の抽出結果検証（0補完・欠損隠蔽防止エラーロギング）
        self.validate_extracted_fields(item)

        for field in item._meta.fields:
            val = getattr(item, field.name, None)
            if isinstance(field, (models.CharField, models.TextField)):
                if val is None:
                    if not field.null:
                        setattr(item, field.name, "")
                    continue
                val_str = str(val).strip()
                if val_str.lower() in ["none", ""]:
                    if field.null:
                        setattr(item, field.name, None)
                    else:
                        setattr(item, field.name, "")
                else:
                    val_cleaned = re.sub(r'\s+', ' ', val_str)
                    setattr(item, field.name, val_cleaned)

        # 数値フィールドの数値検証・NOT NULL制約ガード・オーバーフロー防止
        for int_field_name in ['price', 'annualRent', 'monthlyRent', 'soukosu', 'chikunen', 'chidai']:
            if hasattr(item, int_field_name):
                f_obj = item._meta.get_field(int_field_name)
                f_val = getattr(item, int_field_name, None)
                if f_val is not None:
                    try:
                        val_int = int(f_val)
                        # 32-bit IntegerField に対するオーバーフロー防止（BIGINT未適用のテーブル向け安全ガード）
                        if isinstance(f_obj, models.IntegerField) and not isinstance(f_obj, models.BigIntegerField):
                            if val_int > 2147483647:
                                val_int = 2147483647
                            elif val_int < -2147483648:
                                val_int = -2147483648
                        setattr(item, int_field_name, val_int)
                    except (ValueError, TypeError):
                        setattr(item, int_field_name, None if f_obj.null else 0)
                elif not f_obj.null:
                    setattr(item, int_field_name, 0)

        # chidai / chidaiStr の自動補完（パーサー個別実装で未設定の場合、_soupから自動抽出）
        soup = getattr(item, '_soup', None)
        if soup is not None:
            if hasattr(item, 'chidai') and getattr(item, 'chidai', None) is None:
                c_val = self._parseChidai(soup)
                if c_val is not None:
                    setattr(item, 'chidai', c_val)
            if hasattr(item, 'chidaiStr') and not getattr(item, 'chidaiStr', ''):
                cs_val = self._parseChidaiStr(soup)
                if cs_val:
                    setattr(item, 'chidaiStr', cs_val)

        # grossYield (DecimalField) の NOT NULL ガード
        if hasattr(item, 'grossYield'):
            f_obj = item._meta.get_field('grossYield')
            gy_val = getattr(item, 'grossYield', None)
            if gy_val is None and not f_obj.null:
                from decimal import Decimal
                setattr(item, 'grossYield', Decimal('0.0'))


        # station1, station2, station3 の表記統一 (『成城学園前』駅 -> 成城学園前, 勝どき駅 -> 勝どき)
        for st_field in ['station1', 'station2', 'station3']:
            if hasattr(item, st_field):
                st_val = getattr(item, st_field, None)
                if st_val and isinstance(st_val, str):
                    cleaned_st = st_val.strip("『』「」 ").strip()
                    if cleaned_st.endswith('駅'):
                        cleaned_st = cleaned_st[:-1].strip()
                    setattr(item, st_field, cleaned_st)

        # genkyo / currentStatus の自動相互同期
        genkyo_val = getattr(item, 'genkyo', None) if hasattr(item, 'genkyo') else None
        curr_val = getattr(item, 'currentStatus', None) if hasattr(item, 'currentStatus') else None
        if genkyo_val and hasattr(item, 'currentStatus') and not curr_val:
            setattr(item, 'currentStatus', genkyo_val)
        elif curr_val and hasattr(item, 'genkyo') and not genkyo_val:
            setattr(item, 'genkyo', curr_val)

        return item

    def validate_required_fields(self, item: models.Model):
        errors = []
        if hasattr(item, 'price'):
            p_val = getattr(item, 'price', None)
            if p_val is None or (isinstance(p_val, (int, float, Decimal)) and p_val <= 0):
                errors.append(f"price is invalid or non-positive ({p_val})")
        if hasattr(item, 'address') and not getattr(item, 'address', ''):
            errors.append("address is empty")

        if errors:
            err_msg = f"StrictExtractionFailed: {', '.join(errors)} for URL: {getattr(item, 'pageUrl', 'unknown')}"
            logging.warning(err_msg)
            raise LoadPropertyPageException(err_msg)

    def save_error_html(self, url: str, content: bytes, reason: str = "Parsing failed"):
        """エラー発生時の生HTMLおよびメタデータをdocs/error_pages/配下に自動保存"""
        import hashlib
        from pathlib import Path
        import datetime
        try:
            error_dir = Path("docs/error_pages")
            try:
                model_name = self.createEntity().__class__.__name__
                company_type = re.sub(r'(?<!^)(?=[A-Z])', '_', model_name).lower()
                company_dir = error_dir / company_type
            except Exception:
                company_dir = error_dir / "unknown"
            company_dir.mkdir(parents=True, exist_ok=True)
            base_filename = hashlib.sha256(url.encode('utf-8')).hexdigest()
            html_filepath = company_dir / (base_filename + ".html")
            meta_filepath = company_dir / (base_filename + "_meta.txt")
            with open(html_filepath, "wb") as f:
                f.write(content)
            with open(meta_filepath, "w", encoding="utf-8") as f:
                f.write(f"URL: {url}\nReason: {reason}\nTimestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            logging.info(f"Saved error HTML to {company_dir}/{base_filename}")
        except Exception:
            logging.exception("Failed to save error HTML")

    async def parsePropertyDetailPage(self, session, url) -> models.Model:
        """物件詳細ページを取得・動的種別判定を行い、適切なパーサーでパースしてモデルインスタンスを返却"""
        if url:
            u_lower = str(url).lower()
            if any(p in u_lower for p in ["/shiritai/", "/360/", "/chintai/", "/rent/", "/inquiry", "/contact", "/benefit/"]):
                logging.info(f"Fast-skipping non-property/rental URL: {url}")
                raise SkipPropertyException(f"Non-property URL skipped: {url}")

        item: models.Model = self.createEntity()
        content = None
        try:
            item.pageUrl = url
            content = await self._getContent(session, url)
            charset = self.getCharset()
            if charset is None:
                encoding = chardet.detect(content[:4096])["encoding"] or "utf-8"
            else:
                encoding = charset
            if encoding and str(encoding).lower() in ("shift_jis", "sjis", "shift-jis", "windows-31j"):
                encoding = "cp932"
            try:
                soup = BeautifulSoup(content, "lxml", from_encoding=encoding)
                if not soup.find() or len(str(soup)) < 100:
                    soup = BeautifulSoup(content, "html.parser", from_encoding=encoding)
            except Exception:
                soup = BeautifulSoup(content, "html.parser", from_encoding=encoding)

            title = soup.title.string if soup.title else ""
            if title:
                if "掲載終了物件" in title:
                    logging.info(f"Listing ended for URL: {url}")
                    raise ListingEndedException()
                if "サーバーが混み合っています" in title:
                    logging.info(f"Server busy for URL: {url}")
                    raise ServerBusyException()

            # 物件詳細到着時の動的種別判定およびパーサー自己切り替え
            specs = self._get_specs(soup)
            detected_type = PropertyTypeDetector.detect(
                url=url,
                title=title,
                html_text=soup.get_text()[:2000],
                specs=specs,
                default=self.property_type
            )
            parser_to_use = self
            if detected_type and self.property_type and detected_type != self.property_type:
                target_parser = UrlRouter.create_parser(
                    url=url,
                    title=title,
                    html_text=soup.get_text()[:2000],
                    specs=specs,
                    property_type=detected_type
                )
                if target_parser and target_parser.__class__ != self.__class__:
                    logging.info(
                        f"[PropertyTypeSwitch] URL {url}: expected '{self.property_type}' ({self.__class__.__name__}) "
                        f"-> detected '{detected_type}' ({target_parser.__class__.__name__})"
                    )
                    parser_to_use = target_parser
                    item = target_parser.createEntity()
                    item.pageUrl = url

            item = parser_to_use._parsePropertyDetailPage(item, soup)
            item = parser_to_use.clean_parsed_item(item)
            item._soup = soup
            parser_to_use.validate_required_fields(item)
        except SkipPropertyException as e:
            raise e
        except (LoadPropertyPageException, TimeoutError) as e:
            logging.error(f'Failure loading page: {url} - Reason: {str(e)}')
            raise e
        except Exception as e:
            msg = f"Can not read property page: {url} - Reason: {str(e)}"
            logging.error(msg)
            if content:
                self.save_error_html(url, content, reason=str(e))
            raise LoadPropertyPageException(msg)
        return item

    async def _getContent(self, session: aiohttp.ClientSession, url: str) -> bytes:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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


# ==============================================================================
# 物件種別別 Base パーサークラス (Property-Type Base Parsers)
# ==============================================================================

class MansionParserBase(ParserBase):
    """
    マンション用基底パーサークラス
    """
    property_type = 'mansion'

    @abstractmethod
    def _parseSenyuMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("専有面積", "") or specs.get("壁芯面積", "")
        if val:
            m = re.search(r'([\d\.]+)', val)
            return Decimal(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "")

    @abstractmethod
    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("築年月", "") or specs.get("完成時期", "")
        return converter.parse_chikunengetsu(s) if s else None

    @abstractmethod
    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("構造", "") or specs.get("建物構造", "")

    @abstractmethod
    def _parseFloor(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("階数", "") or specs.get("所在階", "")

    @abstractmethod
    def _parseSouKosu(self, response: BeautifulSoup, specs=None) -> int | None:
        specs = specs or self._get_specs(response)
        val = specs.get("総戸数", "")
        if val:
            m = re.search(r'(\d+)', val)
            return int(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseManagementFee(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("管理費", "")
        return converter.parse_price(val) if val else None

    @abstractmethod
    def _parseReserveFund(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("修繕積立金", "")
        return converter.parse_price(val) if val else None

    @abstractmethod
    def _parseKenpei(self, response: BeautifulSoup, specs=None) -> int | None:
        specs = specs or self._get_specs(response)
        val = specs.get("建ぺい率", "") or specs.get("建蔽率", "")
        if val:
            m = re.search(r'(\d+)', val)
            return int(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseYouseki(self, response: BeautifulSoup, specs=None) -> int | None:
        specs = specs or self._get_specs(response)
        val = specs.get("容積率", "")
        if val:
            m = re.search(r'(\d+)', val)
            return int(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引き渡し", "")

    @abstractmethod
    def _parseGenkyo(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    @abstractmethod
    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None) -> str:
        return self._parseGenkyo(response, specs)

    @abstractmethod
    def _parseRights(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or specs.get("借地権種類", "")

    @abstractmethod
    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "")


class KodateParserBase(ParserBase):
    """
    戸建て用基底パーサークラス
    """
    property_type = 'kodate'

    @abstractmethod
    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("土地面積", "") or specs.get("区画面積", "") or specs.get("敷地面積", "")
        if val:
            m = re.search(r'([\d\.]+)', val)
            return Decimal(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("建物面積", "") or specs.get("延床面積", "")
        if val:
            m = re.search(r'([\d\.]+)', val)
            return Decimal(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("築年月", "") or specs.get("完成時期", "")
        return converter.parse_chikunengetsu(s) if s else None

    @abstractmethod
    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "")

    @abstractmethod
    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("構造", "") or specs.get("建物構造", "")

    @abstractmethod
    def _parseKenpei(self, response: BeautifulSoup, specs=None) -> int | None:
        specs = specs or self._get_specs(response)
        val = specs.get("建ぺい率", "") or specs.get("建蔽率", "")
        if val:
            m = re.search(r'(\d+)', val)
            return int(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseYouseki(self, response: BeautifulSoup, specs=None) -> int | None:
        specs = specs or self._get_specs(response)
        val = specs.get("容積率", "")
        if val:
            m = re.search(r'(\d+)', val)
            return int(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseRights(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "") or specs.get("借地権種類", "")

    @abstractmethod
    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "")

    @abstractmethod
    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("接道状況", "") or specs.get("接道", "")

    @abstractmethod
    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引き渡し", "")

    @abstractmethod
    def _parseGenkyo(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    @abstractmethod
    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None) -> str:
        return self._parseGenkyo(response, specs)

    def _parseChimoku(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("地目", "")


class TochiParserBase(ParserBase):
    """
    土地用基底パーサークラス
    """
    property_type = 'tochi'

    @abstractmethod
    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("土地面積", "") or specs.get("区画面積", "") or specs.get("敷地面積", "")
        if val:
            m = re.search(r'([\d\.]+)', val)
            return Decimal(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseKenpei(self, response: BeautifulSoup, specs=None) -> int | None:
        specs = specs or self._get_specs(response)
        val = specs.get("建ぺい率", "") or specs.get("建蔽率", "")
        if val:
            m = re.search(r'(\d+)', val)
            return int(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseYouseki(self, response: BeautifulSoup, specs=None) -> int | None:
        specs = specs or self._get_specs(response)
        val = specs.get("容積率", "")
        if val:
            m = re.search(r'(\d+)', val)
            return int(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseChimoku(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("地目", "")

    @abstractmethod
    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("接道状況", "") or specs.get("接道", "")

    @abstractmethod
    def _parseRights(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

    @abstractmethod
    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "")

    @abstractmethod
    def _parseMaguchi(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("間口", "") or specs.get("接道状況", "") or specs.get("接道", "")
        if not val and response:
            tag = self._getValueByLabel(response, "間口") or self._getValueByLabel(response, "接道")
            if tag:
                val = tag.get_text(strip=True) if hasattr(tag, 'get_text') else str(tag)
        if val:
            match = re.search(r'(?:間口|約|幅員|道路)?\s*(\d+(?:\.\d+)?)\s*[mｍ]', val)
            if match:
                try:
                    return Decimal(match.group(1))
                except Exception:
                    pass
        return None

    @abstractmethod
    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引き渡し", "")

    @abstractmethod
    def _parseGenkyo(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("現況", "") or specs.get("現況状況", "")

    @abstractmethod
    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None) -> str:
        return self._parseGenkyo(response, specs)


class InvestmentParserBase(ParserBase):
    """
    投資用物件用基底パーサークラス
    """
    property_type = 'investment'

    @abstractmethod
    def _parseGrossYield(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("表面利回り", "") or specs.get("利回り", "") or specs.get("想定利回り", "")
        if val:
            m = re.search(r'([\d\.]+)', val)
            return Decimal(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseAnnualRent(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("年間予定収入", "") or specs.get("満室時想定年収", "") or specs.get("年間収入", "") or specs.get("年収", "")
        return converter.parse_price(val) if val else None

    @abstractmethod
    def _parseMonthlyRent(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("月額収入", "") or specs.get("家賃", "")
        return converter.parse_price(val) if val else None

    @abstractmethod
    def _parseGenkyo(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("稼働状況", "") or specs.get("入居状況", "") or specs.get("現況", "")

    @abstractmethod
    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None) -> str:
        return self._parseGenkyo(response, specs)

    @abstractmethod
    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        s = specs.get("築年月", "") or specs.get("完成時期", "")
        return converter.parse_chikunengetsu(s) if s else None

    @abstractmethod
    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("構造", "") or specs.get("建物構造", "")

    @abstractmethod
    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("土地面積", "") or specs.get("区画面積", "") or specs.get("敷地面積", "")
        if val:
            m = re.search(r'([\d\.]+)', val)
            return Decimal(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        specs = specs or self._get_specs(response)
        val = specs.get("建物面積", "") or specs.get("延床面積", "")
        if val:
            m = re.search(r'([\d\.]+)', val)
            return Decimal(m.group(1)) if m else None
        return None

    @abstractmethod
    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("引渡時期", "") or specs.get("引渡", "") or specs.get("引き渡し", "")

    @abstractmethod
    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("接道状況", "") or specs.get("接道", "")

    @abstractmethod
    def _parseChimoku(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("地目", "")

    @abstractmethod
    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "")

    @abstractmethod
    def _parseRights(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("権利", "") or specs.get("土地権利", "")

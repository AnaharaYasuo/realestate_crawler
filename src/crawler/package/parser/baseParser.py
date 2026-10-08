import os
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
import datetime
import hashlib
from pathlib import Path
from django.db import models
from package.utils import converter
from package.utils import logging_config  # noqa: F401
from package.utils.property_type_detector import PropertyTypeDetector
from package.utils.url_router import UrlRouter
from package.utils.failure_reporter import FailureReporter
from package.api.differential import ListItem
HTML_PARSER = 'html.parser'
TOKEN_INQUIRY = '/inquiry'
TOKEN_CONTACT = '/contact'
DECIMAL_REGEX = re.compile('([\\d\\.]+)')
DIGIT_REGEX = re.compile('(\\d+)')
WHITESPACE_REGEX = re.compile('\\s+')
_BLANK_SPEC_VALUES = frozenset({'', '-', '－', '―', '—'})
KEY_SHAKUCHIKEN_SHURUI = '借地権種類'
MSG_LISTING_ENDED_PREFIX = 'Listing ended for URL:'

def _is_filled_spec_value(val) -> bool:
    if isinstance(val, dict):
        val = val.get('value')
    if val is None:
        return False
    return str(val).strip() not in _BLANK_SPEC_VALUES

def _is_positive_area(val) -> bool:
    if isinstance(val, dict):
        val = val.get('value')
    if val is None:
        return False
    area = converter.parse_menseki(str(val))
    return area is not None and area > 0

def _spec_has_value(specs, key: str, is_filled=_is_filled_spec_value) -> bool:
    """key と一致、または「key（壁芯）」等の修飾付きラベルのいずれかに値があるか (ラベル内の空白は無視)"""
    qualified = (f'{key}（', f'{key}(')
    for label, val in specs.items():
        if not isinstance(label, str):
            continue
        normalized = WHITESPACE_REGEX.sub('', label)
        if (normalized == key or normalized.startswith(qualified)) and is_filled(val):
            return True
    return False

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

class ListingEndedException(SkipPropertyException):
    """Raised when a property listing has ended."""

class ServerBusyException(SkipPropertyException):
    """Raised when the server is busy."""

class RateLimitedException(Exception):
    """Raised when target server returns HTTP 429 Too Many Requests."""

class ServerDownException(Exception):
    """Raised when target server is down or timing out repeatedly."""

class ParserBase(metaclass=ABCMeta):
    property_type = ''
    sectional_unit_guard_enabled = False
    EXPECTED_SPEC_FIELDS_BY_TYPE = {'mansion': ['price', 'address', 'senyuMenseki', 'madori', 'chikunengetsuStr', 'kouzou'], 'kodate': ['price', 'address', 'tochiMenseki', 'tatemonoMenseki', 'madori', 'chikunengetsuStr', 'kouzou'], 'tochi': ['price', 'address', 'tochiMenseki'], 'investment': ['price', 'address', 'grossYield', 'annualRent', 'kouzou']}
    OPTIONAL_OR_METADATA_FIELDS = {'id', 'pageUrl', 'propertyName', 'priceStr', 'traffic', 'transport1', 'inputDate', 'inputDateTime', 'updateDateTime', 'transfer1', 'railway1', 'station1', 'railwayWalkMinute1Str', 'railwayWalkMinute1', 'busStation1', 'busWalkMinute1Str', 'busWalkMinute1', 'transfer2', 'railway2', 'station2', 'railwayWalkMinute2Str', 'railwayWalkMinute2', 'busStation2', 'busWalkMinute2Str', 'busWalkMinute2', 'transfer3', 'railway3', 'station3', 'railwayWalkMinute3Str', 'railwayWalkMinute3', 'busStation3', 'busWalkMinute3Str', 'busWalkMinute3', 'transfer4', 'railway4', 'station4', 'railwayWalkMinute4Str', 'railwayWalkMinute4', 'busStation4', 'busWalkMinute4Str', 'busWalkMinute4', 'transfer5', 'railway5', 'station5', 'railwayWalkMinute5Str', 'railwayWalkMinute5', 'busStation5', 'busWalkMinute5Str', 'busWalkMinute5', 'railwayCount', 'busUse1', 'busUse2', 'busUse3', 'busUse4', 'busUse5', 'senyuMensekiStr', 'chikunengetsu', 'kanrihiStr', 'kanrihi', 'syuzenTsumitateStr', 'syuzenTsumitate', 'balconyMensekiStr', 'balconyMenseki', 'kaisu', 'kaisuStr', 'soukosu', 'soukosuStr', 'saikou', 'kanriKeitai', 'kanriKaisya', 'tyusyajo', 'tochiMensekiStr', 'tatemonoMensekiStr', 'chikunen', 'genkyo', 'currentStatus', 'tochikenri', 'hikiwatashi', 'biko', 'setsudou', 'chimoku', 'youtoChiiki', 'kenpei', 'kenpeiStr', 'youseki', 'yousekiStr', 'maguchi', 'maguchiStr', 'okuyuki', 'okuyukiStr', 'roadWidth', 'roadWidthStr', 'roadDirection', 'roadType', 'roadStructure', 'monthlyRent', 'propertyType', 'notes', 'rawSpecs', 'chidai', 'chidaiStr', 'douroMuki', 'address1', 'address2', 'address3', 'addressKyoto', 'bikeokiba', 'boukaChiiki', 'buildingCondition', 'bunjoKaisya', 'chiikiChiku', 'chimokuChisei', 'chisei', 'cityPlanning', 'deliveryDate', 'direction', 'douro', 'douroHaba', 'douroKubun', 'facilities', 'floor', 'floorStr', 'floorType_chijo', 'floorType_chika', 'floorType_kai', 'floorType_kouzou', 'isSoldout', 'kadobeya', 'kaisuKouzou', 'kakuninBango', 'kanriKeitaiKaisya', 'kanrihi_p_heibei', 'kenchikuJoken', 'kenpeiYousekiStr', 'kokudoHou', 'kuiki', 'kyutaishin', 'manager', 'neighborhood', 'nextUpdateAt', 'nextUpdateDate', 'otherArea', 'otherFees', 'privateRoadBurden', 'privateRoadFee', 'roofBarukoniMenseki', 'saikenchiku', 'saikouKadobeya', 'saikouMuki', 'saikouMukiStr', 'saikouSaiteki', 'saikouSaitekiStr', 'schoolDistrict', 'sekouKaisya', 'senyouNiwaMenseki', 'setback', 'setsumen', 'shidoMenseki', 'shidoMensekiStr', 'shuzenTsumitate', 'sonotaChiiki', 'sonotaHiyouStr', 'startRoad', 'syuzenTsumitate_p_heibei', 'tatemonoKaisu', 'torihiki', 'totalFloor', 'totalFloorStr', 'transactionType', 'updateDate', 'updatedAt', 'urbanPlanning'}

    @classmethod
    def get_classified_fields(cls, prop_type: str | None=None) -> set:
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
            return ''
        if field in selectors:
            return str(selectors[field])
        s_name = re.sub('(?<!^)(?=[A-Z])', '_', field).lower()
        for candidate in [s_name, f'{s_name}_key', f'{s_name}_selector', f'{field}_key', f'{field}_selector']:
            if candidate in selectors:
                return str(selectors[candidate])
        return ''

    def __init__(self):
        self._specs_cache = {}
        self.selectors = {}
        self.consecutive_timeouts = 0
        self.MAX_CONSECUTIVE_TIMEOUTS = 3
        try:
            env_max_pages = int(os.getenv("MAX_PAGES_PER_JOB", "2000"))
            self.MAX_PAGES_PER_JOB = env_max_pages if env_max_pages > 0 else 2000
        except (ValueError, TypeError):
            self.MAX_PAGES_PER_JOB = 2000

        try:
            env_max_props = int(os.getenv("MAX_PROPERTIES_PER_JOB", "50000"))
            self.MAX_PROPERTIES_PER_JOB = env_max_props if env_max_props > 0 else 50000
        except (ValueError, TypeError):
            self.MAX_PROPERTIES_PER_JOB = 50000

    @abstractmethod
    def getCharset(self):
        pass

    @abstractmethod
    def createEntity(self) -> models.Model:
        return None

    def get_price_str(self, response: BeautifulSoup) -> str:
        """価格(文字列)の抽出"""
        specs = self._get_specs(response)
        price_str = specs.get('価格', '') or specs.get('販売価格', '') or specs.get('物件価格', '')
        if not price_str and response:
            tag = self._getValueByLabel(response, '価格') or self._getValueByLabel(response, '販売価格')
            if tag:
                price_str = tag.get_text(strip=True) if hasattr(tag, 'get_text') else str(tag)
        if not price_str and response:
            el = response.select_one('.price, .mod-price, span.priceNum, td.price, .priceText')
            if el:
                price_str = el.get_text(strip=True)
        # ラベル文字列そのものを値として拾った場合は無効 (#761)
        if price_str in ('価格', '販売価格', '物件価格'):
            return ''
        return price_str

    def get_price(self, response: BeautifulSoup) -> int | Decimal | None:
        """価格(数値)の抽出"""
        price_str = self.get_price_str(response)
        return converter.parse_price(price_str)

    def get_address(self, response: BeautifulSoup) -> str:
        """所在地(住所)の抽出"""
        specs = self._get_specs(response)
        addr = specs.get('所在地', '') or specs.get('住所', '')
        if not addr and response:
            tag = self._getValueByLabel(response, '所在地') or self._getValueByLabel(response, '住所')
            if tag:
                addr = tag.get_text(strip=True) if hasattr(tag, 'get_text') else str(tag)
        if not addr and response:
            el = response.select_one('.address, .mod-address, td.address')
            if el:
                addr = el.get_text(strip=True)
        return addr

    def get_property_name(self, response: BeautifulSoup) -> str:
        """物件名の抽出"""
        specs = self._get_specs(response)
        name = specs.get('物件名', '') or specs.get('名称', '') or specs.get('物件名称', '')
        if not name and response:
            for title_el in response.find_all(['h1', 'h2'], limit=5):
                candidate = title_el.get_text(strip=True)
                if candidate:
                    name = candidate
                    break
        return name

    def get_transport1(self, response: BeautifulSoup) -> str:
        """最寄り駅・交通アクセスの抽出"""
        specs = self._get_specs(response)
        return specs.get('交通', '') or specs.get('最寄り駅', '') or specs.get('沿線・駅', '')

    def get_setsudou(self, response: BeautifulSoup) -> str:
        """接道状況の抽出"""
        specs = self._get_specs(response)
        for key in ['接道状況', '接道', '道路状況', '接道状況・幅員', '道路の状況', '接面状況']:
            if specs.get(key):
                return specs[key]
        if response:
            tag = self._getValueByLabel(response, '接道状況') or self._getValueByLabel(response, '接道')
            if tag:
                return tag.get_text(strip=True) if hasattr(tag, 'get_text') else str(tag)
        return ''

    def get_douro_muki(self, response: BeautifulSoup) -> str:
        """接道方向（道路向き）の抽出"""
        specs = self._get_specs(response)
        for key in ['道路の向き', '道路向き', '接道方向', '接道向き', '方角', '接道方角']:
            if specs.get(key):
                return specs[key]
        setsudou = self.get_setsudou(response)
        if setsudou:
            m = re.search('(北東|北西|南東|南西|東|西|南|北)(?:側|向き|方向)?', setsudou)
            if m:
                return m.group(1)
        return ''

    def get_douro_kubun(self, response: BeautifulSoup) -> str:
        """道路区分の抽出"""
        specs = self._get_specs(response)
        for key in ['道路区分', '道路種別', '公道・私道', '公私区分', '道路区分・種別']:
            if specs.get(key):
                return specs[key]
        setsudou = self.get_setsudou(response)
        if setsudou:
            m = re.search('(公道|私道)', setsudou)
            if m:
                return m.group(1)
        return ''

    @staticmethod
    def _extract_trailing_number(text: str) -> str:
        """Extract trailing digits with optional single dot from text."""
        chars = []
        has_dot = False
        for ch in reversed(text):
            if ch.isdigit():
                chars.append(ch)
            elif ch == '.' and not has_dot:
                has_dot = True
                chars.append(ch)
            else:
                break
        return ''.join(reversed(chars))

    @classmethod
    def _extract_number_before_unit(cls, text: str, units: tuple[str, ...]) -> str:
        """Extract trailing integer/float before any matching unit."""
        for unit in units:
            if unit in text:
                num = cls._extract_trailing_number(text.split(unit)[0])
                if num:
                    return num
        return ''

    def get_douro_haba(self, response: BeautifulSoup) -> str:
        """道路幅員の抽出"""
        specs = self._get_specs(response)
        for key in ['道路幅員', '道路幅', '幅員']:
            val = specs.get(key)
            if val:
                num = self._extract_number_before_unit(val, ('m', 'ｍ'))
                return num or val
        setsudou = self.get_setsudou(response)
        if setsudou:
            clean = setsudou.replace(' ', '').replace('　', '')
            return self._extract_number_before_unit(clean, ('m', 'ｍ'))
        return ''

    def get_hikiwatashi(self, response: BeautifulSoup) -> str:
        """引渡時期の抽出"""
        specs = self._get_specs(response)
        return specs.get('引渡時期', '') or specs.get('引渡', '') or specs.get('引き渡し', '')

    def get_genkyo(self, response: BeautifulSoup) -> str:
        """現況の抽出"""
        specs = self._get_specs(response)
        return specs.get('現況', '') or specs.get('現況状況', '') or specs.get('稼働状況', '') or specs.get('入居状況', '')

    def get_current_status(self, response: BeautifulSoup) -> str:
        """現在のステータス・稼働状況の抽出"""
        return self.get_genkyo(response)

    def get_rights(self, response: BeautifulSoup) -> str:
        """権利関係・借地権等の抽出"""
        specs = self._get_specs(response)
        return specs.get('権利', '') or specs.get('土地権利', '') or specs.get(KEY_SHAKUCHIKEN_SHURUI, '')

    def get_chikunengetsu_str(self, response: BeautifulSoup) -> str:
        """築年月（文字列）の抽出"""
        specs = self._get_specs(response)
        return specs.get('築年月', '') or specs.get('完成時期', '') or specs.get('建築年月', '')

    def get_chikunengetsu(self, response: BeautifulSoup):
        """築年月（日付型）の抽出"""
        s = self.get_chikunengetsu_str(response)
        return converter.parse_chikunengetsu(s) if s else None

    @abstractmethod
    def _parsePrice(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        """価格(数値)の抽出（後方互換委譲）"""
        return self.get_price(response)

    @abstractmethod
    def _parsePriceStr(self, response: BeautifulSoup, specs=None) -> str:
        """価格(文字列)の抽出（後方互換委譲）"""
        return self.get_price_str(response)

    @abstractmethod
    def _parseAddress(self, response: BeautifulSoup, specs=None) -> str:
        """所在地(住所)の抽出（後方互換委譲）"""
        return self.get_address(response)

    @abstractmethod
    def _parsePropertyName(self, response: BeautifulSoup, specs=None) -> str:
        """物件名の抽出（後方互換委譲）"""
        return self.get_property_name(response)

    @abstractmethod
    def _parseTransport1(self, response: BeautifulSoup, specs=None) -> str:
        """最寄り駅・交通アクセスの抽出（後方互換委譲）"""
        return self.get_transport1(response)

    @abstractmethod
    def _parsePropertyDetailPage(self, item: models.Model, response: BeautifulSoup) -> models.Model:
        return item

    def get_chidai_str(self, response: BeautifulSoup) -> str:
        """地代（文字列）の抽出"""
        specs = self._get_specs(response)
        for key in ['借地期間・地代（月額）', '借地期間・地代', '地代（月額）', '地代等', '地代', '借地料（月額）', '借地料', '月額地代', '土地地代']:
            if specs.get(key):
                return specs[key]
        for k, v in specs.items():
            if any(term in k for term in ['地代', '借地料']):
                return v
        if response:
            tag = self._getValueByLabel(response, '地代') or self._getValueByLabel(response, '借地料')
            if tag:
                return tag.get_text(strip=True) if hasattr(tag, 'get_text') else str(tag)
        return ''

    def get_chidai(self, response: BeautifulSoup) -> int | None:
        """地代（月額・数値円）の抽出"""
        chidai_str = self.get_chidai_str(response)
        return converter.parse_chidai(chidai_str)

    def _parseChidaiStr(self, response: BeautifulSoup, specs=None) -> str:
        if specs is not None:
            for key in ['借地期間・地代（月額）', '借地期間・地代', '地代（月額）', '地代等', '地代', '借地料（月額）', '借地料', '月額地代', '土地地代']:
                if specs.get(key):
                    return specs[key]
            for k, v in specs.items():
                if any(term in k for term in ['地代', '借地料']):
                    return v
        return self.get_chidai_str(response)

    def _parseChidai(self, response: BeautifulSoup, specs=None) -> int | None:
        if specs is not None:
            return converter.parse_chidai(self._parseChidaiStr(response, specs))
        return self.get_chidai(response)

    async def parsePropertyListPage(self, response):
        return

    _NOISE_CONTAINER_TAGS = frozenset({'footer', 'nav'})
    _NOISE_CLASS_OR_ID_PATTERNS = ('footer', 'sidebar', 'recommend', 'related-properties', 'related', 'nav-')

    @staticmethod
    def _is_property_context(el) -> bool:
        if not hasattr(el, 'get'):
            return False
        name = getattr(el, 'name', None)
        classes = ' '.join(el.get('class', [])).lower()
        el_id = str(el.get('id', '')).lower()
        return (
            name == 'article'
            or 'property' in classes
            or 'detail' in classes
            or 'bukken' in classes
            or 'property' in el_id
            or 'detail' in el_id
        )

    @classmethod
    def _is_noise_header_or_aside(cls, el) -> bool:
        """Return True if header/aside element is outside article/property context."""
        curr = el
        while curr is not None:
            if cls._is_property_context(curr):
                return False
            curr = getattr(curr, 'parent', None)
        return True

    @classmethod
    def _matches_noise_pattern(cls, el) -> bool:
        if not hasattr(el, 'get'):
            return False
        curr_id = str(el.get('id', '')).lower()
        curr_cls = ' '.join(el.get('class', [])).lower()
        return any(pat in curr_id or pat in curr_cls for pat in cls._NOISE_CLASS_OR_ID_PATTERNS)

    @classmethod
    def _is_in_noise_container(cls, el) -> bool:
        """Return True if element is inside footer, nav, sidebar, or other non-property noise sections."""
        curr = el
        while curr is not None:
            name = getattr(curr, 'name', None)
            if name in cls._NOISE_CONTAINER_TAGS:
                return True
            if (name == 'header' or name == 'aside') and cls._is_noise_header_or_aside(curr):
                return True
            if cls._matches_noise_pattern(curr):
                return True
            curr = getattr(curr, 'parent', None)
        return False

    @staticmethod
    def _put_th_td_pairs(ths, tds, specs: dict) -> None:
        for th, td in zip(ths, tds):
            k = th.get_text(strip=True)
            if k:
                specs[k] = td.get_text(strip=True)

    @classmethod
    def _ingest_tr_specs(cls, response: BeautifulSoup, specs: dict) -> None:
        """Parse th/td rows into specs dict."""
        for tr in response.find_all('tr'):
            if cls._is_in_noise_container(tr):
                continue
            ths = tr.find_all('th')
            tds = tr.find_all('td')
            if not ths or not tds:
                continue
            if len(ths) == len(tds):
                cls._put_th_td_pairs(ths, tds, specs)
            else:
                k = ths[0].get_text(strip=True)
                if k:
                    specs[k] = tds[0].get_text(strip=True)

    @classmethod
    def _ingest_dl_specs(cls, response: BeautifulSoup, specs: dict) -> None:
        """Parse dt/dd pairs into specs dict."""
        for dl in response.find_all('dl'):
            if cls._is_in_noise_container(dl):
                continue
            for dt, dd in zip(dl.find_all('dt'), dl.find_all('dd')):
                k = dt.get_text(strip=True)
                if k:
                    specs[k] = dd.get_text(strip=True)

    @staticmethod
    def _element_text(el) -> str:
        """Safe BeautifulSoup text extract (satisfies Sonar S8904)."""
        get_text = getattr(el, 'get_text', None)
        if not callable(get_text):
            return ''
        return get_text(strip=True)

    @staticmethod
    def _find_row_value_element(row, lbl):
        val = row.select_one('.content, .table-data')
        if val is not None and val is not lbl and hasattr(val, 'get_text'):
            return val
        candidates = [el for el in row.find_all(['td', 'dd']) if el is not lbl and hasattr(el, 'get_text')]
        return candidates[0] if candidates else None

    @classmethod
    def _ingest_table_row_specs(cls, response: BeautifulSoup, specs: dict) -> None:
        """Parse .table-row / div.row style label-value rows into specs dict."""
        for row in response.select('.table-row, div.row, tr.table-row'):
            if cls._is_in_noise_container(row):
                continue
            lbl = row.select_one('.label, .table-header, th, dt')
            if lbl is None or not hasattr(lbl, 'get_text'):
                continue
            val = ParserBase._find_row_value_element(row, lbl)
            if val is None or val is lbl:
                continue
            k = ParserBase._element_text(lbl)
            if k and k not in specs:
                specs[k] = ParserBase._element_text(val)

    def _get_specs(self, response: BeautifulSoup) -> dict:
        """HTML内のth/td, dt/dd, .table-rowテーブルを標準解析し辞書として取得"""
        if not response:
            return {}
        cached = getattr(response, '_cached_specs', None)
        if cached is not None:
            return cached
        specs = {}
        self._ingest_tr_specs(response, specs)
        self._ingest_dl_specs(response, specs)
        self._ingest_table_row_specs(response, specs)
        try:
            response._cached_specs = specs
        except (AttributeError, TypeError):
            pass
        return specs

    def _scrape_specs(self, response: BeautifulSoup) -> dict:
        return self._get_specs(response)

    def _scrape_to_dict(self, response: BeautifulSoup) -> dict:
        return self._get_specs(response)

    def _parsePropertyDetailPage(self, item, _response: BeautifulSoup):
        """Default base detail page parse returning the item entity."""
        return item
    _TOKEN_INQUIRY = TOKEN_INQUIRY
    _TOKEN_CONTACT = TOKEN_CONTACT
    _TOKEN_RENT = '/rent/'
    _TOKEN_CHINTAI = '/chintai/'

    @staticmethod
    def _is_non_property_href(href: str) -> bool:
        """Return True for javascript/mailto/inquiry-style links that are not property pages."""
        if not href or href == '#':
            return True
        if href.startswith(('javascript:', 'mailto:', 'tel:')):
            return True
        skip_tokens = (TOKEN_INQUIRY, TOKEN_CONTACT, '/shiritai/', '/360/', '/benefit/', '/baikyaku/')
        return any(tok in href for tok in skip_tokens)

    @staticmethod
    def _href_fails_rental_filter(href: str, str_xpath: str) -> bool:
        if ParserBase._TOKEN_CHINTAI in str_xpath or ParserBase._TOKEN_RENT in str_xpath:
            return False
        return ParserBase._TOKEN_CHINTAI in href or ParserBase._TOKEN_RENT in href or '/chintai_' in href

    @staticmethod
    def _href_fails_detail_filter(href: str, str_xpath: str) -> bool:
        if 'bkdetail' not in str_xpath and 'detail' not in str_xpath:
            return False
        if 'bkdetail' not in href and 'detail' not in href and ('room' not in href):
            return True
        return '/buy/' in str_xpath and '/buy/' not in href

    @staticmethod
    def _href_fails_xpath_contains(href: str, str_xpath: str) -> bool:
        excluded_subs = re.findall('not\\s*\\(\\s*contains\\s*\\(\\s*@href\\s*,\\s*["\\\']([^"\\\']+)["\\\']\\s*\\)\\s*\\)', str_xpath)
        if excluded_subs and any(sub in href for sub in excluded_subs):
            return True
        clean_xpath = re.sub('not\\s*\\([^)]+\\)', '', str_xpath)
        required_subs = re.findall('contains\\s*\\(\\s*@href\\s*,\\s*["\\\']([^"\\\']+)["\\\']\\s*\\)', clean_xpath)
        if required_subs and (not all(sub in href for sub in required_subs)):
            return True
        starts_with_subs = re.findall('starts-with\\s*\\(\\s*@href\\s*,\\s*["\\\']([^"\\\']+)["\\\']\\s*\\)', clean_xpath)
        return bool(starts_with_subs and (not any(href.startswith(sub) for sub in starts_with_subs)))

    @classmethod
    def _href_fails_xpath_filters(cls, href: str, xpath_pattern) -> bool:
        """Return True when href should be skipped based on xpath-derived filters."""
        if not xpath_pattern:
            return False
        str_xpath = str(xpath_pattern)
        if cls._href_fails_rental_filter(href, str_xpath):
            return True
        if cls._href_fails_detail_filter(href, str_xpath):
            return True
        return cls._href_fails_xpath_contains(href, str_xpath)

    @staticmethod
    def _resolve_http_dest_url(href: str, dest_url_fn) -> str | None:
        """Resolve dest URL via dest_url_fn and return only valid http destinations."""
        try:
            dest_url = dest_url_fn(href) if callable(dest_url_fn) else href
        except Exception:
            return None
        if not dest_url or not isinstance(dest_url, str) or (not dest_url.startswith('http')):
            return None
        bad_tokens = ('javascript:', 'void(0)', TOKEN_INQUIRY, TOKEN_CONTACT)
        if any(tok in dest_url for tok in bad_tokens):
            return None
        if ParserBase._is_non_property_href(dest_url):
            return None
        return dest_url
    _CARD_KEYWORDS = ('card', 'item', 'bukken', 'property', 'list', 'box', 'row', 'section')
    _PRICE_SELECTORS = ('.price', '.mod-price', '.priceNum', '.priceText', 'span[class*="price"]', 'strong[class*="price"]', 'p[class*="price"]', 'td.price', 'em')
    _SIMPLE_PRICE_RE = re.compile(r'(\d[\d,.]*\s*(?:億\s*\d[\d,.]*\s*)?万(?:円)?)')
    _NON_PRICE_UNITS = ('分', '階', '年', '戸', '室', '台')

    @classmethod
    def _is_sub_heading(cls, combined: str) -> bool:
        return any(k in combined for k in ('title', 'heading', 'name')) and not any(k in combined for k in ('card', 'item', 'bukken', 'property'))

    @classmethod
    def _get_combined_tag_info(cls, parent) -> str:
        classes = " ".join(parent.get('class', [])) if isinstance(parent.get('class'), list) else str(parent.get('class', ''))
        tag_id = str(parent.get('id', ''))
        return f"{classes} {tag_id}".lower()

    @classmethod
    def _find_card_container(cls, link):
        parent = link
        first_candidate = None
        for _ in range(6):
            parent = parent.find_parent(['div', 'li', 'tr', 'article', 'section'])
            if parent is None:
                break
            combined = cls._get_combined_tag_info(parent)
            if cls._is_sub_heading(combined):
                continue
            if any(k in combined for k in cls._CARD_KEYWORDS):
                first_candidate = first_candidate or parent
                if any(parent.select_one(sel) for sel in cls._PRICE_SELECTORS):
                    return parent
        return first_candidate or link.parent or link

    @classmethod
    def _parse_valid_price(cls, text: str) -> int | None:
        """テキストから適正価格（100万円以上）を抽出（ノイズ単位除外）"""
        for m in cls._SIMPLE_PRICE_RE.finditer(text):
            after = text[m.end():m.end() + 4]
            if not any(unit in after for unit in cls._NON_PRICE_UNITS):
                p = converter.parse_price(m.group(1))
                if p and p >= 1000000:
                    return p
        return None

    @classmethod
    def _extract_card_price(cls, link) -> int | None:
        """カード要素やその周辺から物件価格（整数・円）を厳格に抽出する (Issue #635: 誤判定完全排除)"""
        if not hasattr(link, 'find_parent'):
            return None
        card = cls._find_card_container(link)

        # 1. card 内の価格専用クラス・要素を探索
        for sel in cls._PRICE_SELECTORS:
            el = card.select_one(sel)
            if el:
                p = cls._parse_valid_price(el.get_text(separator=' ', strip=True))
                if p:
                    return p

        # 2. テキスト全体から価格パターンを抽出
        return cls._parse_valid_price(card.get_text(separator=' ', strip=True))

    async def _parsePageCore(self, response: BeautifulSoup, xpath_fn=None, dest_url_fn=None):
        if not dest_url_fn:
            return
        xpath_pattern = xpath_fn() if callable(xpath_fn) else ''
        for link in response.find_all('a'):
            href = link.get('href')
            if self._is_non_property_href(href):
                continue
            is_class_match = 'sr-card__name' in (link.get('class') or []) and 'sr-card__name' in str(xpath_pattern)
            if not is_class_match and self._href_fails_xpath_filters(href, xpath_pattern):
                continue
            dest_url = self._resolve_http_dest_url(href, dest_url_fn)
            if dest_url:
                price = self._extract_card_price(link)
                yield ListItem(url=dest_url, price=price)

    _SPECIAL_CITY_PREFIXES = ('市川', '市原', '八日市', '四日市', '今市', '武蔵村山', '東村山', '村山', '羽村', '大村', '村上', '十日町', '大町', '町田')
    _TOKYO_WARD_PREFIXES = ('千代田', '中央', '港', '新宿', '文京', '台東', '墨田', '江東', '品川', '目黒', '大田', '世田谷', '渋谷', '中野', '杉並', '豊島', '北', '荒川', '板橋', '練馬', '足立', '葛飾', '江戸川')
    _CITY_PREF_MAP = {'伊勢原市': '神奈川県', '市原市': '千葉県', '市川市': '千葉県', '世田谷区': '東京都', '町田市': '東京都', '武蔵村山市': '東京都', '東村山市': '東京都', '羽村市': '東京都', '荒川区': '東京都', '横浜市中区': '神奈川県'}

    @classmethod
    def _match_gun_town(cls, rest: str) -> str:
        """Match 郡+町村 (e.g. 余市郡余市町) without nested greedy wildcards."""
        gun_idx = rest.find('郡')
        if gun_idx <= 0:
            return ''
        for i in range(gun_idx + 1, len(rest)):
            if rest[i] in ('町', '村'):
                return rest[:i + 1]
        return ''

    @classmethod
    def _match_city_from_rest(cls, rest: str) -> str:
        """Match city/ward from address remainder using literal lists + simple patterns."""
        gun_town = cls._match_gun_town(rest)
        if gun_town:
            return gun_town
        m = re.match('^([^市区町村]+市[^市区町村]+区)', rest)
        if m:
            return m.group(1)
        for name in cls._SPECIAL_CITY_PREFIXES:
            candidate = name + '市'
            if rest.startswith(candidate):
                return candidate
        for name in cls._TOKYO_WARD_PREFIXES:
            candidate = name + '区'
            if rest.startswith(candidate):
                return candidate
        m = re.match('^([^市区町村]+[市区町村])', rest)
        if m:
            return m.group(1)
        m = re.match('^([市区町村][^市区町村]+[市区町村])', rest)
        if m:
            return m.group(1)
        return ''

    def _split_address(self, address_str: str):
        """都道府県・市区町村・町名の自動分割ユーティリティ (市川市・市原市・町田市・武蔵村山市等対応)"""
        if not address_str:
            return ('', '', '')
        pref_match = re.match('^(東京都|北海道|(?:京都|大阪)府|.{2,3}県)', address_str)
        pref = pref_match.group(1) if pref_match else ''
        rest = address_str[len(pref):] if pref else address_str
        city = self._match_city_from_rest(rest)
        town = rest[len(city):] if city else rest
        if not pref and city:
            pref = self._CITY_PREF_MAP.get(city, '')
        return (pref, city, town)

    @staticmethod
    def _apply_walk_minutes(item: models.Model, walk_min: str | None) -> None:
        """Set walkMinutes1 / railwayWalkMinute1 when walk_min is a valid int."""
        if not walk_min:
            return
        try:
            minutes = int(walk_min)
        except Exception:
            return
        if hasattr(item, 'walkMinutes1'):
            item.walkMinutes1 = minutes
        if hasattr(item, 'railwayWalkMinute1'):
            item.railwayWalkMinute1 = minutes

    @staticmethod
    def _normalize_station_name(station: str) -> str:
        station = station.strip('『』「」 ').strip()
        if station.endswith('駅'):
            station = station[:-1].strip()
        return station

    def _apply_railway_station_fields(self, item: models.Model, railway: str | None, station: str, walk_min: str | None) -> None:
        """Apply railway1 / station1 / walk minute fields when unset."""
        station = self._normalize_station_name(station)
        if railway and hasattr(item, 'railway1') and (not getattr(item, 'railway1', None)):
            item.railway1 = railway.strip()
        if hasattr(item, 'station1') and (not getattr(item, 'station1', None)):
            item.station1 = station
        self._apply_walk_minutes(item, walk_min)

    @staticmethod
    def _extract_walk_minutes(text: str) -> str | None:
        """Extract walk minutes from text containing '...N分' without regex backtracking."""
        if '分' not in text:
            return None
        before_fun = text.split('分')[0]
        digits = []
        for ch in reversed(before_fun.rstrip()):
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        return ''.join(reversed(digits)) if digits else None

    def _try_bracket_traffic(self, item: models.Model, traffic_text: str) -> bool:
        """Parse 沿線「駅」徒歩N分 style traffic. Returns True if matched."""
        if '「' not in traffic_text or '」' not in traffic_text:
            return False
        left = traffic_text.find('「')
        right = traffic_text.find('」', left)
        if right <= left:
            return False
        station = traffic_text[left + 1:right].strip()
        before = traffic_text[:left].strip()
        railway = before.split()[-1] if before else None
        walk_min = self._extract_walk_minutes(traffic_text[right + 1:])
        self._apply_railway_station_fields(item, railway, station, walk_min)
        return True

    def _try_space_traffic(self, item: models.Model, traffic_text: str) -> bool:
        """Parse 沿線 駅名駅 徒歩N分 style traffic. Returns True if matched."""
        tokens = traffic_text.replace('/', ' ').split()
        railway_suffixes = ('線', 'ライン', 'ライナー', '鉄道', '本線', '空港線', '地下鉄', 'メトロ', '新幹線')
        for i in range(len(tokens) - 1):
            t0, t1 = tokens[i], tokens[i + 1]
            if any(t0.endswith(s) for s in railway_suffixes) and t1.endswith('駅'):
                walk_min = self._extract_walk_minutes(traffic_text)
                self._apply_railway_station_fields(item, t0, t1, walk_min)
                return True
        return False

    @staticmethod
    def _find_station_candidate(traffic_text: str) -> str | None:
        """Find station/stop name candidate from traffic text."""
        station_suffixes = ('駅', '停留所', 'バス停')
        for t in traffic_text.split():
            for sfx in station_suffixes:
                if sfx in t:
                    idx = t.find(sfx) + len(sfx)
                    candidate = t[:idx].lstrip('「（(').rstrip('」）)')
                    if candidate:
                        return candidate
        return None

    def _try_fallback_station_traffic(self, item: models.Model, traffic_text: str) -> bool:
        """Parse 駅名 徒歩N分 style traffic. Returns True if matched."""
        candidate = self._find_station_candidate(traffic_text)
        if not candidate:
            return False
        station = self._normalize_station_name(candidate)
        walk_min = self._extract_walk_minutes(traffic_text)
        if hasattr(item, 'station1') and (not getattr(item, 'station1', None)):
            item.station1 = station
        if hasattr(item, 'walkMinutes1') and walk_min and (getattr(item, 'walkMinutes1', None) is None):
            try:
                item.walkMinutes1 = int(walk_min)
            except Exception:
                pass
        return True

    def _populateTraffic(self, item: models.Model, traffic_str: str | list) -> models.Model:
        """交通アクセスの自動パース・モデルフィールド設定ユーティリティ"""
        if not traffic_str:
            return item
        if isinstance(traffic_str, list):
            traffic_text = '\n'.join([str(x) for x in traffic_str if x])
        else:
            traffic_text = traffic_str
        item.transport1 = traffic_text
        if self._try_bracket_traffic(item, traffic_text):
            return item
        if self._try_space_traffic(item, traffic_text):
            return item
        self._try_fallback_station_traffic(item, traffic_text)
        return item

    async def getResponseBs(self, session, url: str, charset: str | None=None) -> BeautifulSoup:
        """指定URLのコンテンツを取得し BeautifulSoup (lxml/html.parser) として返す"""
        content = await self._getContent(session, url)
        encoding = charset or self.getCharset() or chardet.detect(content[:4096])['encoding'] or 'utf-8'
        if encoding and str(encoding).lower() in ('shift_jis', 'sjis', 'shift-jis', 'windows-31j'):
            encoding = 'cp932'
        try:
            soup = BeautifulSoup(content, 'lxml', from_encoding=encoding)
            if not soup.find() or len(str(soup)) < 100:
                soup = BeautifulSoup(content, HTML_PARSER, from_encoding=encoding)
            return soup
        except Exception:
            return BeautifulSoup(content, HTML_PARSER, from_encoding=encoding)

    async def getResponse(self, session, url: str, charset: str | None=None) -> BeautifulSoup:
        return await self.getResponseBs(session, url, charset=charset)

    async def parseNextPage(self, response):
        await asyncio.sleep(0)
        return ''

    def _getValueByLabel(self, soup: BeautifulSoup, label: str):
        if not soup or not label:
            return None
        for tag in soup.find_all(['th', 'dt', 'span']):
            txt = tag.get_text(strip=True)
            if not txt:
                continue
            if txt == label or txt.startswith((f"{label}:", f"{label}：")) or txt.strip(" :：【】") == label:
                nxt = tag.find_next_sibling(['td', 'dd', 'span', 'div'])
                if nxt:
                    return nxt
        return None

    @staticmethod
    def _map_property_type_token(pt: str) -> str | None:
        """Map self.property_type token to validation type, or None if unknown."""
        if 'mansion' in pt:
            return 'mansion'
        if 'kodate' in pt and 'invest' not in pt:
            return 'kodate'
        if 'tochi' in pt:
            return 'tochi'
        if 'invest' in pt or 'apartment' in pt:
            return 'investment'
        return None

    @staticmethod
    def _infer_property_type_from_item(item: models.Model) -> str:
        """Infer validation property type from model class / attributes."""
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

    def _resolve_validation_property_type(self, item: models.Model) -> str:
        pt = (getattr(self, 'property_type', '') or '').lower()
        mapped = self._map_property_type_token(pt)
        if mapped:
            return mapped
        return self._infer_property_type_from_item(item)

    @staticmethod
    def _validate_numeric_field_val(val: Any) -> tuple[bool, str]:
        if val is None:
            return (True, 'value is None')
        if isinstance(val, (int, float, Decimal)) and val <= 0:
            return (True, f'invalid non-positive value ({val})')
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ['', 'none', 'null']:
                return (True, 'empty string')
            try:
                if float(s) <= 0:
                    return (True, f'invalid non-positive value string ({val})')
            except ValueError:
                pass
        return (False, '')

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
            return (True, f'annualRent and monthlyRent are both missing or zero (annualRent={rent_val}, monthlyRent={m_rent})')
        return (False, '')

    @staticmethod
    def _validate_general_field_val(val: Any) -> tuple[bool, str]:
        if val is None:
            return (True, 'value is None')
        if isinstance(val, str) and val.strip().lower() in ['', 'none', 'null']:
            return (True, 'empty string')
        return (False, '')

    @staticmethod
    def _is_under_construction_item(item: models.Model) -> bool:
        genkyo = str(getattr(item, 'genkyo', '') or getattr(item, 'currentStatus', '') or '')
        return any(tok in genkyo for tok in ('未完成', '建築中', '新築（未完成）'))

    def _try_menseki_str_fallback(self, item: models.Model, field: str, val) -> bool:
        """Reparse *Str when numeric is empty. Returns True if field should skip validation."""
        str_fallback = {'senyuMenseki': 'senyuMensekiStr', 'tochiMenseki': 'tochiMensekiStr', 'tatemonoMenseki': 'tatemonoMensekiStr'}.get(field)
        if not str_fallback or not hasattr(item, str_fallback):
            return False
        str_val = getattr(item, str_fallback, None)
        if not (isinstance(str_val, str) and str_val.strip()):
            return False
        num_invalid, _ = self._validate_numeric_field_val(val)
        if not num_invalid:
            return True
        parsed = converter.parse_menseki(str_val)
        if parsed is not None:
            setattr(item, field, parsed)
            return True
        return False

    def _validate_field_value(self, item: models.Model, field: str, val) -> tuple[bool, str]:
        if field in ['price', 'senyuMenseki', 'tochiMenseki', 'tatemonoMenseki', 'grossYield']:
            return self._validate_numeric_field_val(val)
        if field == 'annualRent':
            return self._validate_rent_field_val(item, val)
        return self._validate_general_field_val(val)

    def _validate_item_field(self, item: models.Model, field: str) -> Optional[dict]:
        if not hasattr(item, field):
            return None
        val = getattr(item, field, None)
        if self._is_under_construction_item(item) and field in ('tatemonoMenseki', 'chikunengetsuStr'):
            return None
        if self._try_menseki_str_fallback(item, field, val):
            return None
        is_invalid, reason = self._validate_field_value(item, field, val)
        if is_invalid:
            return {'field': field, 'value': str(val) if isinstance(val, Decimal) else val, 'reason': reason, 'selector': self._get_field_selector(getattr(self, 'selectors', {}) or {}, field)}
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
        if errors and (not getattr(item, '_extraction_error_logged', False)):
            item._extraction_error_logged = True
            self._log_extraction_errors(item, prop_type, errors)
        return errors

    def _log_extraction_errors(self, item: models.Model, prop_type: str, errors: list[dict]):
        url = getattr(item, 'pageUrl', '') or 'unknown'
        model_name = item.__class__.__name__
        company = getattr(self, 'company', '') or getattr(self, '__class__', type(self)).__name__
        selectors = getattr(self, 'selectors', {}) or {}
        log_payload = {'event': 'PARSER_EXTRACTION_ERROR', 'url': url, 'propertyName': getattr(item, 'propertyName', '') or '', 'company': company, 'model': model_name, 'property_type': prop_type, 'failed_count': len(errors), 'failed_fields': [e['field'] for e in errors], 'details': errors, 'selectors': selectors}
        logging.error(f'[PARSER_EXTRACTION_ERROR] Property extraction failed for URL: {url} | Payload: {json.dumps(log_payload, ensure_ascii=False, default=str)}')

    @staticmethod
    def _clean_char_text_fields(item: models.Model) -> None:
        """Normalize CharField / TextField values (None/empty guards + whitespace collapse)."""
        for field in item._meta.fields:
            if not isinstance(field, (models.CharField, models.TextField)):
                continue
            val = getattr(item, field.name, None)
            if val is None:
                if not field.null:
                    setattr(item, field.name, '')
                continue
            val_str = str(val).strip()
            if val_str.lower() in ['none', '']:
                setattr(item, field.name, None if field.null else '')
            else:
                setattr(item, field.name, re.sub('\\s+', ' ', val_str))

    @staticmethod
    def _clamp_int32(val_int: int) -> int:
        if val_int > 2147483647:
            return 2147483647
        if val_int < -2147483648:
            return -2147483648
        return val_int

    @classmethod
    def _clean_one_int_field(cls, item: models.Model, int_field_name: str) -> None:
        if not hasattr(item, int_field_name):
            return
        f_obj = item._meta.get_field(int_field_name)
        f_val = getattr(item, int_field_name, None)
        if f_val is None:
            if not f_obj.null:
                setattr(item, int_field_name, 0)
            return
        try:
            val_int = int(f_val)
            if isinstance(f_obj, models.IntegerField) and (not isinstance(f_obj, models.BigIntegerField)):
                val_int = cls._clamp_int32(val_int)
            setattr(item, int_field_name, val_int)
        except (ValueError, TypeError):
            setattr(item, int_field_name, None if f_obj.null else 0)

    @classmethod
    def _clean_int_fields(cls, item: models.Model) -> None:
        for int_field_name in ['price', 'annualRent', 'monthlyRent', 'soukosu', 'chikunen', 'chidai']:
            cls._clean_one_int_field(item, int_field_name)

    def _autofill_chidai_from_soup(self, item: models.Model) -> None:
        soup = getattr(item, '_soup', None)
        if soup is None:
            return
        if hasattr(item, 'chidai') and getattr(item, 'chidai', None) is None:
            c_val = self._parseChidai(soup)
            if c_val is not None:
                setattr(item, 'chidai', c_val)
        if hasattr(item, 'chidaiStr') and (not getattr(item, 'chidaiStr', '')):
            cs_val = self._parseChidaiStr(soup)
            if cs_val:
                setattr(item, 'chidaiStr', cs_val)

    @staticmethod
    def _guard_gross_yield(item: models.Model) -> None:
        if not hasattr(item, 'grossYield'):
            return
        f_obj = item._meta.get_field('grossYield')
        current_yield = getattr(item, 'grossYield', None)
        if current_yield is None or (isinstance(current_yield, (int, float, Decimal)) and current_yield <= 0):
            price = getattr(item, 'price', None)
            annual_rent = getattr(item, 'annualRent', None)
            if not annual_rent and hasattr(item, 'monthlyRent') and getattr(item, 'monthlyRent', None):
                annual_rent = int(item.monthlyRent) * 12
            if price and annual_rent and price > 0 and annual_rent > 0:
                calc_yield = round((float(annual_rent) / float(price)) * 100.0, 2)
                if 0 < calc_yield <= 100.0:
                    setattr(item, 'grossYield', Decimal(str(calc_yield)))
                    return
        if getattr(item, 'grossYield', None) is None and (not f_obj.null):
            setattr(item, 'grossYield', Decimal('0.0'))

    @staticmethod
    def _normalize_station_fields(item: models.Model) -> None:
        for st_field in ['station1', 'station2', 'station3']:
            if not hasattr(item, st_field):
                continue
            st_val = getattr(item, st_field, None)
            if not st_val or not isinstance(st_val, str):
                continue
            cleaned_st = st_val.strip('『』「」 ').strip()
            if cleaned_st.endswith('駅'):
                cleaned_st = cleaned_st[:-1].strip()
            setattr(item, st_field, cleaned_st)

    @staticmethod
    def _sync_genkyo_current_status(item: models.Model) -> None:
        genkyo_val = getattr(item, 'genkyo', None) if hasattr(item, 'genkyo') else None
        curr_val = getattr(item, 'currentStatus', None) if hasattr(item, 'currentStatus') else None
        if genkyo_val and hasattr(item, 'currentStatus') and (not curr_val):
            setattr(item, 'currentStatus', genkyo_val)
        elif curr_val and hasattr(item, 'genkyo') and (not genkyo_val):
            setattr(item, 'genkyo', curr_val)

    def clean_parsed_item(self, item: models.Model) -> models.Model:
        self.validate_extracted_fields(item)
        self._clean_char_text_fields(item)
        self._clean_int_fields(item)
        self._autofill_chidai_from_soup(item)
        self._guard_gross_yield(item)
        self._normalize_station_fields(item)
        self._sync_genkyo_current_status(item)
        return item

    def validate_required_fields(self, item: models.Model):
        errors = []
        if hasattr(item, 'price'):
            p_val = getattr(item, 'price', None)
            if p_val is None or (isinstance(p_val, (int, float, Decimal)) and p_val <= 0):
                errors.append(f'price is invalid or non-positive ({p_val})')
        if hasattr(item, 'address') and (not getattr(item, 'address', '')):
            errors.append('address is empty')
        if errors:
            err_msg = f"StrictExtractionFailed: {', '.join(errors)} for URL: {getattr(item, 'pageUrl', 'unknown')}"
            logging.warning(err_msg)
            raise LoadPropertyPageException(err_msg)

    def save_error_html(self, url: str, content: bytes, reason: str='Parsing failed'):
        """エラー発生時の生HTMLおよびメタデータをdocs/error_pages/およびGCSへ保存"""
        try:
            model_name = self.createEntity().__class__.__name__
            company_type = re.sub('(?<!^)(?=[A-Z])', '_', model_name).lower()
            parts = company_type.split('_', 1)
            comp = parts[0] if parts else 'unknown'
            ptype = parts[1] if len(parts) > 1 else 'unknown'
            try:
                FailureReporter.record_job_failure(company=comp, property_type=ptype, error_type='ParseHtmlError', error_message=reason, target_url=url, exit_code=1, raw_html=content)
            except Exception as fe:
                logging.warning(f'FailureReporter failed in save_error_html: {fe}')
            error_dir = Path('docs/error_pages')
            company_dir = error_dir / company_type
            company_dir.mkdir(parents=True, exist_ok=True)
            base_filename = hashlib.sha256(url.encode('utf-8')).hexdigest()
            html_filepath = company_dir / (base_filename + '.html')
            meta_filepath = company_dir / (base_filename + '_meta.txt')
            with open(html_filepath, 'wb') as f:
                f.write(content)
            with open(meta_filepath, 'w', encoding='utf-8') as f:
                f.write(f"URL: {url}\nReason: {reason}\nTimestamp: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n")
            logging.info(f'Saved error HTML to {company_dir}/{base_filename}')
        except Exception:
            logging.exception('Failed to save error HTML')

    @staticmethod
    def _reject_non_property_url(url) -> None:
        if not url:
            return
        u_lower = str(url).lower()
        skip_parts = ('/shiritai/', '/360/', '/chintai/', '/rent/', TOKEN_INQUIRY, TOKEN_CONTACT, '/benefit/', '/baikyaku/')
        if any(p in u_lower for p in skip_parts):
            logging.debug(f'Fast-skipping non-property/rental URL: {url}')
            raise SkipPropertyException(f'Non-property URL skipped: {url}')

    @staticmethod
    def _detect_content_encoding(content: bytes, charset: str | None) -> str:
        if charset is None:
            encoding = chardet.detect(content[:4096])['encoding'] or 'utf-8'
        else:
            encoding = charset
        if encoding and str(encoding).lower() in ('shift_jis', 'sjis', 'shift-jis', 'windows-31j'):
            return 'cp932'
        return encoding

    @classmethod
    def _soup_from_content(cls, content: bytes, charset: str | None) -> BeautifulSoup:
        encoding = cls._detect_content_encoding(content, charset)
        try:
            soup = BeautifulSoup(content, 'lxml', from_encoding=encoding)
            if not soup.find() or len(str(soup)) < 100:
                soup = BeautifulSoup(content, HTML_PARSER, from_encoding=encoding)
            return soup
        except Exception:
            return BeautifulSoup(content, HTML_PARSER, from_encoding=encoding)

    LISTING_ENDED_TITLE_KEYWORDS: tuple[str, ...] = (
        "掲載終了",
        "掲載が終了",
        "掲載を終了",
        "成約済",
        "ご成約",
        "お探しの物件は見つかりません",
        "お探しのページは見つかりません",
        "お探しのページが見つかりません",
        "物件が見つかりません",
        "存在しないか、掲載が終了",
    )

    LISTING_ENDED_BODY_KEYWORDS: tuple[str, ...] = (
        "掲載が終了したか、成約済みになった可能性があります",
        "お探しの物件は、掲載が終了",
        "お探しの物件は掲載が終了",
        "掲載を終了いたしました",
        "掲載を終了しました",
        "掲載終了物件",
        "ご指定の物件は掲載を終了",
        "指定された物件は掲載を終了",
        "お探しのページは見つかりませんでした",
        "お探しの物件は見つかりませんでした",
        "お探しのページは存在しないか、掲載が終了",
        "現在、掲載を停止しております",
        "この物件は現在掲載されていません",
    )

    @classmethod
    def _clean_notice_soup(cls, soup: BeautifulSoup) -> BeautifulSoup:
        clean_soup = BeautifulSoup(str(soup), "html.parser")
        noise_selectors = (
            "footer, nav, .recommend, .related, .recommend-area, .recommendations, "
            ".ranking-area, .sidebar, .related-properties, .recommended-properties, "
            ".related-links, .other-properties"
        )
        for noise in clean_soup.select(noise_selectors):
            noise.decompose()

        # 告知ボックスまたはリンクテキスト自体が掲載終了通知を含む場合は保持し、それ以外の通常リンクを除去
        err_box_selectors = ".mod-message-end, .not-found, .error-message, .alert-box, .is-ended, .property-ended"
        for a_tag in clean_soup.find_all("a"):
            a_text = WHITESPACE_REGEX.sub("", a_tag.get_text())
            is_notice_link = any(WHITESPACE_REGEX.sub("", kw) in a_text for kw in cls.LISTING_ENDED_BODY_KEYWORDS)
            in_err_box = any(a_tag.find_parent(class_=cls_name.replace(".", "")) for cls_name in err_box_selectors.split(", "))
            if not (in_err_box or is_notice_link):
                a_tag.decompose()
        return clean_soup

    @classmethod
    def _check_body_listing_ended(cls, clean_soup: BeautifulSoup) -> bool:
        err_boxes = clean_soup.select(".mod-message-end, .not-found, .error-message, .alert-box, .is-ended, .property-ended")
        for err_box in err_boxes:
            box_text = WHITESPACE_REGEX.sub(" ", err_box.get_text())
            box_no_space = WHITESPACE_REGEX.sub("", box_text)
            if "成約済" in box_no_space and ("当物件" in box_no_space or "本物件" in box_no_space or "この物件" in box_no_space or "成約済みとなりました" in box_no_space or "ご成約" in box_no_space):
                return True
            if any(WHITESPACE_REGEX.sub("", kw) in box_no_space for kw in cls.LISTING_ENDED_BODY_KEYWORDS):
                return True

        norm_body_no_space = WHITESPACE_REGEX.sub("", clean_soup.get_text())
        return any(WHITESPACE_REGEX.sub("", kw) in norm_body_no_space for kw in cls.LISTING_ENDED_BODY_KEYWORDS)

    @classmethod
    def _raise_if_listing_ended(cls, soup: BeautifulSoup, url) -> None:
        """物件詳細ページが掲載終了・非公開状態の場合に ListingEndedException を送出"""
        title = soup.title.string.strip() if (soup.title and soup.title.string) else ""
        if title:
            cls._raise_on_listing_title(title, url)

        clean_soup = cls._clean_notice_soup(soup.body or soup)

        # 対象物件の告知領域内にある h1 要素を検査（関連物件やフッターの見出しは除外）
        for h1_tag in clean_soup.find_all("h1"):
            h1_text = h1_tag.get_text().strip()
            if any(kw in h1_text for kw in cls.LISTING_ENDED_TITLE_KEYWORDS):
                logging.debug(f"{MSG_LISTING_ENDED_PREFIX} {url}")
                raise ListingEndedException(f"{MSG_LISTING_ENDED_PREFIX} {url}")

        if cls._check_body_listing_ended(clean_soup):
            logging.debug(f"{MSG_LISTING_ENDED_PREFIX} {url}")
            raise ListingEndedException(f"{MSG_LISTING_ENDED_PREFIX} {url}")

    @classmethod
    def _raise_on_listing_title(cls, title: str, url) -> None:
        if not title:
            return
        if "サーバーが混み合っています" in title:
            logging.debug(f"Server busy for URL: {url}")
            raise ServerBusyException()
        if any(kw in title for kw in cls.LISTING_ENDED_TITLE_KEYWORDS):
            logging.debug(f"{MSG_LISTING_ENDED_PREFIX} {url}")
            raise ListingEndedException(f"{MSG_LISTING_ENDED_PREFIX} {url}")

    @staticmethod
    def _is_sectional_unit_page(specs) -> bool:
        """専有面積 (正の数値) があり土地面積が無いスペック表は区分所有の住戸とみなす"""
        if not specs:
            return False
        return _spec_has_value(specs, '専有面積', _is_positive_area) and (not _spec_has_value(specs, '土地面積'))

    def _senyu_area_outside_specs(self, soup) -> str:
        """スペック表以外 (サマリー等) に記載された専有面積。サイト固有の記載位置はサブクラスで返す"""
        return ''

    def _is_sectional_unit(self, specs, soup) -> bool:
        if self._is_sectional_unit_page(specs):
            return True
        has_land_area = bool(specs) and _spec_has_value(specs, '土地面積')
        return not has_land_area and _is_positive_area(self._senyu_area_outside_specs(soup))

    def _maybe_switch_parser(self, url, title: str, soup: BeautifulSoup, specs: dict, item: models.Model):
        """Switch to a different parser when detected property type differs. Returns (parser, item)."""
        detected_type = PropertyTypeDetector.detect(url=url, title=title, html_text=soup.get_text()[:2000], specs=specs, default=self.property_type)
        if not (detected_type and self.property_type and (detected_type != self.property_type)):
            return (self, item)
        if self.sectional_unit_guard_enabled and self.property_type == 'mansion' and self._is_sectional_unit(specs, soup):
            logging.info(f"[PropertyTypeSwitch] URL {url}: expected '{self.property_type}' -> detected '{detected_type}' skipped (sectional unit)")
            return (self, item)
        target_parser = UrlRouter.create_parser(url=url, title=title, html_text=soup.get_text()[:2000], specs=specs, property_type=detected_type)
        if not target_parser or target_parser.__class__ == self.__class__:
            return (self, item)
        logging.info(f"[PropertyTypeSwitch] URL {url}: expected '{self.property_type}' ({self.__class__.__name__}) -> detected '{detected_type}' ({target_parser.__class__.__name__})")
        new_item = target_parser.createEntity()
        new_item.pageUrl = url
        return (target_parser, new_item)

    async def parsePropertyDetailPage(self, session, url) -> models.Model:
        """物件詳細ページを取得・動的種別判定を行い、適切なパーサーでパースしてモデルインスタンスを返却"""
        self._reject_non_property_url(url)
        item: models.Model = self.createEntity()
        content = None
        try:
            item.pageUrl = url
            content = await self._getContent(session, url)
            soup = self._soup_from_content(content, self.getCharset())
            title = soup.title.string if soup.title else ''
            self._raise_if_listing_ended(soup, url)
            specs = self._get_specs(soup)
            parser_to_use, item = self._maybe_switch_parser(url, title, soup, specs, item)
            item = parser_to_use._parsePropertyDetailPage(item, soup)
            item = parser_to_use.clean_parsed_item(item)
            item._soup = soup
            parser_to_use.validate_required_fields(item)
        except SkipPropertyException:
            raise
        except (LoadPropertyPageException, TimeoutError):
            logging.exception(f'Failure loading page: {url}')
            raise
        except Exception as e:
            msg = f'Can not read property page: {url} - Reason: {str(e)}'
            logging.exception(msg)
            if content:
                self.save_error_html(url, content, reason=str(e))
            raise LoadPropertyPageException(msg)
        return item

    @staticmethod
    def _validate_http_status(status: int, url: str) -> None:
        """HTTPレスポンスステータスに応じた適切な例外を送出"""
        if status in (404, 410):
            raise ListingEndedException(f'Property page returned HTTP status {status}: {url}')
        if status == 429:
            raise RateLimitedException(f'HTTP Status 429 Too Many Requests: {url}')
        if status == 403:
            raise LoadPropertyPageException(f'HTTP Status 403 Forbidden (Possible WAF/Bot Protection): {url}')
        if status in (500, 502, 503, 504):
            raise ServerBusyException(f'Property page returned HTTP status {status}: {url}')
        raise LoadPropertyPageException(f'HTTP Status {status}: {url}')

    async def _getContent(self, session: aiohttp.ClientSession, url: str) -> bytes:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        max_timeouts = getattr(self, 'MAX_CONSECUTIVE_TIMEOUTS', 3)
        for attempt in range(max_timeouts):
            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status == 200:
                        self.consecutive_timeouts = 0
                        return await response.read()
                    self._validate_http_status(response.status, url)
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                cur_timeouts = getattr(self, 'consecutive_timeouts', 0) + 1
                self.consecutive_timeouts = cur_timeouts
                if cur_timeouts >= max_timeouts:
                    raise ServerDownException(f'Target server is down or timing out repeatedly ({cur_timeouts} times)') from e
                if attempt == self.MAX_CONSECUTIVE_TIMEOUTS - 1:
                    raise LoadPropertyPageException(f'Timeout after {attempt + 1} attempts for URL: {url}') from e
                await asyncio.sleep(1 * (attempt + 1))
        return b''

class MansionParserBase(ParserBase):
    """
    マンション用基底パーサークラス
    """
    property_type = 'mansion'

    def get_senyu_menseki_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('専有面積', '') or specs.get('壁芯面積', '') or specs.get('建物面積', '')

    def get_senyu_menseki(self, response: BeautifulSoup) -> Decimal | None:
        val = self.get_senyu_menseki_str(response)
        return converter.parse_menseki(val) if val else None

    def get_madori(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('間取り', '') or specs.get('間取', '')

    def get_chikunengetsu_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('築年月', '') or specs.get('完成時期', '') or specs.get('建築年月', '')

    def get_chikunengetsu(self, response: BeautifulSoup):
        s = self.get_chikunengetsu_str(response)
        return converter.parse_chikunengetsu(s) if s else None

    def get_kouzou(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('構造', '') or specs.get('建物構造', '')

    def get_kaisu_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('階数', '') or specs.get('所在階', '') or specs.get('階', '') or specs.get('所在階／階数', '')

    def get_floor(self, response: BeautifulSoup) -> int | None:
        s = self.get_kaisu_str(response)
        if s:
            m = DIGIT_REGEX.search(s)
            return int(m.group(1)) if m else None
        return None

    def get_soukosu_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('総戸数', '') or specs.get('総区画数', '')

    def get_soukosu(self, response: BeautifulSoup) -> int | None:
        val = self.get_soukosu_str(response)
        if val:
            m = DIGIT_REGEX.search(val)
            return int(m.group(1)) if m else None
        return None

    def get_management_fee_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('管理費', '') or specs.get('管理費等', '')

    def get_management_fee(self, response: BeautifulSoup) -> int | Decimal | None:
        val = self.get_management_fee_str(response)
        return converter.parse_yen(val) if val else None

    def get_reserve_fund_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('修繕積立金', '') or specs.get('修繕積立金等', '')

    def get_reserve_fund(self, response: BeautifulSoup) -> int | Decimal | None:
        val = self.get_reserve_fund_str(response)
        return converter.parse_yen(val) if val else None

    def get_balcony_menseki_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('バルコニー面積', '') or specs.get('バルコニー', '')

    def get_balcony_menseki(self, response: BeautifulSoup) -> Decimal | None:
        val = self.get_balcony_menseki_str(response)
        return converter.parse_menseki(val) if val else None

    def get_kenpei(self, response: BeautifulSoup) -> int | None:
        specs = self._get_specs(response)
        val = specs.get('建ぺい率', '') or specs.get('建蔽率', '')
        if val:
            m = DIGIT_REGEX.search(val)
            return int(m.group(1)) if m else None
        return None

    def get_youseki(self, response: BeautifulSoup) -> int | None:
        specs = self._get_specs(response)
        val = specs.get('容積率', '')
        if val:
            m = DIGIT_REGEX.search(val)
            return int(m.group(1)) if m else None
        return None

    def get_hikiwatashi(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('引渡時期', '') or specs.get('引渡', '') or specs.get('引き渡し', '')

    def get_genkyo(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('現況', '') or specs.get('現況状況', '')

    def get_current_status(self, response: BeautifulSoup) -> str:
        return self.get_genkyo(response)

    def get_rights(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('権利', '') or specs.get('土地権利', '') or specs.get(KEY_SHAKUCHIKEN_SHURUI, '')

    def get_youto_chiiki(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('用途地域', '')

    @abstractmethod
    def _parseSenyuMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        return self.get_senyu_menseki(response)

    @abstractmethod
    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_madori(response)

    @abstractmethod
    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        return self.get_chikunengetsu(response)

    @abstractmethod
    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_kouzou(response)

    @abstractmethod
    def _parseFloor(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_kaisu_str(response)

    @abstractmethod
    def _parseSouKosu(self, response: BeautifulSoup, specs=None) -> int | None:
        return self.get_soukosu(response)

    @abstractmethod
    def _parseManagementFee(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        return self.get_management_fee(response)

    @abstractmethod
    def _parseReserveFund(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        return self.get_reserve_fund(response)

    @abstractmethod
    def _parseKenpei(self, response: BeautifulSoup, specs=None) -> int | None:
        return self.get_kenpei(response)

    @abstractmethod
    def _parseYouseki(self, response: BeautifulSoup, specs=None) -> int | None:
        return self.get_youseki(response)

    @abstractmethod
    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_hikiwatashi(response)

    @abstractmethod
    def _parseGenkyo(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_genkyo(response)

    @abstractmethod
    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_current_status(response)

    @abstractmethod
    def _parseRights(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_rights(response)

    @abstractmethod
    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_youto_chiiki(response)

class KodateParserBase(ParserBase):
    """
    戸建て用基底パーサークラス
    """
    property_type = 'kodate'

    def get_tochi_menseki_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('土地面積', '') or specs.get('区画面積', '') or specs.get('敷地面積', '')

    def get_tochi_menseki(self, response: BeautifulSoup) -> Decimal | None:
        val = self.get_tochi_menseki_str(response)
        return converter.parse_menseki(val) if val else None

    def get_tatemono_menseki_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('建物面積', '') or specs.get('延床面積', '')

    def get_tatemono_menseki(self, response: BeautifulSoup) -> Decimal | None:
        val = self.get_tatemono_menseki_str(response)
        return converter.parse_menseki(val) if val else None

    def get_chikunengetsu_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('築年月', '') or specs.get('完成時期', '')

    def get_chikunengetsu(self, response: BeautifulSoup):
        s = self.get_chikunengetsu_str(response)
        return converter.parse_chikunengetsu(s) if s else None

    def get_madori(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('間取り', '') or specs.get('間取', '')

    def get_kouzou(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('構造', '') or specs.get('建物構造', '')

    def get_kenpei_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('建ぺい率', '') or specs.get('建蔽率', '')

    def get_kenpei(self, response: BeautifulSoup) -> int | None:
        val = self.get_kenpei_str(response)
        if val:
            m = DIGIT_REGEX.search(val)
            return int(m.group(1)) if m else None
        return None

    def get_youseki_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('容積率', '')

    def get_youseki(self, response: BeautifulSoup) -> int | None:
        val = self.get_youseki_str(response)
        if val:
            m = DIGIT_REGEX.search(val)
            return int(m.group(1)) if m else None
        return None

    def get_rights(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('権利', '') or specs.get('土地権利', '') or specs.get(KEY_SHAKUCHIKEN_SHURUI, '')

    def get_youto_chiiki(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('用途地域', '')

    def get_hikiwatashi(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('引渡時期', '') or specs.get('引渡', '') or specs.get('引き渡し', '')

    def get_genkyo(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('現況', '') or specs.get('現況状況', '')

    def get_current_status(self, response: BeautifulSoup) -> str:
        return self.get_genkyo(response)

    def get_chimoku(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('地目', '')

    @abstractmethod
    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        return self.get_tochi_menseki(response)

    @abstractmethod
    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        return self.get_tatemono_menseki(response)

    @abstractmethod
    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        return self.get_chikunengetsu(response)

    @abstractmethod
    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_madori(response)

    @abstractmethod
    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_kouzou(response)

    @abstractmethod
    def _parseKenpei(self, response: BeautifulSoup, specs=None) -> int | None:
        return self.get_kenpei(response)

    @abstractmethod
    def _parseYouseki(self, response: BeautifulSoup, specs=None) -> int | None:
        return self.get_youseki(response)

    @abstractmethod
    def _parseRights(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_rights(response)

    @abstractmethod
    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_youto_chiiki(response)

    @abstractmethod
    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_setsudou(response)

    @abstractmethod
    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_hikiwatashi(response)

    @abstractmethod
    def _parseGenkyo(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_genkyo(response)

    @abstractmethod
    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_current_status(response)

    def _parseChimoku(self, response: BeautifulSoup, _specs=None) -> str:
        return self.get_chimoku(response)

class TochiParserBase(ParserBase):
    """
    土地用基底パーサークラス
    """
    property_type = 'tochi'

    def get_tochi_menseki_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('土地面積', '') or specs.get('区画面積', '') or specs.get('敷地面積', '') or specs.get('面積', '')

    def get_tochi_menseki(self, response: BeautifulSoup) -> Decimal | None:
        val = self.get_tochi_menseki_str(response)
        return converter.parse_menseki(val) if val else None

    def get_kenpei_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('建ぺい率', '') or specs.get('建蔽率', '')

    def get_kenpei(self, response: BeautifulSoup) -> int | None:
        val = self.get_kenpei_str(response)
        if val:
            m = DIGIT_REGEX.search(val)
            return int(m.group(1)) if m else None
        return None

    def get_youseki_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('容積率', '')

    def get_youseki(self, response: BeautifulSoup) -> int | None:
        val = self.get_youseki_str(response)
        if val:
            m = DIGIT_REGEX.search(val)
            return int(m.group(1)) if m else None
        return None

    def get_chimoku(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('地目', '')

    def get_rights(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('権利', '') or specs.get('土地権利', '')

    def get_youto_chiiki(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('用途地域', '')

    @staticmethod
    def _extract_maguchi_decimal(val: str) -> Decimal | None:
        if not val:
            return None
        match = re.search('(?:(?:間口|約|幅員|道路)\\s*)?(\\d{1,5}(?:\\.\\d{1,3})?)\\s*[mｍ]', val)
        if match:
            try:
                return Decimal(match.group(1))
            except Exception:
                pass
        return None

    def get_maguchi(self, response: BeautifulSoup) -> Decimal | None:
        specs = self._get_specs(response)
        val = specs.get('間口', '') or specs.get('接道状況', '') or specs.get('接道', '')
        if not val and response:
            tag = self._getValueByLabel(response, '間口') or self._getValueByLabel(response, '接道')
            if tag:
                val = tag.get_text(strip=True) if hasattr(tag, 'get_text') else str(tag)
        return self._extract_maguchi_decimal(val)

    def get_hikiwatashi(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('引渡時期', '') or specs.get('引渡', '') or specs.get('引き渡し', '')

    def get_genkyo(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('現況', '') or specs.get('現況状況', '')

    def get_current_status(self, response: BeautifulSoup) -> str:
        return self.get_genkyo(response)

    def get_kaisu_str(self, _response: BeautifulSoup) -> str:
        """土地には階数が存在しないため常に空文字を返す"""
        return ''

    @abstractmethod
    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        return self.get_tochi_menseki(response)

    @abstractmethod
    def _parseKenpei(self, response: BeautifulSoup, specs=None) -> int | None:
        return self.get_kenpei(response)

    @abstractmethod
    def _parseYouseki(self, response: BeautifulSoup, specs=None) -> int | None:
        return self.get_youseki(response)

    @abstractmethod
    def _parseChimoku(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_chimoku(response)

    @abstractmethod
    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_setsudou(response)

    @abstractmethod
    def _parseRights(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_rights(response)

    @abstractmethod
    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_youto_chiiki(response)

    @abstractmethod
    def _parseMaguchi(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        return self.get_maguchi(response)

    @abstractmethod
    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_hikiwatashi(response)

    @abstractmethod
    def _parseGenkyo(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_genkyo(response)

    @abstractmethod
    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_current_status(response)

class InvestmentParserBase(ParserBase):
    """
    投資用物件用基底パーサークラス
    """
    property_type = 'investment'

    def get_gross_yield_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('表面利回り', '') or specs.get('利回り', '') or specs.get('想定利回り', '')

    def get_gross_yield(self, response: BeautifulSoup) -> Decimal | None:
        val = self.get_gross_yield_str(response)
        if val:
            m = DECIMAL_REGEX.search(val)
            return Decimal(m.group(1)) if m else None
        return None

    def get_annual_rent_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('年間予定収入', '') or specs.get('満室時想定年収', '') or specs.get('年間収入', '') or specs.get('年収', '')

    def get_annual_rent(self, response: BeautifulSoup) -> int | Decimal | None:
        val = self.get_annual_rent_str(response)
        return converter.parse_price(val) if val else None

    def get_monthly_rent_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('月額収入', '') or specs.get('家賃', '')

    def get_monthly_rent(self, response: BeautifulSoup) -> int | Decimal | None:
        val = self.get_monthly_rent_str(response)
        return converter.parse_price(val) if val else None

    def get_genkyo(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('稼働状況', '') or specs.get('入居状況', '') or specs.get('現況', '')

    def get_current_status(self, response: BeautifulSoup) -> str:
        return self.get_genkyo(response)

    def get_chikunengetsu_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('築年月', '') or specs.get('完成時期', '')

    def get_chikunengetsu(self, response: BeautifulSoup):
        s = self.get_chikunengetsu_str(response)
        return converter.parse_chikunengetsu(s) if s else None

    def get_kouzou(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('構造', '') or specs.get('建物構造', '')

    def get_tochi_menseki_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('土地面積', '') or specs.get('区画面積', '') or specs.get('敷地面積', '')

    def get_tochi_menseki(self, response: BeautifulSoup) -> Decimal | None:
        val = self.get_tochi_menseki_str(response)
        return converter.parse_menseki(val) if val else None

    def get_tatemono_menseki_str(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('建物面積', '') or specs.get('延床面積', '')

    def get_tatemono_menseki(self, response: BeautifulSoup) -> Decimal | None:
        val = self.get_tatemono_menseki_str(response)
        return converter.parse_menseki(val) if val else None

    def get_hikiwatashi(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('引渡時期', '') or specs.get('引渡', '') or specs.get('引き渡し', '')

    def get_chimoku(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('地目', '')

    def get_youto_chiiki(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('用途地域', '')

    def get_rights(self, response: BeautifulSoup) -> str:
        specs = self._get_specs(response)
        return specs.get('権利', '') or specs.get('土地権利', '')

    @abstractmethod
    def _parseGrossYield(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        return self.get_gross_yield(response)

    @abstractmethod
    def _parseAnnualRent(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        return self.get_annual_rent(response)

    @abstractmethod
    def _parseMonthlyRent(self, response: BeautifulSoup, specs=None) -> int | Decimal | None:
        return self.get_monthly_rent(response)

    @abstractmethod
    def _parseGenkyo(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_genkyo(response)

    @abstractmethod
    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_current_status(response)

    @abstractmethod
    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        return self.get_chikunengetsu(response)

    @abstractmethod
    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_kouzou(response)

    @abstractmethod
    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        return self.get_tochi_menseki(response)

    @abstractmethod
    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None) -> Decimal | None:
        return self.get_tatemono_menseki(response)

    @abstractmethod
    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_hikiwatashi(response)

    @abstractmethod
    def _parseSetsudou(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_setsudou(response)

    @abstractmethod
    def _parseChimoku(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_chimoku(response)

    @abstractmethod
    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_youto_chiiki(response)

    @abstractmethod
    def _parseRights(self, response: BeautifulSoup, specs=None) -> str:
        return self.get_rights(response)
"""
ML 特徴量抽出用 各種属性パーサー・日付計算・数値変換モジュール (Issue #713, Epic #710)
"""
import datetime
import re
import unicodedata
from decimal import Decimal
from typing import Any


_KOUZOU_STEEL_KEYWORDS = ('鉄骨', '重量鉄骨', '軽量鉄骨', 'S造')
_KOUZOU_RC_KEYWORDS = ('RC', '鉄筋コンクリート', '鉄筋', 'PC', 'プレキャスト')
_KOUZOU_S_FALLBACK_KEYWORDS = ('コンクリート', 'ブロック', 'ALC')


def parse_kouzou(kouzou_str: str | None) -> str:
    """構造文字列から構造カテゴリを分類 (全角・表記揺れをNFKC正規化) (Issue #1281)"""
    if not kouzou_str:
        return 'default'
    k_norm = unicodedata.normalize('NFKC', str(kouzou_str)).upper()
    # 鉄骨造（PC板葺）など屋根・外壁付属のPC/ALCが主構造に誤判定されるのを防ぐため、主構造のS/RCを先見
    if 'SRC' in k_norm or '鉄骨鉄筋' in k_norm:
        return 'SRC'
    if any(kw in k_norm for kw in _KOUZOU_STEEL_KEYWORDS) or k_norm.startswith('S'):
        return 'LS' if ('軽量' in k_norm or 'LS' in k_norm) else 'S'
    if any(kw in k_norm for kw in _KOUZOU_RC_KEYWORDS):
        return 'RC'
    if '木' in k_norm or 'W造' in k_norm:
        return 'W'
    if any(kw in k_norm for kw in _KOUZOU_S_FALLBACK_KEYWORDS):
        return 'S'
    return 'default'


def parse_road_direction_features(direction_str: str) -> dict[str, float]:
    """接道方角の数値化（方位角度数、日照採光スコア、南向きフラグ）"""
    d = str(direction_str or "")
    angles = {
        '北': 0.0, '北東': 45.0, '東': 90.0, '南東': 135.0,
        '南': 180.0, '南西': 225.0, '西': 270.0, '北西': 315.0
    }
    sunlight = {
        '南': 1.00, '南東': 0.95, '南西': 0.95, '東': 0.90,
        '西': 0.85, '北東': 0.80, '北西': 0.80, '北': 0.75
    }
    angle = 180.0
    sun = 0.88
    is_south = 0.0
    for k in ['南東', '南西', '北東', '北西', '南', '東', '西', '北']:
        if k in d:
            angle = angles[k]
            sun = sunlight[k]
            is_south = 1.0 if '南' in k else 0.0
            break
    return {
        "road_direction_angle": angle,
        "sunlight_score": sun,
        "is_south_facing": is_south
    }


def parse_road_type_features(type_str: str) -> dict[str, float]:
    """道路種別の数値化（公道・私道・位置指定スコア）"""
    t = str(type_str or "")
    if "公道" in t:
        score = 1.00
        is_pub = 1.0
        is_pri = 0.0
    elif "位置指定" in t:
        score = 0.95
        is_pub = 0.0
        is_pri = 1.0
    elif "私道" in t:
        score = 0.90
        is_pub = 0.0
        is_pri = 1.0
    else:
        score = 0.90
        is_pub = 0.0
        is_pri = 0.0
    return {
        "road_type_score": score,
        "is_public_road": is_pub,
        "is_private_road": is_pri
    }


def parse_road_structure_features(struct_str: str) -> dict[str, float]:
    """接道形態・状況の数値化（角地・両面道路プレミアム）"""
    s = str(struct_str or "")
    if "四方" in s:
        score = 1.15
        is_corner = 1.0
        is_double = 1.0
    elif "三方" in s:
        score = 1.10
        is_corner = 1.0
        is_double = 1.0
    elif "角地" in s or "準角地" in s:
        score = 1.08 if "角地" in s else 1.04
        is_corner = 1.0
        is_double = 0.0
    elif "両面" in s or "二方" in s:
        score = 1.06
        is_corner = 0.0
        is_double = 1.0
    elif any(k in s for k in ["袋地", "無道路", "通路"]):
        score = 0.75
        is_corner = 0.0
        is_double = 0.0
    else:
        score = 1.00
        is_corner = 0.0
        is_double = 0.0
    return {
        "road_structure_score": score,
        "is_corner_lot": is_corner,
        "is_double_sided_road": is_double
    }


def parse_chimoku_features(chimoku_str: str) -> dict[str, float]:
    """地目の数値化（実データ分析に基づくディスカウント率反映） (Issue #1294)

    全国4.8万件の本番土地データにおける同一市区町村内実勢坪単価中央値比率:
    - 宅地: 1.00
    - 畑: 0.94
    - 未設定: 0.95
    - 雑種地: 0.92
    - 現況宅地(登記他): 0.90
    - 原野: 0.77
    - 山林: 0.68
    - 田: 0.63
    - その他(保安林等): 0.50
    """
    c = str(chimoku_str or "").strip()
    if "現況：宅地" in c or "現況地目：宅地" in c:
        score = 0.90
        is_res = 1.0
    elif "宅地" in c:
        score = 1.00
        is_res = 1.0
    elif "雑種" in c:
        score = 0.92
        is_res = 0.0
    elif "畑" in c:
        score = 0.94
        is_res = 0.0
    elif "原野" in c:
        score = 0.77
        is_res = 0.0
    elif "山林" in c:
        score = 0.68
        is_res = 0.0
    elif "田" in c or "農地" in c:
        score = 0.63
        is_res = 0.0
    elif not c or c in ("-", "－"):
        score = 0.95
        is_res = 1.0
    else:
        score = 0.50
        is_res = 0.0
    return {
        "chimoku_score": score,
        "is_residential_chimoku": is_res
    }


def parse_kouzou_features(kouzou_str: str) -> dict[str, float]:
    """建物構造の数値化（耐久ランク、耐火スコア、RC/木造フラグ）"""
    k = str(kouzou_str or "").upper()
    cat = parse_kouzou(kouzou_str)
    if cat == 'SRC':
        rank = 5.0
        fireproof = 1.00
        is_rc = 1.0
        is_w = 0.0
    elif cat == 'RC':
        rank = 4.0
        fireproof = 1.00
        is_rc = 1.0
        is_w = 0.0
    elif cat == 'S':
        rank = 3.0
        fireproof = 0.80
        is_rc = 0.0
        is_w = 0.0
    elif cat == 'LS':
        rank = 2.0
        fireproof = 0.70
        is_rc = 0.0
        is_w = 0.0
    elif cat == 'W' or '木' in k:
        rank = 1.0
        fireproof = 0.60
        is_rc = 0.0
        is_w = 1.0
    else:
        rank = 2.5
        fireproof = 0.70
        is_rc = 0.0
        is_w = 0.0
    return {
        "kouzou_durability_rank": rank,
        "kouzou_fireproof_score": fireproof,
        "is_rc_or_src": is_rc,
        "is_wood": is_w
    }


MAJOR_FOUR = ["mitsui", "sumifu", "sumitomo", "nomura", "tokyu", "三井", "住友", "野村", "東急"]
HOUSE_MAKERS = [
    "misawa", "daiwa", "sekisui", "asahi", "daikyo", "smtrc", "mizuho", "sumai1", "sumirin", "heim", "haseko",
    "ミサワ", "大和", "積水", "旭化成", "大京", "住友林業", "セキスイハイム", "長谷工",
]
BRAND_TIER3 = ["パーク", "シティタワー", "シティテラス", "シティハウス", "グランドメゾン", "プラウド", "ブランズ"]
BRAND_TIER2 = ["ライオンズ", "プレミスト", "ヘーベル", "ダイワハウス"]


def parse_company_features(company_str: str) -> dict[str, float]:
    """不動産会社・分譲ブランドの数値化（大手ティア・ブランド力）"""
    c = str(company_str or "").lower()
    if any(m in c for m in MAJOR_FOUR) or any(b in c for b in BRAND_TIER3):
        tier = 3.0
        is_major = 1.0
    elif any(h in c for h in HOUSE_MAKERS) or any(b in c for b in BRAND_TIER2):
        tier = 2.0
        is_major = 0.0
    else:
        tier = 1.0
        is_major = 0.0
    return {
        "company_tier": tier,
        "is_major_company": is_major
    }


_CACHED_SITE_KEYS: list[str] | None = None


def resolve_company_name(property_obj: Any) -> str:
    """物件オブジェクト・辞書から会社名・ブランド名を解決 (Issue #1279)"""
    global _CACHED_SITE_KEYS
    # 1. 直接指定された company
    c = _get_attr(property_obj, 'company', None)
    if c and str(c).strip() and str(c).lower() != 'unknown':
        return str(c).strip()

    # 2. モデルクラス名から解決
    cls_name = getattr(property_obj, '__class__', type(None)).__name__
    if _CACHED_SITE_KEYS is None:
        from package.site_registry import SiteRegistry
        _CACHED_SITE_KEYS = sorted(SiteRegistry.get_all_sites().keys(), key=len, reverse=True)
    sites = _CACHED_SITE_KEYS
    name_lower = cls_name.lower()
    matched_site = next((s for s in sites if name_lower.startswith(s) or s in name_lower), None)
    if matched_site and matched_site not in ('athome', 'homes'):
        return matched_site

    # 3. ブランド名（物件名・分譲会社等）
    for field in ('bunjoKaisya', 'sekouKaisya', 'kanriKaisya', 'propertyName'):
        val = _get_attr(property_obj, field, None)
        if val and str(val).strip():
            val_str = str(val).strip()
            val_lower = val_str.lower()
            if any(k in val_lower for k in MAJOR_FOUR + HOUSE_MAKERS + BRAND_TIER3 + BRAND_TIER2):
                return val_str

    if matched_site:
        return matched_site

    return 'unknown'


def parse_youto_zone_features(youto_str: str) -> dict[str, float]:
    """用途地域規制の数値化（住居・商業・工業系フラグおよび住環境ランク）"""
    y = str(youto_str or "")
    is_res = 1.0 if any(k in y for k in ["住居", "低層", "中高層"]) else 0.0
    is_comm = 1.0 if any(k in y for k in ["商業", "近隣商業"]) else 0.0
    is_ind = 1.0 if any(k in y for k in ["工業", "準工業"]) else 0.0

    if "第1種低層" in y or "第１種低層" in y:
        rank = 5.0
    elif "第2種低層" in y or "第２種低層" in y:
        rank = 4.5
    elif "中高層" in y:
        rank = 4.0
    elif "住居" in y:
        rank = 3.5
    elif is_comm:
        rank = 3.0
    elif is_ind:
        rank = 2.0
    else:
        rank = 3.5
    return {
        "is_residential_zone": is_res,
        "is_commercial_zone": is_comm,
        "is_industrial_zone": is_ind,
        "zone_rank": rank
    }


def parse_madori_layout_features(madori_str: str, text: str = "") -> dict[str, float]:
    """間取り・部屋数の数値化（部屋数、LDKフラグ、ワンルームフラグ）"""
    raw = (str(madori_str or "") + " " + str(text or "")).upper()
    room_count = 3.0
    has_ldk = 0.0
    is_studio = 0.0
    m = re.search(r'(\d+)\s*(?:R|K|DK|LDK|SLDK)?', raw)
    if m:
        room_count = float(m.group(1))
    if 'LDK' in raw:
        has_ldk = 1.0
    elif 'DK' in raw:
        has_ldk = 0.5
    elif '1R' in raw or 'ワンルーム' in raw:
        is_studio = 1.0
        room_count = 1.0
    return {
        "room_count": room_count,
        "has_ldk": has_ldk,
        "is_studio": is_studio
    }


def _extract_floor_number(floor_val: Any, raw: str) -> float:
    m_fl = re.search(r'(\d{1,5})\s*階(?:建|部分)?', str(floor_val or ""))
    if m_fl:
        return float(m_fl.group(1))
    if floor_val:
        try:
            return float(floor_val)
        except (ValueError, TypeError):
            pass
    m_fl2 = re.search(r'(\d{1,5})\s*階部分', raw)
    return float(m_fl2.group(1)) if m_fl2 else 0.0


def _extract_total_floors(total_floor_val: Any, raw: str) -> float:
    m_tot = re.search(r'(?:(?:地上|地下)\s*)?(\d{1,5})\s*階建', str(total_floor_val or ""))
    if m_tot:
        return float(m_tot.group(1))
    if total_floor_val:
        try:
            return float(total_floor_val)
        except (ValueError, TypeError):
            pass
    m_tot2 = re.search(r'(\d{1,5})\s*階建', raw)
    return float(m_tot2.group(1)) if m_tot2 else 0.0


def parse_floor_features(floor_val: Any, total_floor_val: Any, text: str = "") -> dict[str, float]:
    """所在階・総階数・階高比率の数値化（最上階・1階フラグ）"""
    raw = f"{floor_val or ''} {total_floor_val or ''} {text or ''}"
    fl = _extract_floor_number(floor_val, raw)
    tot = _extract_total_floors(total_floor_val, raw)

    fl = max(1.0, fl) if fl > 0 else 3.0
    tot = max(fl, tot) if tot > 0 else max(fl, 5.0)
    return {
        "floor_number": fl,
        "total_floors": tot,
        "floor_ratio": round(fl / tot, 3),
        "is_top_floor": 1.0 if fl >= tot else 0.0,
        "is_first_floor": 1.0 if fl <= 1.0 else 0.0
    }


def _parse_wareki_date(text: str) -> datetime.date | None:
    m = re.search(r'(昭和|平成|令和)(\d{1,2})年(?:(\d{1,2})月)?', text)
    if not m:
        return None
    era = m.group(1)
    year = int(m.group(2))
    month = int(m.group(3)) if m.group(3) else 1
    era_offsets = {'昭和': 1925, '平成': 1988, '令和': 2018}
    gregorian_year = era_offsets.get(era, 2000) + year
    try:
        return datetime.date(gregorian_year, month, 1)
    except (ValueError, TypeError):
        return None


def _parse_seireki_date(text: str) -> datetime.date | None:
    m = re.search(r'(\d{4})[年/\.-](\d{1,2})', text)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), 1)
        except (ValueError, TypeError):
            pass
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def calculate_chikunen(chikunengetsu: Any, base_date: datetime.date | None = None) -> float:
    """築年数を算出 (基準日を指定可能。文字列からのパースにも対応)"""
    if not base_date:
        base_date = datetime.date.today()
    if not chikunengetsu:
        return 20.0

    if isinstance(chikunengetsu, (datetime.date, datetime.datetime)):
        dt = chikunengetsu.date() if isinstance(chikunengetsu, datetime.datetime) else chikunengetsu
        return (base_date - dt).days / 365.25

    if isinstance(chikunengetsu, str):
        parsed_dt = _parse_wareki_date(chikunengetsu) or _parse_seireki_date(chikunengetsu)
        if parsed_dt:
            return (base_date - parsed_dt).days / 365.25
        return 20.0

    return 20.0


def _parse_float_from_str(val_str: str, default_val: Any) -> Any:
    if val_str.count('.') > 1:
        return default_val
    m_val = re.search(r'(\d+(?:\.\d+)?)', val_str)
    if not m_val:
        return default_val
    try:
        f_val = float(m_val.group(1))
        return default_val if f_val <= 0 and default_val is not None else f_val
    except (ValueError, TypeError):
        return default_val


def safe_float(val: Any, default_val: Any) -> Any:
    if val is None:
        return default_val
    if isinstance(val, (int, float, Decimal)):
        f_val = float(val)
        return default_val if f_val <= 0 and default_val is not None else f_val
    if isinstance(val, str):
        return _parse_float_from_str(val.strip(), default_val)
    return default_val


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


_DESIGNATED_CITY_WARD_RE = re.compile(r'^([^市]+市[^区]+区)')
_NORMAL_MUNI_RE = re.compile(r'^([^区市町村]+[区市町村])')
_FULL_ADDRESS_MUNI_RE = re.compile(r'^(東京都|大阪府|京都府|北海道|[^県]+県)([^市]+市[^区]+区|[^区市町]+[区市町])')
_POSTAL_CODE_PREFIX_RE = re.compile(r'^(?:〒\s*|\b)\d{3}[-‐ー−]?\d{4}\s*')


def _clean_addr2(addr2: str) -> str:
    """市区町村名を抽出（郵便番号除去、政令指定都市の市＋区表記を完全保持）(Issue #1277, #1281)"""
    if not addr2:
        return ""
    addr2 = _POSTAL_CODE_PREFIX_RE.sub('', addr2).strip()
    # 1. 政令指定都市の「市＋区」（例: 名古屋市中区, 横浜市西区）
    m_ward = _DESIGNATED_CITY_WARD_RE.match(addr2)
    if m_ward:
        return m_ward.group(1)
    # 2. 通常の市区町村
    m_normal = _NORMAL_MUNI_RE.match(addr2)
    if m_normal:
        return m_normal.group(1)
    return addr2


_DESIGNATED_CITY_PREF_MAP = {
    '京都市': '京都府', '神戸市': '兵庫県', '札幌市': '北海道', '千葉市': '千葉県',
    'さいたま市': '埼玉県', '堺市': '大阪府', '大阪市': '大阪府', '仙台市': '宮城県',
    '岡山市': '岡山県', '広島市': '広島県', '名古屋市': '愛知県', '新潟市': '新潟県',
    '熊本市': '熊本県', '川崎市': '神奈川県', '横浜市': '神奈川県', '相模原市': '神奈川県',
    '北九州市': '福岡県', '福岡市': '福岡県', '浜松市': '静岡県', '静岡市': '静岡県'
}

_STATIC_CITY_PREF_MAP: dict[str, str] | None = None


def _load_static_city_pref_map() -> dict[str, str]:
    global _STATIC_CITY_PREF_MAP
    if _STATIC_CITY_PREF_MAP is not None:
        return _STATIC_CITY_PREF_MAP
    import json
    import os
    json_path = os.path.join(os.path.dirname(__file__), 'city_prefecture_map.json')
    if os.path.exists(json_path):
        try:
            with open(json_path, encoding='utf-8') as f:
                _STATIC_CITY_PREF_MAP = json.load(f)
                return _STATIC_CITY_PREF_MAP
        except Exception:
            pass
    _STATIC_CITY_PREF_MAP = {}
    return _STATIC_CITY_PREF_MAP


def _search_muni_cache_for_pref(address2: str) -> str:
    """キャッシュから市区町村の都道府県を検索"""
    from package.ml.features.reference_data import _muni_cache
    if not _muni_cache:
        try:
            from package.ml.features.reference_data import _init_global_caches
            _init_global_caches()
        except Exception:
            pass

    for (pref, city) in _muni_cache:
        if city == address2:
            return pref
        if '市' in address2 and '区' in address2 and city == address2.split('市')[0] + '市':
            return pref
    return ""


def _infer_prefecture_from_muni(address2: str) -> str:
    """市区町村名から都道府県を推測・補完 (Issue #1281)"""
    if not address2:
        return ""

    # 1. 政令指定都市の市＋区（例: 名古屋市中村区 -> 名古屋市 -> 愛知県）
    if '市' in address2 and '区' in address2:
        base_city = address2.split('市')[0] + '市'
        if base_city in _DESIGNATED_CITY_PREF_MAP:
            return _DESIGNATED_CITY_PREF_MAP[base_city]

    # 2. 東京23区（単独の「区」かつ他政令指定都市でない場合）
    if address2.endswith('区') and '市' not in address2:
        return '東京都'

    # 3. 静的マッピング（DB非接続環境でも動作）
    static_map = _load_static_city_pref_map()
    if address2 in static_map:
        return static_map[address2]

    # 4. マスタキャッシュから検索（DB接続時）
    return _search_muni_cache_for_pref(address2)


def _fallback_address(full_address: str, a1: str, a2: str) -> tuple[str, str]:
    """フル住所から都道府県・市区町村（政令市＋区）を補完抽出 (Issue #1277, #1281)"""
    full_address = _POSTAL_CODE_PREFIX_RE.sub('', full_address or '').strip()
    # address2 が政令市名単体（例: '名古屋市'）で区名を含まない場合、full_address から区名を補完
    if a2 and re.match(r'^[^市]+市$', a2) and full_address:
        m_ward = re.search(re.escape(a2) + r'([^区]+区)', full_address)
        if m_ward:
            a2 = f"{a2}{m_ward.group(1)}"
    if not a1 or not a2:
        m = _FULL_ADDRESS_MUNI_RE.match(full_address or '')
        if m:
            a1 = a1 or m.group(1)
            a2 = a2 or m.group(2)
    # address1 が空欄で address2 が判明している場合、マスタ逆引きで補完 (Issue #1281)
    if not a1 and a2:
        a1 = _infer_prefecture_from_muni(a2)
    return a1, a2


def extract_clean_address(property_obj: Any) -> tuple[str, str, str, str]:
    address1 = str(_get_attr(property_obj, 'address1', '') or '')
    address2 = _clean_addr2(str(_get_attr(property_obj, 'address2', '') or ''))
    address1, address2 = _fallback_address(str(_get_attr(property_obj, 'address', '') or ''), address1, address2)
    station1 = str(_get_attr(property_obj, 'station1', '') or '')
    company = resolve_company_name(property_obj)
    return address1, address2, station1, company


_GROUP_SUFFIX_RE = re.compile(r'\d{1,4}(?:号室|号|階)?$')
_CHOME_RE = re.compile(r'(\D+?)(\d+)?(?:丁目|-)')
_FROM_FIRST_DIGIT_RE = re.compile(r'\d.*$', re.DOTALL)


def _normalize_group_text(text: Any) -> str:
    """NFKC 正規化し空白・末尾の号室/階表記を除去する（同一建物の表記揺れ吸収用）。"""
    s = unicodedata.normalize('NFKC', str(text or ''))
    s = ''.join(s.split())
    return _GROUP_SUFFIX_RE.sub('', s)


def _extract_chome(full_address: str, address1: str, address2: str) -> str:
    """住所から（都道府県・市区町村を除いた）町丁目部分を抽出する。抽出できなければ空文字。"""
    addr = unicodedata.normalize('NFKC', full_address or '')
    rest = addr
    for prefix in (address1, address2):
        p = unicodedata.normalize('NFKC', prefix or '')
        if p and p in rest:
            rest = rest.split(p, 1)[1]
    rest = rest.strip()
    if not rest:
        return ''
    m = _CHOME_RE.match(rest)
    if m:
        return f"{m.group(1)}{m.group(2) or ''}"
    return _FROM_FIRST_DIGIT_RE.sub('', rest)


def extract_group_labels(property_obj: Any, address1: str, address2: str) -> tuple[str, str]:
    """
    CV（GroupKFold）用のグループ列 (building_group, chome_group) を返す (Issue #1278)。
    - chome_group: 都道府県＋市区町村＋町丁目（住所が無ければ空文字）
    - building_group: 物件名＋町丁目 → 物件名が無ければ正規化住所 → それも無ければ chome_group
    """
    full_address = str(_get_attr(property_obj, 'address', '') or '')
    chome = _extract_chome(full_address, address1, address2)
    area_key = (address1 or '') + (address2 or '')
    chome_group = area_key + chome if area_key else _normalize_group_text(full_address)
    name = _normalize_group_text(_get_attr(property_obj, 'propertyName', ''))
    if name:
        building_group = f"{name}|{chome_group}"
    else:
        building_group = _normalize_group_text(full_address) or chome_group
    return building_group, chome_group


def _parse_date_value(val: Any) -> datetime.date | None:
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, str):
        try:
            return datetime.datetime.strptime(val[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    return None


def _resolve_eval_base_date(base_date: Any, _prop_date: datetime.date | None = None) -> datetime.date:
    today_val = datetime.date.today()
    if not base_date:
        return today_val
    parsed = _parse_date_value(base_date)
    return parsed if parsed is not None else today_val


def _check_is_legacy(prop_date: datetime.date | None, property_obj: Any) -> float:
    if prop_date and prop_date < datetime.date(2025, 1, 1):
        return 1.0
    if bool(_get_attr(property_obj, 'is_legacy_data', False)):
        return 1.0
    if _get_attr(property_obj, 'isSoldout', 0) == 1:
        return 1.0
    return 0.0


def resolve_eval_dates_and_diff(property_obj: Any, base_date: Any) -> tuple[datetime.date, datetime.date, float, float]:
    raw_date = _get_attr(property_obj, 'inputDate', None) or _get_attr(property_obj, 'inputDateTime', None)
    prop_date = _parse_date_value(raw_date)
    eval_base_date = _resolve_eval_base_date(base_date, prop_date)
    ref_prop_date = prop_date or eval_base_date
    diff_days = (eval_base_date - ref_prop_date).days
    time_diff_months = max(0.0, round(float(diff_days) / 30.4375, 2))
    is_legacy = _check_is_legacy(prop_date, property_obj)
    return eval_base_date, ref_prop_date, time_diff_months, is_legacy


def _get_raw_chikunengetsu(property_obj: Any) -> Any:
    return (
        _get_attr(property_obj, 'chikunengetsu', None)
        or _get_attr(property_obj, 'builtYear', None)
        or _get_attr(property_obj, 'buildDate', None)
        or _get_attr(property_obj, 'chikunengetsuStr', None)
        or _get_attr(property_obj, 'kenchikuNengetsu', None)
        or _get_attr(property_obj, 'chikunen', None)
    )


def calculate_chikunen_feature(property_obj: Any, property_type: str, eval_base_date: datetime.date) -> tuple[float, float]:
    chikunengetsu = _get_raw_chikunengetsu(property_obj)
    if not chikunengetsu:
        kouzou_raw = str(_get_attr(property_obj, 'kouzou', '') or _get_attr(property_obj, 'structure', ''))
        age = 38.0 if ("木" in kouzou_raw or property_type == 'kodate') else 30.0
        return age, 1.0
    return calculate_chikunen(chikunengetsu, eval_base_date), 0.0


def extract_traffic_and_walk_min(property_obj: Any) -> tuple[int, float, float, int]:
    walk_min = _get_attr(property_obj, 'railwayWalkMinute1', None)
    raw_traffic = str(_get_attr(property_obj, 'traffic', '') or _get_attr(property_obj, 'koutsu', '') or '')
    bus_use = _get_attr(property_obj, 'busUse1', 0)

    bus_min = 0.0
    m_bus = re.search(r'(?:【バス】|バス|乗車)\s*(\d+)\s*分', raw_traffic)
    if m_bus:
        bus_min = safe_float(m_bus.group(1), 0.0)
        bus_use = 1

    bus_walk = _get_attr(property_obj, 'busWalkMinute1', None)
    if bus_walk is None:
        m_bwalk = re.search(r'(?:停歩|停 徒歩|バス停徒歩)\s*(\d+)\s*分', raw_traffic)
        bus_walk = safe_float(m_bwalk.group(1), 0.0) if m_bwalk else 0.0
    else:
        bus_walk = safe_float(bus_walk, 0.0)

    if walk_min is None:
        m_walk = re.search(r'(?:徒歩|歩)\s*(\d+)\s*分', raw_traffic)
        walk_min = safe_float(m_walk.group(1), 15) if m_walk else 15
    return int(walk_min), bus_min, bus_walk, bus_use


def _parse_setback_area(text: str) -> float:
    patterns = (
        r'(?:セットバック|後退)(?:面積)?(?:約)?\s*([\d.]+)\s*(?:㎡|平米|m2|ｍ２)',
        r'([\d.]+)\s*(?:㎡|平米|m2|ｍ２)\s*(?:のセットバック|の後退|セットバック要)',
    )
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            val = safe_float(m.group(1), 0.0)
            if val > 0:
                return val
    return 0.0


def _collect_setback_candidate_texts(property_obj: Any) -> list[str]:
    texts = []
    setback_field = _get_attr(property_obj, 'setback', None)
    if setback_field:
        texts.append(str(setback_field))
    for attr in ('setsudou', 'remarks', 'tochiMensekiStr', 'note'):
        val = _get_attr(property_obj, attr, None)
        if val:
            texts.append(str(val))
    return texts


def _extract_setback_from_text(property_obj: Any) -> float:
    for text in _collect_setback_candidate_texts(property_obj):
        area_val = _parse_setback_area(text)
        if area_val > 0:
            return area_val
    return 0.0


def _first_non_empty_attr(property_obj: Any, attrs: tuple[str, ...]) -> Any:
    for a in attrs:
        v = _get_attr(property_obj, a, None)
        if v:
            return v
    return None


def _regex_extract_float(pattern: str, text: str) -> float | None:
    if not text:
        return None
    m = re.search(pattern, text)
    return safe_float(m.group(1), 0.0) if m else None


def _calculate_desk_setback(property_obj: Any) -> float:
    maguchi_temp = _first_non_empty_attr(property_obj, ('maguchi', 'setsumen', 'maguchiStr', 'setsumenStr'))
    road_width_temp = _first_non_empty_attr(property_obj, ('roadWidth', 'douroHaba', 'roadWidthStr', 'douroHabaStr'))
    s1 = str(_get_attr(property_obj, 'setsudou', '') or '')
    s2 = str(_get_attr(property_obj, 'douro', '') or '')
    raw_setsudou_temp = f"{s1} {s2}".strip()

    if not road_width_temp:
        road_width_temp = _regex_extract_float(r'(?:幅員|幅)?\s*(\d{1,5}(?:\.\d{1,3})?)\s*[mｍ]', raw_setsudou_temp)
    if not maguchi_temp:
        maguchi_temp = _regex_extract_float(r'(?:間口|接面|接道)\s*(?:約\s*)?(\d{1,5}(?:\.\d{1,3})?)\s*[mｍ]', raw_setsudou_temp)

    maguchi_val_temp = safe_float(maguchi_temp, 6.0)
    road_width_val_temp = safe_float(road_width_temp, 4.0)

    if road_width_val_temp < 4.0:
        return maguchi_val_temp * ((4.0 - road_width_val_temp) / 2.0)
    return 0.0


def _evaluate_kenchiku_joken(property_obj: Any, combined_text: str) -> float:
    kj_raw = str(_get_attr(property_obj, 'kenchikuJoken', '') or '').strip()
    check_text = f"{kj_raw} {combined_text}"
    if any(k in check_text for k in ("建築条件無", "建築条件なし", "建築条件ナシ", "条件無し", "条件なし")):
        return 0.0
    if kj_raw in ("無", "なし", "ナシ", "-", "－"):
        return 0.0
    if any(k in check_text for k in ("建築条件付", "建築条件あり", "建築条件有")) or kj_raw in ("有", "あり", "付"):
        return 1.0
    return 0.0


def _evaluate_chisei_terrain(property_obj: Any, combined_text: str) -> tuple[float, float]:
    c1 = str(_get_attr(property_obj, 'chisei', '') or '')
    c2 = str(_get_attr(property_obj, 'chimokuChisei', '') or '')
    check_text = f"{c1} {c2} {combined_text}".strip()
    if any(k in check_text for k in ("傾斜", "法面", "のり面", "がけ", "崖", "急傾斜", "山岳", "擁壁")):
        return 0.78, 0.0
    if any(k in check_text for k in ("ひな段", "雛段", "高台", "段差", "高低差")):
        return 0.92, 0.0
    if "低地" in check_text or "窪地" in check_text:
        return 0.88, 0.0
    return 1.00, 1.0


def _evaluate_bouka_score(property_obj: Any, combined_text: str) -> float:
    b1 = str(_get_attr(property_obj, 'boukaChiiki', '') or '')
    b2 = str(_get_attr(property_obj, 'chiikiChiku', '') or '')
    bouka_raw = f"{b1} {b2}".strip()
    check_bouka = f"{bouka_raw} {combined_text}"
    if "準防火" in check_bouka:
        return 1.00
    if "防火地域" in check_bouka or bouka_raw == "防火":
        return 1.05
    if "22条" in check_bouka or "２２条" in check_bouka:
        return 0.97
    return 0.98


_EMPTY_PR_TOKENS = ("無", "なし", "ナシ", "-", "－", "0", "0㎡", "0.0㎡")


def _evaluate_private_road_burden(property_obj: Any, combined_text: str) -> float:
    shido_area = safe_float(_get_attr(property_obj, 'shidoMenseki', None), 0.0)
    if shido_area and shido_area > 0.0:
        return 1.0
    pr_raw = str(_first_non_empty_attr(property_obj, ('privateRoadBurden', 'shidoMensekiStr')) or '').strip()
    if pr_raw and pr_raw not in _EMPTY_PR_TOKENS and "無" not in pr_raw and "なし" not in pr_raw:
        return 1.0
    if "私道負担有" in combined_text or "私道負担あり" in combined_text:
        return 1.0
    return 0.0


def _evaluate_bouka_and_private_road(property_obj: Any, combined_text: str) -> tuple[float, float]:
    return _evaluate_bouka_score(property_obj, combined_text), _evaluate_private_road_burden(property_obj, combined_text)


def parse_land_specific_features(property_obj: Any, combined_text: str = "") -> dict[str, float]:
    """土地・戸建て固有の価格決定要因（建築条件・地勢・防火規制・私道負担）を数値特徴量化 (Issue #1338)"""
    has_kj = _evaluate_kenchiku_joken(property_obj, combined_text)
    chisei_score, is_flat = _evaluate_chisei_terrain(property_obj, combined_text)
    bouka_score, has_pr = _evaluate_bouka_and_private_road(property_obj, combined_text)
    return {
        "has_kenchiku_joken": has_kj,
        "chisei_score": chisei_score,
        "is_flat_terrain": is_flat,
        "bouka_score": bouka_score,
        "has_private_road_burden": has_pr,
    }


def calculate_area_and_setback(property_obj: Any, property_type: str) -> tuple[float, float, float, float]:
    senyu_menseki = _get_attr(property_obj, 'senyuMenseki', 0.0)
    tatemono_menseki = _get_attr(property_obj, 'tatemonoMenseki', 0.0)
    tochi_menseki = _get_attr(property_obj, 'tochiMenseki', 0.0)

    area = float(senyu_menseki) if senyu_menseki else 0.0
    tatemono_area = float(tatemono_menseki) if tatemono_menseki else 0.0
    tochi_area = float(tochi_menseki) if tochi_menseki else 0.0

    if property_type == 'mansion' and area > 500.0:
        area = 70.0

    if property_type == 'mansion':
        tochi_area = 0.0

    setback_area_temp = _extract_setback_from_text(property_obj)
    if setback_area_temp <= 0.0:
        setback_area_temp = _calculate_desk_setback(property_obj)

    setback_ratio_temp = 0.0
    if setback_area_temp > 0.0 and tochi_area > 0.0:
        setback_ratio_temp = min(1.0, setback_area_temp / tochi_area)

    tochi_area = tochi_area * (1.0 - setback_ratio_temp)
    return area, tatemono_area, tochi_area, setback_ratio_temp


def calculate_digest_volume_features(property_type: str, tochi_area: float, tatemono_area: float, max_youseki: float) -> tuple[float, float, int]:
    if property_type not in ['kodate', 'apartment'] or tochi_area <= 0:
        return 0.0, 0.0, 0
    digest_volume_ratio = (tatemono_area / tochi_area) * 100.0
    surplus_volume_potential = max(0.0, max_youseki - digest_volume_ratio)
    non_conforming_flag = 1 if digest_volume_ratio > max_youseki else 0
    return digest_volume_ratio, surplus_volume_potential, non_conforming_flag


def calculate_shin_taishin(property_obj: Any, chikunen: float) -> int:
    chikunengetsu = _get_raw_chikunengetsu(property_obj)
    if chikunengetsu and isinstance(chikunengetsu, datetime.date):
        return 0 if chikunengetsu < datetime.date(1981, 6, 1) else 1
    return 0 if chikunen > 45.0 else 1


def calculate_effective_building_and_floor_area(property_obj: Any, tochi_area: float, max_kenpei: float, actual_volume_limit: float) -> tuple[float, float]:
    road_struct = _get_attr(property_obj, 'roadStructure', '') or _get_attr(property_obj, 'setsudou', '') or ''
    is_corner = any(x in str(road_struct) for x in ("角地", "準角地", "三方", "四方"))
    effective_kenpei = min(100.0, max_kenpei + 10.0) if is_corner else max_kenpei
    max_building_area = tochi_area * (effective_kenpei / 100.0) if tochi_area > 0 else 0.0
    max_floor_area = tochi_area * (actual_volume_limit / 100.0) if tochi_area > 0 else 0.0
    return max_building_area, max_floor_area


# Alias for backward compatibility
_extract_clean_address = extract_clean_address
_extract_group_labels = extract_group_labels
_resolve_eval_dates_and_diff = resolve_eval_dates_and_diff
_calculate_chikunen_feature = calculate_chikunen_feature
_extract_traffic_and_walk_min = extract_traffic_and_walk_min
_calculate_area_and_setback = calculate_area_and_setback
_calculate_digest_volume_features = calculate_digest_volume_features
_calculate_shin_taishin = calculate_shin_taishin
_calculate_effective_building_and_floor_area = calculate_effective_building_and_floor_area

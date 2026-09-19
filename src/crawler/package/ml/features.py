# -*- coding: utf-8 -*-
import datetime
import re
from decimal import Decimal
from typing import Dict, Tuple, Any
from package.utils.plot_shape_analyzer import analyze_plot_shape

# 再調達単価 (万円/㎡) と法定耐用年数
REPLACEMENT_COSTS = {
    'RC': 25.0,
    'SRC': 25.0,
    'S': 20.0,
    'W': 15.0,
    'LS': 15.0,  # 軽量鉄骨
    'default': 18.0
}

LIFESPAN = {
    'RC': 47,
    'SRC': 47,
    'S': 34,
    'W': 22,
    'LS': 34,
    'default': 30
}

FEATURE_SETS = {
    "mansion": {
        "first": [
            "area", "chikunen", "walk_min", "kanrihi", "syuzen",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "max_building_area", "max_floor_area",
            "kagechi_ratio", "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "zone_max_kenpei", "zone_max_youseki"
        ],
        "second": [
            "area", "chikunen", "walk_min", "kanrihi", "syuzen",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei", "max_building_area", "max_floor_area",
            "kagechi_ratio", "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "interior_score", "layout_score",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "zone_max_kenpei", "zone_max_youseki"
        ]
    },
    "kodate": {
        "first": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "zone_max_kenpei", "zone_max_youseki"
        ],
        "second": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "interior_score", "layout_score",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "zone_max_kenpei", "zone_max_youseki"
        ]
    },
    "apartment": {
        "first": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "gross_yield", "annual_rent",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "zone_max_kenpei", "zone_max_youseki"
        ],
        "second": [
            "area", "tochi_menseki", "chikunen", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
            "gross_yield", "annual_rent",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density", "kouzou_lifespan_ratio",
            "interior_score", "layout_score",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "zone_max_kenpei", "zone_max_youseki"
        ]
    },
    "tochi": {
        "first": [
            "area", "tochi_menseki", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "is_furuya", "has_demolition_condition", "furuya_demolition_cost", "furuya_usable_value", "furuya_option_value",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "zone_max_kenpei", "zone_max_youseki"
        ],
        "second": [
            "area", "tochi_menseki", "walk_min",
            "pop_growth", "income", "passenger_volume", "average_land_price",
            "estimated_rosenka_price", "estimated_fixed_asset_price",
            "cost_approach_value", "mkt_comparison_value", "income_approach_value",
            "flood_risk_level", "landslide_risk_level",
            "max_youseki", "max_kenpei",
            "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
            "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value",
            "max_building_area", "max_floor_area", "kagechi_ratio",
            "total_population", "income_growth_rate", "land_price_growth_rate",
            "effective_walk_min", "population_density",
            "interior_score", "layout_score",
            "is_shigaika_chousei", "is_saikenchiku_fuka", "rights_ratio",
            "potential_floor_area", "scale_discount",
            "is_furuya", "has_demolition_condition", "furuya_demolition_cost", "furuya_usable_value", "furuya_option_value",
            "plot_shadow_ratio", "plot_aspect_ratio", "plot_effective_ratio", "plot_shape_penalty",
            "zone_max_kenpei", "zone_max_youseki"
        ]
    }
}

def parse_kouzou(kouzou_str):
    """構造文字列から構造カテゴリを分類"""
    if not kouzou_str:
        return 'default'
    kouzou_str = kouzou_str.upper()
    if 'RC' in kouzou_str or '鉄筋コンクリート' in kouzou_str:
        return 'RC'
    if 'SRC' in kouzou_str or '鉄骨鉄筋' in kouzou_str:
        return 'SRC'
    if '鉄骨' in kouzou_str or '重量鉄骨' in kouzou_str or 'Ｓ造' in kouzou_str:
        if '軽量' in kouzou_str:
            return 'LS'
        return 'S'
    if '木' in kouzou_str or 'Ｗ造' in kouzou_str:
        return 'W'
    return 'default'

def calculate_chikunen(chikunengetsu, base_date=None):
    """築年数を算出 (基準日を指定可能。文字列からのパースにも対応)"""
    import re
    if not base_date:
        base_date = datetime.date.today()
    if not chikunengetsu:
        return 20.0
    
    if isinstance(chikunengetsu, str):
        # 和暦の簡易パース (昭和/平成/令和)
        m = re.search(r'(昭和|平成|令和)(\d{1,2})年(?:(\d{1,2})月)?', chikunengetsu)
        if m:
            era = m.group(1)
            year = int(m.group(2))
            month = int(m.group(3)) if m.group(3) else 1
            gregorian_year = 2000
            if era == '昭和':
                gregorian_year = 1925 + year
            elif era == '平成':
                gregorian_year = 1988 + year
            elif era == '令和':
                gregorian_year = 2018 + year
            try:
                dt = datetime.date(gregorian_year, month, 1)
                return (base_date - dt).days / 365.25
            except:
                return 20.0
                
        # 西暦のパース (YYYY-MM-DD or YYYY年MM月など)
        m = re.search(r'(\d{4})[年/\.-](\d{1,2})', chikunengetsu)
        if m:
            try:
                dt = datetime.date(int(m.group(1)), int(m.group(2)), 1)
                return (base_date - dt).days / 365.25
            except:
                pass
                
        # 単純な日付形式 YYYY-MM-DD
        try:
            dt = datetime.datetime.strptime(chikunengetsu, "%Y-%m-%d").date()
            return (base_date - dt).days / 365.25
        except:
            return 20.0
    elif isinstance(chikunengetsu, (datetime.date, datetime.datetime)):
        if isinstance(chikunengetsu, datetime.datetime):
            chikunengetsu = chikunengetsu.date()
        return (base_date - chikunengetsu).days / 365.25
    return 20.0


def safe_float(val, default_val):
    if val is None:
        return default_val
    if isinstance(val, (int, float, Decimal)):
        f_val = float(val)
        if f_val <= 0 and default_val is not None:
            return default_val
        return f_val
    if isinstance(val, str):
        val_str = val.strip()
        if val_str.count('.') > 1:
            return default_val
        m_val = re.search(r'(\d+(?:\.\d+)?)', val_str)
        if m_val:
            try:
                f_val = float(m_val.group(1))
                if f_val <= 0 and default_val is not None:
                    return default_val
                return f_val
            except (ValueError, TypeError):
                pass
    return default_val

# 全国47都道府県の標準的基準地価（住宅地/商業地, 円/㎡）
PREFECTURE_BASE_LAND_PRICES = {
    "東京都": (500000, 2500000),
    "神奈川県": (210000, 650000),
    "大阪府": (230000, 1300000),
    "愛知県": (150000, 600000),
    "京都府": (220000, 850000),
    "埼玉県": (140000, 420000),
    "兵庫県": (150000, 520000),
    "千葉県": (120000, 320000),
    "福岡県": (140000, 750000),
    "宮城県": (100000, 450000),
    "広島県": (100000, 380000),
    "静岡県": (70000, 180000),
    "滋賀県": (75000, 180000),
    "北海道": (50000, 220000),
    "奈良県": (80000, 200000),
    "岡山県": (65000, 180000),
    "熊本県": (65000, 220000),
    "沖縄県": (110000, 300000),
    "茨城県": (50000, 130000),
    "栃木県": (50000, 130000),
    "群馬県": (45000, 120000),
    "長野県": (40000, 95000),
    "岐阜県": (45000, 110000),
    "三重県": (45000, 110000),
    "新潟県": (35000, 80000),
    "富山県": (40000, 90000),
    "石川県": (55000, 160000),
    "福井県": (40000, 90000),
    "山梨県": (35000, 80000),
    "福島県": (40000, 95000),
    "山形県": (35000, 80000),
    "岩手県": (35000, 85000),
    "秋田県": (30000, 75000),
    "青森県": (30000, 75000),
    "鳥取県": (35000, 80000),
    "島根県": (30000, 75000),
    "山口県": (40000, 90000),
    "徳島県": (45000, 100000),
    "香川県": (55000, 140000),
    "愛媛県": (50000, 130000),
    "高知県": (45000, 110000),
    "佐賀県": (40000, 90000),
    "長崎県": (50000, 120000),
    "大分県": (45000, 110000),
    "宮崎県": (40000, 95000),
    "鹿児島県": (40000, 110000),
}

def _get_nationwide_base_land_price(prefecture: str, city: str = "") -> Tuple[int, int]:
    """
    全国47都道府県および市区町村別の基準地価（住宅地/商業地, 円/㎡）を動的算出
    """
    pref_clean = (prefecture or "").strip()
    city_clean = (city or "").strip()
    
    base_res, base_comm = 80000, 200000
    for p, vals in PREFECTURE_BASE_LAND_PRICES.items():
        if p in pref_clean or pref_clean in p:
            base_res, base_comm = vals
            break
            
    if any(k in city_clean for k in ["千代田区", "中央区", "港区"]):
        return 2000000, 6500000
    if any(k in city_clean for k in ["渋谷区", "新宿区", "文京区", "目黒区"]):
        return 1300000, 3800000
    if any(k in city_clean for k in ["品川区", "世田谷区", "大田区", "杉並区", "中野区", "豊島区"]):
        return 800000, 2200000
    if "区" in city_clean and ("東京" in pref_clean or pref_clean == "東京都"):
        return 550000, 1400000
        
    if any(k in city_clean for k in ["北区", "中央区", "中区", "博多区", "東山区", "下京区", "西区"]):
        if any(p in pref_clean for p in ["大阪府", "京都府", "愛知県", "福岡県", "神奈川県", "兵庫県"]):
            return max(base_res * 2, 450000), max(base_comm * 2, 1800000)
            
    if any(k in city_clean for k in ["郡", "町", "村"]):
        return int(base_res * 0.45), int(base_comm * 0.45)
        
    return base_res, base_comm

# グローバルキャッシュ変数
_muni_cache: Dict[Tuple[str, str], Any] = {}
_muni_pref_cache: Dict[str, list] = {}
_station_cache: Dict[str, Any] = {}
_lp_cache: Dict[Tuple[str, str, str], Any] = {}
_lp_pref_res_cache: Dict[str, list] = {}
_lp_pref_comm_cache: Dict[str, list] = {}
_hazard_cache: Dict[Tuple[str, str], Any] = {}
_zone_cache: Dict[str, Any] = {}

def _init_global_caches():
    """
    特徴量抽出のボトルネックを解消するため、
    全 Potential 関連マスタを一括でインメモリキャッシュします。
    """
    global _muni_cache, _muni_pref_cache, _station_cache, _lp_cache, _lp_pref_res_cache, _lp_pref_comm_cache, _hazard_cache, _zone_cache
    from package.models.evaluation import MunicipalPotential, StationPotential, LandPricePotential, HazardMapPotential, UrbanPlanningZonePotential

    if not _muni_cache:
        for m in MunicipalPotential.objects.all():
            _muni_cache[(m.prefecture, m.city)] = m
            _muni_pref_cache.setdefault(m.prefecture, []).append(m)
            
    if not _station_cache:
        for s in StationPotential.objects.all():
            _station_cache[s.station_name] = s
            
    if not _lp_cache:
        for lp in LandPricePotential.objects.all():
            _lp_cache[(lp.prefecture, lp.city, lp.land_use)] = lp
            if lp.land_use == 'residential':
                _lp_pref_res_cache.setdefault(lp.prefecture, []).append(lp)
            elif lp.land_use == 'commercial':
                _lp_pref_comm_cache.setdefault(lp.prefecture, []).append(lp)
            
    if not _hazard_cache:
        for hz in HazardMapPotential.objects.all():
            _hazard_cache[(hz.prefecture, hz.city)] = hz
            
    if not _zone_cache:
        for z in UrbanPlanningZonePotential.objects.all():
            _zone_cache[z.zone_name] = z

    from django.db import connections
    try:
        connections.close_all()
    except Exception:
        pass

_load_all_potential_caches_once = _init_global_caches


def build_features(property_obj, property_type, base_date=None, mkt_comparison_master=None):
    """
    共通特徴量エンジニアリング関数 (Djangoモデルオブジェクトまたは辞書に対応)
    """
    
    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    # 1. 基本属性の抽出
    address1 = get_attr(property_obj, 'address1', '') or ''
    address2 = get_attr(property_obj, 'address2', '') or ''
    
    import re
    if address2:
        m_clean = re.match(r'^([^区市町村]+[区市町村])', address2)
        if m_clean:
            address2 = m_clean.group(1)
            
    if not address1 or not address2:
        full_address = get_attr(property_obj, 'address', '') or ''
        m = re.match(r'^(東京都|大阪府|京都府|北海道|[^県]+県)([^区市町]+[区市町])', full_address)
        if m:
            if not address1:
                address1 = m.group(1)
            if not address2:
                address2 = m.group(2)
                
    station1 = get_attr(property_obj, 'station1', '') or ''
    company = get_attr(property_obj, 'company', 'unknown') or 'unknown'

    # 基準日の設定
    if not base_date:
        input_date = get_attr(property_obj, 'inputDate', None)
        if input_date:
            base_date = input_date
        else:
            base_date = datetime.date.today()
            
    chikunengetsu = (
        get_attr(property_obj, 'chikunengetsu', None)
        or get_attr(property_obj, 'builtYear', None)
        or get_attr(property_obj, 'buildDate', None)
        or get_attr(property_obj, 'chikunengetsuStr', None)
        or get_attr(property_obj, 'kenchikuNengetsu', None)
        or get_attr(property_obj, 'chikunen', None)
    )
    if not chikunengetsu:
        kouzou_raw = str(get_attr(property_obj, 'kouzou', '') or get_attr(property_obj, 'structure', ''))
        if "木" in kouzou_raw or property_type == 'kodate':
            chikunen = 38.0
        else:
            chikunen = 30.0
    else:
        chikunen = calculate_chikunen(chikunengetsu, base_date)
    
    walk_min = get_attr(property_obj, 'railwayWalkMinute1', None)
    raw_traffic = str(get_attr(property_obj, 'traffic', '') or get_attr(property_obj, 'koutsu', '') or '')
    bus_use = get_attr(property_obj, 'busUse1', 0)
    
    # バス乗車分数の抽出 (例: "【バス】28分", "バス20分", "バス乗車15分")
    bus_min = 0.0
    m_bus = re.search(r'(?:【バス】|バス|乗車)\s*([0-9]+)\s*分', raw_traffic)
    if m_bus:
        bus_min = safe_float(m_bus.group(1), 0.0)
        bus_use = 1
        
    bus_walk = get_attr(property_obj, 'busWalkMinute1', None)
    if bus_walk is None:
        m_bwalk = re.search(r'(?:停歩|停 徒歩|バス停徒歩)\s*([0-9]+)\s*分', raw_traffic)
        bus_walk = safe_float(m_bwalk.group(1), 0.0) if m_bwalk else 0.0
    else:
        bus_walk = safe_float(bus_walk, 0.0)

    if walk_min is None:
        # traffic / koutsu テキストからの徒歩分数抽出
        m_walk = re.search(r'(?:徒歩|歩)\s*([0-9]+)\s*分', raw_traffic)
        if m_walk:
            walk_min = safe_float(m_walk.group(1), 15)
        else:
            walk_min = 15
    walk_min = int(walk_min)
    
    # 各種面積
    senyu_menseki = get_attr(property_obj, 'senyuMenseki', 0.0)
    tatemono_menseki = get_attr(property_obj, 'tatemonoMenseki', 0.0)
    tochi_menseki = get_attr(property_obj, 'tochiMenseki', 0.0)
    
    area = float(senyu_menseki) if senyu_menseki else 0.0
    tatemono_area = float(tatemono_menseki) if tatemono_menseki else 0.0
    tochi_area = float(tochi_menseki) if tochi_menseki else 0.0
    
    # マンションの面積異常サニタイズ（価格等の混入による500㎡超の異常値を防御）
    if property_type == 'mansion' and area > 500.0:
        area = 70.0
    
    # セットバック（後退）相当面積の算出および土地有効面積への調整
    import re
    setback_area_temp = 0.0
    
    # (A) 実際のテキスト（setback / setsudou / remarks / tochiMensekiStr / note）からセットバック面積を探す
    search_texts = []
    setback_field = get_attr(property_obj, 'setback', None)
    if setback_field:
        search_texts.append(str(setback_field))
    for attr in ['setsudou', 'remarks', 'tochiMensekiStr', 'note']:
        val = get_attr(property_obj, attr, None)
        if val:
            search_texts.append(str(val))
            
    for text in search_texts:
        patterns = [
            r'(?:セットバック|後退)(?:面積)?(?:約)?\s*([0-9\.]+)\s*(?:㎡|平米|m2|ｍ２)',
            r'([0-9\.]+)\s*(?:㎡|平米|m2|ｍ２)\s*(?:のセットバック|の後退|セットバック要)',
        ]
        found = False
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    area_val = float(match.group(1))
                    if area_val > 0:
                        setback_area_temp = area_val
                        found = True
                        break
                except:
                    pass
        if found:
            break
            
    # (B) テキストから見つからない場合は、間口と道路幅員から机上計算
    if setback_area_temp <= 0.0:
        maguchi_temp = get_attr(property_obj, 'maguchi', None)
        road_width_temp = get_attr(property_obj, 'roadWidth', None) or get_attr(property_obj, 'douroHaba', None)
        raw_setsudou_temp = get_attr(property_obj, 'setsudou', '') or ''
        
        if not road_width_temp and raw_setsudou_temp:
            m_width = re.search(r'([0-9\.]+)\s*[mｍ]', raw_setsudou_temp)
            if m_width:
                road_width_temp = safe_float(m_width.group(1), 0.0)
                
        if not maguchi_temp and raw_setsudou_temp:
            m_maguchi = re.search(r'(?:間口|接面)\s*(?:約)?\s*([0-9\.]+)\s*[mｍ]', raw_setsudou_temp)
            if m_maguchi:
                maguchi_temp = safe_float(m_maguchi.group(1), 0.0)
                
        maguchi_val_temp = safe_float(maguchi_temp, 6.0)
        road_width_val_temp = safe_float(road_width_temp, 4.0)
        
        if road_width_val_temp < 4.0:
            setback_width_temp = (4.0 - road_width_val_temp) / 2.0
            setback_area_temp = maguchi_val_temp * setback_width_temp

    setback_ratio_temp = 0.0
    if setback_area_temp > 0.0 and tochi_area > 0.0:
        setback_ratio_temp = min(1.0, setback_area_temp / tochi_area)
        
    # セットバック相当分を除いた土地面積を以降の価格推定計算に利用
    tochi_area = tochi_area * (1.0 - setback_ratio_temp)
    
    # グローバルキャッシュの初期化
    _init_global_caches()
    
    # 2. 自治体ポテンシャルマスタとの結合
    pop_growth = 0.0
    income = 3000
    total_population = 100000
    income_growth_rate = 0.0
    muni = _muni_cache.get((address1, address2))
    if muni:
        pop_growth = float(muni.population_growth_rate)
        income = muni.average_income
        total_population = muni.total_population if muni.total_population is not None else 100000
        income_growth_rate = float(muni.income_growth_rate) if muni.income_growth_rate is not None else 0.0
    else:
        muni_pref_vals = _muni_pref_cache.get(address1, [])
        if muni_pref_vals:
            pop_growth = sum(float(x.population_growth_rate) for x in muni_pref_vals) / len(muni_pref_vals)
            income = int(sum(x.average_income for x in muni_pref_vals) / len(muni_pref_vals))
            total_population = int(sum(x.total_population for x in muni_pref_vals if x.total_population is not None) / len(muni_pref_vals)) if any(x.total_population is not None for x in muni_pref_vals) else 100000
            income_growth_rate = sum(float(x.income_growth_rate) for x in muni_pref_vals if x.income_growth_rate is not None) / len(muni_pref_vals) if any(x.income_growth_rate is not None for x in muni_pref_vals) else 0.0

    # 3. 駅ポテンシャルマスタとの結合
    passenger_volume = 10000
    if station1:
        station_clean = station1.replace("駅", "")
        station_pot = _station_cache.get(station_clean)
        if station_pot:
            passenger_volume = station_pot.passenger_volume

    # 地域の人口密度（density）に基づき、駅距離に対するペナルティ倍率を動的調整する
    # 人口密度が 4,000人/㎢ 以上の過密・主要交通エリアは影響度 1.0 (フルに徒歩分数が価格へ影響)
    # 人口密度が減る（地方や郊外のマイカー社会）に従って、駅距離の影響度を最低 0.4 まで逓減
    pop_density = 4000.0
    if muni and muni.population_density is not None:
        pop_density = float(muni.population_density)
    else:
        muni_pref_vals = _muni_pref_cache.get(address1, [])
        if muni_pref_vals:
            pop_density = sum(float(x.population_density) for x in muni_pref_vals if x.population_density is not None) / len(muni_pref_vals) if any(x.population_density is not None for x in muni_pref_vals) else 4000.0

    walk_min_penalty_scale = max(0.4, min(1.0, 0.4 + 0.6 * (pop_density / 4000.0)))
    if bus_use or bus_min > 0:
        raw_access_min = float(bus_min * 1.5 + bus_walk)
        if raw_access_min < walk_min and bus_min > 0:
            raw_access_min = float(bus_min * 1.5 + walk_min)
        if raw_access_min <= 0:
            raw_access_min = float(walk_min)
    else:
        raw_access_min = float(walk_min)
        
    effective_walk_min = raw_access_min * walk_min_penalty_scale

    # 4. 用途地域規制（上限容積率・建ぺい率）の正規表現抽出とマスタ引き当て
    import re
    
    def extract_limit(text, is_youseki=False):
        if not text:
            return None
        text_str = str(text)
        # "80% / 600%" や "80/600" など建ぺい・容積がスラッシュで併記されている場合
        if '/' in text_str:
            parts = re.findall(r'(\d+(?:\.\d+)?)\s*%?', text_str)
            if len(parts) >= 2:
                try:
                    return float(parts[1]) if is_youseki else float(parts[0])
                except (ValueError, TypeError):
                    pass
        if is_youseki:
            m_yo = re.search(r'容積率?[^\d]*(\d+(?:\.\d+)?)\s*%', text_str)
            if m_yo:
                return float(m_yo.group(1))
        else:
            m_ke = re.search(r'建[ぺペ]い率?[^\d]*(\d+(?:\.\d+)?)\s*%', text_str)
            if m_ke:
                return float(m_ke.group(1))
        match = re.search(r'(\d+(?:\.\d+)?)\s*%', text_str)
        if match:
            return float(match.group(1))
        match = re.search(r'(\d+(?:\.\d+)?)', text_str)
        if match:
            val = float(match.group(1))
            if 10.0 <= val <= 1500.0:
                return val
        return None

    max_youseki = None
    max_kenpei = None
    
    youseki_raw = (
        get_attr(property_obj, 'youseki', None)
        or get_attr(property_obj, 'yousekiStr', None)
        or get_attr(property_obj, 'kenpeiYousekiStr', None)
        or get_attr(property_obj, 'yousekiRitsu', None)
    )
    kenpei_raw = (
        get_attr(property_obj, 'kenpei', None)
        or get_attr(property_obj, 'kenpeiStr', None)
        or get_attr(property_obj, 'kenpeiYousekiStr', None)
        or get_attr(property_obj, 'kenpeiRitsu', None)
    )
    
    max_youseki = extract_limit(youseki_raw, is_youseki=True)
    max_kenpei = extract_limit(kenpei_raw, is_youseki=False)
    
    zone_name_prop = (
        get_attr(property_obj, 'zone_name', None)
        or get_attr(property_obj, 'youtoChiiki', None)
        or get_attr(property_obj, 'youto', None)
    )
    zone_rec = None
    if zone_name_prop:
        if zone_name_prop in _zone_cache:
            zone_rec = _zone_cache[zone_name_prop]
        else:
            for name, z in _zone_cache.items():
                if name in str(zone_name_prop) or str(zone_name_prop) in name:
                    zone_rec = z
                    break

    if zone_rec:
        zone_max_kenpei = float(zone_rec.max_kenpei)
        zone_max_youseki = float(zone_rec.max_youseki)
        if max_kenpei is None:
            max_kenpei = zone_max_kenpei
        if max_youseki is None:
            max_youseki = zone_max_youseki
    else:
        zone_max_kenpei = max_kenpei if max_kenpei is not None else 60.0
        zone_max_youseki = max_youseki if max_youseki is not None else 200.0

    if max_youseki is None or max_kenpei is None:
        zone_keyword = None
        check_text = str(youseki_raw or '') + " " + str(zone_name_prop or '')
        keywords = [
            "第一種低層", "第二種低層", "第一種中高層", "第二種中高層",
            "第一種住居", "第二種住居", "準住居", "田園住居",
            "近隣商業", "商業", "準工業", "工業", "工業専用"
        ]
        for kw in keywords:
            if kw in check_text:
                zone_keyword = kw
                break
        
        if zone_keyword:
            try:
                for name, z in _zone_cache.items():
                    if zone_keyword in name:
                        zone_rec = z
                        break
                if zone_rec:
                    zone_max_kenpei = float(zone_rec.max_kenpei)
                    zone_max_youseki = float(zone_rec.max_youseki)
                    if max_youseki is None:
                        max_youseki = zone_max_youseki
                    if max_kenpei is None:
                        max_kenpei = zone_max_kenpei
            except:
                pass
                
    if max_youseki is None:
        max_youseki = 200.0
    if max_kenpei is None:
        max_kenpei = 60.0

    # 5. 公示地価ポテンシャルマスタとの結合 (上限容積率に基づく住宅地/商業地価の動的ブレンド)
    if max_youseki <= 150.0:
        weight_comm = 0.0
    elif max_youseki >= 450.0:
        weight_comm = 1.0
    else:
        weight_comm = (max_youseki - 150.0) / 300.0
        
    weight_res = 1.0 - weight_comm
    
    # 住宅地価の取得
    res_price = None
    res_rosenka = None
    res_fixed = None
    lp_res = _lp_cache.get((address1, address2, 'residential'))
    if lp_res:
        res_price = lp_res.average_land_price
        res_rosenka = lp_res.estimated_rosenka_price
        res_fixed = lp_res.estimated_fixed_asset_price
    else:
        lp_pref_res = _lp_pref_res_cache.get(address1, [])
        if lp_pref_res:
            res_price = sum(x.average_land_price for x in lp_pref_res) / len(lp_pref_res)
            res_rosenka = sum(x.estimated_rosenka_price for x in lp_pref_res if x.estimated_rosenka_price is not None) / len(lp_pref_res)
            res_fixed = sum(x.estimated_fixed_asset_price for x in lp_pref_res if x.estimated_fixed_asset_price is not None) / len(lp_pref_res)
            
    # 商業地価の取得
    comm_price = None
    comm_rosenka = None
    comm_fixed = None
    lp_comm = _lp_cache.get((address1, address2, 'commercial'))
    if lp_comm:
        comm_price = lp_comm.average_land_price
        comm_rosenka = lp_comm.estimated_rosenka_price
        comm_fixed = lp_comm.estimated_fixed_asset_price
    else:
        lp_pref_comm = _lp_pref_comm_cache.get(address1, [])
        if lp_pref_comm:
            comm_price = sum(x.average_land_price for x in lp_pref_comm) / len(lp_pref_comm)
            comm_rosenka = sum(x.estimated_rosenka_price for x in lp_pref_comm if x.estimated_rosenka_price is not None) / len(lp_pref_comm)
            comm_fixed = sum(x.estimated_fixed_asset_price for x in lp_pref_comm if x.estimated_fixed_asset_price is not None) / len(lp_pref_comm)
            
    # ブレンド価格の計算
    def blend_value(res_val, comm_val, default):
        if res_val is not None and comm_val is not None:
            return int(res_val * weight_res + comm_val * weight_comm)
        elif res_val is not None:
            return int(res_val)
        elif comm_val is not None:
            return int(comm_val)
        return default

    # 変動率の取得とブレンド
    res_growth = float(lp_res.land_price_growth_rate) if lp_res and lp_res.land_price_growth_rate is not None else None
    comm_growth = float(lp_comm.land_price_growth_rate) if lp_comm and lp_comm.land_price_growth_rate is not None else None
    
    if res_growth is None:
        lp_pref_res = _lp_pref_res_cache.get(address1, [])
        if lp_pref_res:
            res_growth = sum(float(x.land_price_growth_rate) for x in lp_pref_res if x.land_price_growth_rate is not None) / len(lp_pref_res) if any(x.land_price_growth_rate is not None for x in lp_pref_res) else 0.0
            
    if comm_growth is None:
        lp_pref_comm = _lp_pref_comm_cache.get(address1, [])
        if lp_pref_comm:
            comm_growth = sum(float(x.land_price_growth_rate) for x in lp_pref_comm if x.land_price_growth_rate is not None) / len(lp_pref_comm) if any(x.land_price_growth_rate is not None for x in lp_pref_comm) else 0.0

    def blend_float_value(res_val, comm_val, default):
        if res_val is not None and comm_val is not None:
            return float(res_val * weight_res + comm_val * weight_comm)
        elif res_val is not None:
            return float(res_val)
        elif comm_val is not None:
            return float(comm_val)
        return default

    land_price_growth_rate = blend_float_value(res_growth, comm_growth, 0.0)

    def_res, def_comm = _get_nationwide_base_land_price(address1, address2)
    def_blend = blend_value(def_res, def_comm, 80000)
    average_land_price = blend_value(res_price, comm_price, def_blend)
    estimated_rosenka_price = blend_value(res_rosenka, comm_rosenka, int(average_land_price * 0.8))
    estimated_fixed_asset_price = blend_value(res_fixed, comm_fixed, int(average_land_price * 0.7))

    # 6. 最有効利用特徴量 (Kodate / Apartment) の算出
    digest_volume_ratio = 0.0
    surplus_volume_potential = 0.0
    non_conforming_flag = 0
    
    if property_type in ['kodate', 'apartment'] and tochi_area > 0:
        digest_volume_ratio = (tatemono_area / tochi_area) * 100.0
        surplus_volume_potential = max(0.0, max_youseki - digest_volume_ratio)
        if digest_volume_ratio > max_youseki:
            non_conforming_flag = 1

    # 6. 不動産鑑定メタ特徴量
    # 規模減退率 (Scale Discount) の算出 (1,000㎡超の大規模土地・山林の平米単価非線形減退)
    scale_discount = 1.0
    if tochi_area > 1000.0:
        scale_discount = max(0.05, float((1000.0 / tochi_area) ** 0.35))

    # 潜在延床面積 (Potential Floor Area) の算出
    if property_type == 'mansion':
        potential_floor_area = area
    else:
        potential_floor_area = tochi_area * (max_youseki / 100.0)

    # (a) 積算想定価格 (Cost Approach Value)
    kouzou_str = get_attr(property_obj, 'kouzou', '') or ''
    kouzou_cat = parse_kouzou(kouzou_str)
    cost_unit = REPLACEMENT_COSTS[kouzou_cat]
    lifespan = LIFESPAN[kouzou_cat]
    remaining_rate = max(0.1, (lifespan - chikunen) / lifespan)
    
    if property_type == 'mansion':
        land_value = (area * 0.2) * (average_land_price / 10000.0)
        building_value = area * cost_unit * remaining_rate
        cost_approach_value = land_value + building_value
    else:
        land_value = tochi_area * (average_land_price / 10000.0) * scale_discount
        building_value = tatemono_area * cost_unit * remaining_rate
        cost_approach_value = land_value + building_value

    # (b) 比準想定価格 (Market Comparison Value)
    mkt_comparison_value = 0.0
    eval_area = area if property_type == 'mansion' else tatemono_area
    if eval_area <= 0:
        eval_area = 50.0
        
    if mkt_comparison_master:
        age_band = int(chikunen // 10)
        key = (address1, address2, property_type, age_band)
        avg_unit_price = mkt_comparison_master.get(key)
        if avg_unit_price is None:
            keys_pref = [k for k in mkt_comparison_master.keys() if k[0] == address1 and k[2] == property_type and k[3] == age_band]
            if keys_pref:
                avg_unit_price = sum(mkt_comparison_master[k] for k in keys_pref) / len(keys_pref)
            else:
                avg_unit_price = 30.0
        mkt_comparison_value = avg_unit_price * eval_area
    else:
        mkt_comparison_value = eval_area * (average_land_price / 10000.0)

    # (c) 収益想定価格 (Income Approach Value - 経済的価値創出還元価値)
    gross_yield = get_attr(property_obj, 'grossYield', None)
    annual_rent = get_attr(property_obj, 'annualRent', None)
    
    if gross_yield is not None and float(gross_yield) > 0:
        cap_rate = float(gross_yield) / 100.0
    else:
        cap_rate = 0.06
        if income > 4500:
            cap_rate = 0.050
        if income > 7000:
            cap_rate = 0.040

    if annual_rent is not None and float(annual_rent) > 0:
        raw_rent = float(annual_rent)
        rent_man = (raw_rent / 10000.0) if raw_rent > 100000.0 else raw_rent
        noi_man = rent_man * 0.85
        income_approach_value = noi_man / cap_rate
    else:
        # 推定平米月額賃料 (土地価格水準・所得水準・立地ポテンシャルから算出)
        unit_rent_yen_monthly = max(1200.0, min(8000.0, average_land_price * 0.0018))
        if property_type == 'tochi':
            # 土地の収益還元 (潜在延床面積に基づく開発想定残余価格)
            dev_floor_area = potential_floor_area * 0.80
            ann_rent_man = (dev_floor_area * unit_rent_yen_monthly * 12.0) / 10000.0
            noi_man = ann_rent_man * 0.85
            dev_cost = dev_floor_area * 22.0  # 新築建築コスト (22万円/㎡)
            income_approach_value = max(0.0, (noi_man / cap_rate) - dev_cost) * scale_discount
            if income_approach_value <= 0:
                income_approach_value = tochi_area * (average_land_price / 10000.0) * scale_discount * 0.7
        else:
            ann_rent_man = (eval_area * unit_rent_yen_monthly * 12.0) / 10000.0
            noi_man = ann_rent_man * 0.85
            income_approach_value = (noi_man / cap_rate) * scale_discount

    # 7. 耐震基準フラグ (新旧耐震の判定: 1981年6月1日以降が新耐震)
    is_shin_taishin = 1  # デフォルト新耐震
    if chikunengetsu and isinstance(chikunengetsu, datetime.date):
        if chikunengetsu < datetime.date(1981, 6, 1):
            is_shin_taishin = 0
    else:
        if chikunen > 45.0:
            is_shin_taishin = 0

    # 8. ハザードマップ災害リスク (浸水・土砂リスクの追加)
    flood_risk_level = 0
    landslide_risk_level = 0
    try:
        hz = _hazard_cache.get((address1, address2))
        if hz:
            flood_risk_level = int(hz.flood_risk_level)
            landslide_risk_level = int(hz.landslide_risk_level)
    except:
        pass

    # 土地（tochi）固有の鑑定特徴量の算出
    maguchi_val = 6.0
    road_width_val = 4.0
    setback_ratio = 0.0
    actual_volume_limit = max_youseki
    volume_digest_factor = 1.0
    road_condition_factor = 1.0
    frontage_penalty_factor = 1.0
    residual_land_value = 0.0
    road_direction_str = ""
    road_type_str = ""
    road_structure_str = ""
    chimoku_str = ""
    
    if property_type in ['tochi', 'kodate', 'apartment']:
        import re
        if property_type == 'tochi':
            # 主要評価面積を土地面積とする
            area = tochi_area
            
        maguchi = get_attr(property_obj, 'maguchi', None)
        road_width = get_attr(property_obj, 'roadWidth', None) or get_attr(property_obj, 'douroHaba', None)
        road_direction_str = get_attr(property_obj, 'roadDirection', '') or get_attr(property_obj, 'douroMuki', '') or ''
        road_type_str = get_attr(property_obj, 'roadType', '') or get_attr(property_obj, 'douroKubun', '') or ''
        road_structure_str = get_attr(property_obj, 'roadStructure', '') or get_attr(property_obj, 'setsudou', '') or ''
        chimoku_str = get_attr(property_obj, 'chimoku', '') or ''
        
        # 動的パースのフォールバックロジック (カラムに値が入っていない場合)
        raw_setsudou = get_attr(property_obj, 'setsudou', '') or ''
        
        if not road_width and raw_setsudou:
            m_width = re.search(r'(\d+(?:\.\d+)?)\s*[mｍ]', raw_setsudou)
            if m_width:
                road_width = safe_float(m_width.group(1), None)
                
        if not maguchi and raw_setsudou:
            m_maguchi = re.search(r'(?:間口|接面)\s*(?:約)?\s*(\d+(?:\.\d+)?)\s*[mｍ]', raw_setsudou)
            if m_maguchi:
                maguchi = safe_float(m_maguchi.group(1), None)
                
        if not road_direction_str and raw_setsudou:
            for direction in ["北東", "北西", "南東", "南西", "東", "西", "南", "北"]:
                if direction in raw_setsudou:
                    road_direction_str = direction
                    break
                    
        if not road_type_str and raw_setsudou:
            if "公道" in raw_setsudou:
                road_type_str = "公道"
            elif "私道" in raw_setsudou:
                road_type_str = "私道"
        
        maguchi_val = safe_float(maguchi, 6.0)
        road_width_val = safe_float(road_width, 4.0)
        
        # ① セットバック（後退）面積比率 (既に上部で計算済みの値を利用)
        setback_ratio = setback_ratio_temp
                
        # ② 実質上限容積率制限 (幅員制限)
        youto = get_attr(property_obj, 'youtoChiiki', '') or ''
        is_commercial = any(x in youto for x in ["商業", "近隣商業", "工業", "準工業", "工業専用"])
        multiplier = 0.6 if is_commercial else 0.4
        road_volume_limit = road_width_val * multiplier * 100.0
        actual_volume_limit = min(max_youseki, road_volume_limit)
        
        # ③ 北側道路緩和・容積消化効率係数
        if "北" in road_direction_str and road_width_val >= 4.0:
            volume_digest_factor = 1.15
        elif "南" in road_direction_str:
            est_depth = tochi_area / maguchi_val if maguchi_val > 0 else 10.0
            if est_depth < 10.0:
                volume_digest_factor = 0.85
                
        # ④ 接道条件加算補正
        if any(x in road_structure_str for x in ["角地", "準角地", "三方", "四方"]):
            road_condition_factor = 1.05
        elif any(x in road_structure_str for x in ["二方", "両面道路"]):
            road_condition_factor = 1.03
            
        # ⑤ 間口狭小ペナルティ
        if maguchi_val < 2.0:
            frontage_penalty_factor = 0.25
        elif maguchi_val < 4.0:
            frontage_penalty_factor = 0.90
            
        # ⑥ 土地残余法比準地価 (tochi_areaは既にセットバック分控除済みのため、setback_ratioによる二重控除は行わない)
        residual_land_value = tochi_area * (average_land_price / 10000.0) * volume_digest_factor * road_condition_factor * frontage_penalty_factor

    # ⑦ 最大建築面積、最大延床面積 (前面道路幅員制限考慮)
    max_building_area = 0.0
    max_floor_area = 0.0
    
    # 角地による建ぺい率緩和 (+10.0%)
    road_struct = get_attr(property_obj, 'roadStructure', '') or get_attr(property_obj, 'setsudou', '') or ''
    is_corner = any(x in str(road_struct) for x in ["角地", "準角地", "三方", "四方"])
    effective_kenpei = max_kenpei
    if is_corner:
        effective_kenpei = min(100.0, max_kenpei + 10.0)

    if tochi_area > 0:
        max_building_area = tochi_area * (effective_kenpei / 100.0)
        vol_limit = actual_volume_limit if 'actual_volume_limit' in locals() else max_youseki
        max_floor_area = tochi_area * (vol_limit / 100.0)

    # ⑧ かげ地割合（吉野金次式）の簡易抽出
    biko_text = get_attr(property_obj, 'biko', '') or ''
    tochi_text = get_attr(property_obj, 'tochikenri', '') or ''
    
    is_hatasao = any(x in str(biko_text) or x in str(tochi_text) for x in ["旗竿", "路地状", "敷地延長", "敷延"])
    is_fuseigei = any(x in str(biko_text) or x in str(tochi_text) for x in ["不整形", "変形地", "台形地", "袋地"])
    
    # オブジェクトに明示的なかげ地割合属性がある場合は優先
    kagechi_ratio = safe_float(get_attr(property_obj, 'kagechi_ratio', None), None)
    if kagechi_ratio is None:
        if is_hatasao:
            kagechi_ratio = 0.25 # 旗竿地は平均的にかげ地割合25%と仮定
        elif is_fuseigei:
            kagechi_ratio = 0.15 # 不整形地は平均的にかげ地割合15%と仮定
        else:
            kagechi_ratio = 0.0

    # 土地形状（かげ地・最大内接矩形・うなぎの寝床・頂点数）の幾何評価
    plot_vertices = get_attr(property_obj, 'plot_vertices', None)
    if plot_vertices and len(plot_vertices) >= 3:
        shape_metrics = analyze_plot_shape(plot_vertices)
        kagechi_ratio = shape_metrics.shadow_area_ratio
        plot_shadow_ratio = shape_metrics.shadow_area_ratio
        plot_aspect_ratio = shape_metrics.mir_aspect_ratio
        plot_effective_ratio = shape_metrics.mir_effective_ratio
        plot_shape_penalty = shape_metrics.shape_penalty_score
    else:
        plot_shadow_ratio = kagechi_ratio
        plot_aspect_ratio = 1.0 if not is_fuseigei else 0.5
        plot_effective_ratio = max(0.0, 1.0 - kagechi_ratio)
        plot_shape_penalty = round(max(0.60, min(1.0, 1.0 - (kagechi_ratio * 0.35))), 4)

    # 形状ペナルティによる土地価値補正
    if property_type in ['tochi', 'kodate']:
        cost_approach_value = round(cost_approach_value * plot_shape_penalty, 2)
        mkt_comparison_value = round(mkt_comparison_value * plot_shape_penalty, 2)
        if residual_land_value > 0:
            residual_land_value = round(residual_land_value * plot_shape_penalty, 2)

    # 特徴量辞書を返却
    feats = {
        "area": area if property_type in ['mansion', 'tochi'] else tatemono_area,
        "tochi_menseki": tochi_area,
        "chikunen": chikunen,
        "walk_min": walk_min,
        "kanrihi": int(min(float(get_attr(property_obj, 'kanrihi', 0) or 0) / 10000.0, 30000.0) if float(get_attr(property_obj, 'kanrihi', 0) or 0) > 200000.0 else float(get_attr(property_obj, 'kanrihi', 0) or 0)),
        "syuzen": int(min(float(get_attr(property_obj, 'syuzenTsumitate', 0) or 0) / 10000.0, 30000.0) if float(get_attr(property_obj, 'syuzenTsumitate', 0) or 0) > 200000.0 else float(get_attr(property_obj, 'syuzenTsumitate', 0) or 0)),
        "pop_growth": pop_growth,
        "income": income,
        "passenger_volume": passenger_volume,
        "average_land_price": average_land_price,
        "estimated_rosenka_price": estimated_rosenka_price,
        "estimated_fixed_asset_price": estimated_fixed_asset_price,
        "digest_volume_ratio": digest_volume_ratio,
        "surplus_volume_potential": surplus_volume_potential,
        "non_conforming_flag": non_conforming_flag,
        "cost_approach_value": cost_approach_value,
        "mkt_comparison_value": mkt_comparison_value,
        "income_approach_value": income_approach_value,
        "gross_yield": float(gross_yield) if gross_yield else 0.0,
        "annual_rent": float(annual_rent) if annual_rent else 0.0,
        "is_shin_taishin": is_shin_taishin,
        "flood_risk_level": flood_risk_level,
        "landslide_risk_level": landslide_risk_level,
        "max_youseki": max_youseki,
        "max_kenpei": max_kenpei,
        # 土地用追加特徴量
        "maguchi": maguchi_val,
        "road_width": road_width_val,
        "setback_ratio": setback_ratio,
        "actual_volume_limit": actual_volume_limit,
        "volume_digest_factor": volume_digest_factor,
        "road_condition_factor": road_condition_factor,
        "frontage_penalty_factor": frontage_penalty_factor,
        "residual_land_value": residual_land_value,
        "max_building_area": max_building_area,
        "max_floor_area": max_floor_area,
        "kagechi_ratio": kagechi_ratio,
        "total_population": total_population,
        "income_growth_rate": income_growth_rate,
        "land_price_growth_rate": land_price_growth_rate,
        "effective_walk_min": effective_walk_min,
        "population_density": pop_density,
        "potential_floor_area": potential_floor_area,
        "scale_discount": scale_discount,
        "plot_shadow_ratio": plot_shadow_ratio,
        "plot_aspect_ratio": plot_aspect_ratio,
        "plot_effective_ratio": plot_effective_ratio,
        "plot_shape_penalty": plot_shape_penalty,
        "zone_max_kenpei": zone_max_kenpei,
        "zone_max_youseki": zone_max_youseki
    }
    
    # カテゴリカル（文字列）
    feats["prefecture"] = address1
    feats["city"] = address2
    feats["station"] = station1
    feats["company"] = company
    feats["kouzou"] = kouzou_str
    # 土地カテゴリカル
    feats["road_direction"] = road_direction_str
    feats["road_type"] = road_type_str
    feats["road_structure"] = road_structure_str
    feats["chimoku"] = chimoku_str
    # ⑨ 権利関係・制限フラグの抽出 (生のHTML全体および全記載テキスト包含検索)
    raw_html_content = get_attr(property_obj, 'raw_html', '') or get_attr(property_obj, 'rawHtml', '') or get_attr(property_obj, 'detail_html', '') or get_attr(property_obj, 'page_html', '') or ''
    
    tochikenri = get_attr(property_obj, 'tochikenri', '') or ''
    biko_val = get_attr(property_obj, 'biko', '') or ''
    kuiki = get_attr(property_obj, 'kuiki', '') or ''
    youto = get_attr(property_obj, 'youtoChiiki', '') or ''
    prop_name = get_attr(property_obj, 'propertyName', '') or ''
    setsudou_text = get_attr(property_obj, 'setsudou', '') or get_attr(property_obj, 'roadStructure', '') or ''
    notes_val = get_attr(property_obj, 'notes', '') or get_attr(property_obj, 'bikou', '') or ''
    genkyo_val = get_attr(property_obj, 'genkyo', '') or ''

    all_text_list = [raw_html_content, tochikenri, biko_val, kuiki, youto, prop_name, setsudou_text, notes_val, genkyo_val]
    combined_text = " ".join([str(x) for x in all_text_list if x])
    combined_text_lower = combined_text.lower()
    
    is_shigaika_chousei = 1.0 if ("調整区域" in combined_text or "市街化調整" in combined_text) else 0.0
    is_saikenchiku_fuka = 1.0 if ("再建築不可" in combined_text) else 0.0
    
    rights_ratio = 1.0
    if "底地" in combined_text_lower or "貸地" in combined_text_lower:
        rights_ratio = 0.20
    elif "定期" in combined_text_lower or "定借" in combined_text_lower:
        if chikunen > 0:
            remaining_ratio = max(0.20, (50 - chikunen) / 50.0)
        else:
            remaining_ratio = 0.50
        rights_ratio = 0.70 * remaining_ratio
    elif "借地" in combined_text_lower or "賃借" in combined_text_lower:
        rights_ratio = 0.65

    feats["is_shigaika_chousei"] = is_shigaika_chousei
    feats["is_saikenchiku_fuka"] = is_saikenchiku_fuka
    feats["rights_ratio"] = rights_ratio

    # ⑩ 古家付き土地（建物残存価値・解体費用控除・再建築不可特則・リノベ戸建賃貸オプション評価）
    is_furuya = 0.0
    has_demolition_condition = 0.0
    furuya_demolition_cost = 0.0
    furuya_usable_value = 0.0
    furuya_option_value = 0.0

    furuya_keywords = [
        "古家あり", "古家有", "古家付", "古家建", "上物あり", "上物有", "上物付",
        "古家解体", "建物あり", "建物有", "現況：古家", "現況古家", "上物解体", "古家付売地"
    ]
    if any(k in combined_text for k in furuya_keywords):
        is_furuya = 1.0
        
        # 解体更地渡し条件の判定（売主負担による解体）
        demolition_cond_keywords = [
            "更地渡し", "解体更地渡し", "解体後引渡", "更地引渡",
            "売主負担にて解体", "売主負担で解体", "売主にて解体", "売主側で解体"
        ]
        if any(k in combined_text for k in demolition_cond_keywords):
            has_demolition_condition = 1.0
            
        # 古家建物面積の抽出 (テキストから「建物〇㎡」「延床〇㎡」またはtatemono_area)
        furuya_bldg_area = 0.0
        m_bldg = re.search(r'(?:延床|建物)(?:面積)?[:：約]?\s*([0-9\.]+)\s*(?:㎡|平米|m2|ｍ２)', combined_text)
        if m_bldg:
            furuya_bldg_area = safe_float(m_bldg.group(1), 0.0)
        if furuya_bldg_area <= 0.0:
            furuya_bldg_area = safe_float(tatemono_area, 0.0)
        if furuya_bldg_area <= 0.0:
            furuya_bldg_area = 80.0  # 標準的な中古木造戸建の延床面積
            
        # 構造別の解体単価 (木造 1.4万円/㎡, 鉄骨 1.8万円/㎡, RC 2.5万円/㎡)
        unit_demolish = 1.4
        if "鉄骨" in combined_text:
            unit_demolish = 1.8
        elif any(x in combined_text for x in ["RC", "鉄筋"]):
            unit_demolish = 2.5
            
        if has_demolition_condition == 1.0 or is_saikenchiku_fuka == 1.0:
            # 更地渡し、または再建築不可（解体すると新築不可のため既得権維持・解体禁止）の場合は買主負担0
            furuya_demolition_cost = 0.0
        else:
            furuya_demolition_cost = round(furuya_bldg_area * unit_demolish, 2)
            
        # 古家の戸建賃貸運用・リノベーション再生価値
        unit_rent_monthly = max(1200.0, min(8000.0, average_land_price * 0.0018))
        est_monthly_rent_man = max(4.0, min(25.0, (unit_rent_monthly * furuya_bldg_area * 0.70) / 10000.0))
        est_annual_noi_man = est_monthly_rent_man * 12.0 * 0.80
        
        # 還元利回り (再建築不可は10.0%, 通常古家は8.0%)
        cap_rate_furuya = 0.10 if is_saikenchiku_fuka == 1.0 else 0.08
        gross_furuya_val = est_annual_noi_man / cap_rate_furuya
        renov_cost = furuya_bldg_area * 3.0  # リノベ費用目安: 3万円/㎡
        
        if is_saikenchiku_fuka == 1.0:
            # 再建築不可の場合、建物維持による敷地既得権利用価値を加算
            furuya_usable_value = round(max(0.0, gross_furuya_val - renov_cost) + tochi_area * (average_land_price / 10000.0) * 0.25, 2)
        else:
            furuya_usable_value = round(max(0.0, gross_furuya_val - renov_cost), 2)
            
        # オプション価値: 更地手取り価格（再建築不可の場合は新築不可による20%減価底地水準）を上回る古家再生のプレミアム
        saikenchiku_land_factor = 0.20 if is_saikenchiku_fuka == 1.0 else 1.0
        clean_land_val = max(0.0, tochi_area * (average_land_price / 10000.0) * scale_discount * saikenchiku_land_factor - furuya_demolition_cost)
        furuya_option_value = round(max(0.0, furuya_usable_value - clean_land_val), 2)
        
        # 土地評価額への古家査定反映
        if property_type == 'tochi':
            if is_saikenchiku_fuka == 1.0:
                cost_approach_value = furuya_usable_value
                income_approach_value = max(income_approach_value, furuya_usable_value)
            else:
                cost_approach_value = max(0.0, cost_approach_value - furuya_demolition_cost) + (furuya_option_value * 0.5)
                if furuya_usable_value > 0:
                    income_approach_value = max(income_approach_value, furuya_usable_value)
            if furuya_demolition_cost > 0:
                residual_land_value = max(0.0, residual_land_value - furuya_demolition_cost)

    feats["is_furuya"] = is_furuya
    feats["has_demolition_condition"] = has_demolition_condition
    feats["furuya_demolition_cost"] = furuya_demolition_cost
    feats["furuya_usable_value"] = furuya_usable_value
    feats["furuya_option_value"] = furuya_option_value
    feats["cost_approach_value"] = cost_approach_value
    feats["income_approach_value"] = income_approach_value
    feats["residual_land_value"] = residual_land_value
    
    # ⑩ 構造耐用年数消化比率 (Wood: 22年急減価, RC: 47年緩減価の相互作用)
    kouzou_cat = parse_kouzou(kouzou_str)
    lifespan_val = LIFESPAN.get(kouzou_cat, 30)
    feats["kouzou_lifespan_ratio"] = min(2.5, float(chikunen) / float(lifespan_val)) if lifespan_val > 0 else 1.0

    return feats


def build_features_batch(properties_list, property_type, base_date=None, mkt_comparison_master=None):
    """
    複数物件リストに対して一括で特徴量辞書リストを生成する高パフォーマンスヘルパー
    """
    _init_global_caches()
    results = []
    for prop in properties_list:
        try:
            feats = build_features(prop, property_type, base_date=base_date, mkt_comparison_master=mkt_comparison_master)
            results.append(feats)
        except Exception:
            # 万一の個別パース例外時は空辞書でなくデフォルト値でフォールバック
            fallback = {col: 0.0 for col in FEATURE_SETS.get(property_type, {}).get("first", [])}
            fallback["area"] = 50.0
            results.append(fallback)
    return results


"""
ML 参照マスタ（地価、自治体、駅、ハザード、用途地域、マクロ経済）管理およびキャッシュモジュール (Issue #713, Epic #710)
"""
import datetime
import logging
import re
import threading
from typing import Any

from package.ml.features.constants import PREFECTURE_BASE_LAND_PRICES
from package.ml.features.reference_records import (
    HazardMapRecord,
    LandPriceRecord,
    MacroEconomicRecord,
    MunicipalRecord,
    StationRecord,
    UrbanPlanningZoneRecord,
)

logger = logging.getLogger(__name__)

# グローバルキャッシュ変数 (軽量 dataclass slots=True レコードを保持)
_muni_cache: dict[tuple[str, str], MunicipalRecord] = {}
_muni_pref_cache: dict[str, list[MunicipalRecord]] = {}
_station_cache: dict[str, StationRecord] = {}
_lp_cache: dict[tuple[str, str, str], LandPriceRecord] = {}
_lp_pref_res_cache: dict[str, list[LandPriceRecord]] = {}
_lp_pref_comm_cache: dict[str, list[LandPriceRecord]] = {}
_hazard_cache: dict[tuple[str, str], HazardMapRecord] = {}
_zone_cache: dict[str, UrbanPlanningZoneRecord] = {}
_macro_cache: dict[str, MacroEconomicRecord] = {}

_cache_lock = threading.Lock()


def _match_tokyo_district_price(pref_clean: str, city_clean: str) -> tuple[int, int] | None:
    if any(k in city_clean for k in ["千代田区", "中央区", "港区"]):
        return 2000000, 6500000
    if any(k in city_clean for k in ["渋谷区", "新宿区", "文京区", "目黒区"]):
        return 1300000, 3800000
    if any(k in city_clean for k in ["品川区", "世田谷区", "大田区", "杉並区", "中野区", "豊島区"]):
        return 800000, 2200000
    if "区" in city_clean and ("東京" in pref_clean or pref_clean == "東京都"):
        return 550000, 1400000
    return None


def _match_regional_hub_price(pref_clean: str, city_clean: str, base_res: int, base_comm: int) -> tuple[int, int] | None:
    if any(k in city_clean for k in ["北区", "中央区", "中区", "博多区", "東山区", "下京区", "西区"]) and any(
        p in pref_clean for p in ["大阪府", "京都府", "愛知県", "福岡県", "神奈川県", "兵庫県"]
    ):
        return max(base_res * 2, 450000), max(base_comm * 2, 1800000)
    if any(k in city_clean for k in ["郡", "町", "村"]):
        return int(base_res * 0.45), int(base_comm * 0.45)
    return None


def _get_nationwide_base_land_price(prefecture: str, city: str = "") -> tuple[int, int]:
    """全国47都道府県および市区町村別の基準地価（住宅地/商業地, 円/㎡）を動的算出"""
    pref_clean = (prefecture or "").strip()
    city_clean = (city or "").strip()

    base_res, base_comm = 80000, 200000
    for p, vals in PREFECTURE_BASE_LAND_PRICES.items():
        if p in pref_clean or pref_clean in p:
            base_res, base_comm = vals
            break

    tokyo_price = _match_tokyo_district_price(pref_clean, city_clean)
    if tokyo_price:
        return tokyo_price

    regional_price = _match_regional_hub_price(pref_clean, city_clean, base_res, base_comm)
    if regional_price:
        return regional_price

    return base_res, base_comm


def _init_muni_cache(muni_cls) -> bool:
    if _muni_cache:
        return False
    _muni_pref_cache.clear()
    fields = [
        "prefecture", "city", "population_growth_rate", "average_income",
        "total_population", "income_growth_rate", "population_density",
    ]
    for row in muni_cls.objects.values(*fields):
        rec = MunicipalRecord(
            prefecture=row["prefecture"],
            city=row["city"],
            population_growth_rate=float(row["population_growth_rate"]) if row["population_growth_rate"] is not None else 0.0,
            average_income=int(row["average_income"]),
            total_population=row["total_population"],
            income_growth_rate=float(row["income_growth_rate"]) if row["income_growth_rate"] is not None else None,
            population_density=float(row["population_density"]) if row["population_density"] is not None else None,
        )
        _muni_cache[(rec.prefecture, rec.city)] = rec
        _muni_pref_cache.setdefault(rec.prefecture, []).append(rec)
    return True


def _init_lp_cache(lp_cls) -> bool:
    if _lp_cache:
        return False
    _lp_pref_res_cache.clear()
    _lp_pref_comm_cache.clear()
    fields = [
        "prefecture", "city", "average_land_price", "estimated_rosenka_price",
        "estimated_fixed_asset_price", "land_price_growth_rate", "land_use",
    ]
    for row in lp_cls.objects.values(*fields):
        rec = LandPriceRecord(
            prefecture=row["prefecture"],
            city=row["city"],
            average_land_price=int(row["average_land_price"]),
            estimated_rosenka_price=row["estimated_rosenka_price"],
            estimated_fixed_asset_price=row["estimated_fixed_asset_price"],
            land_price_growth_rate=float(row["land_price_growth_rate"]) if row["land_price_growth_rate"] is not None else None,
            land_use=row["land_use"],
        )
        _lp_cache[(rec.prefecture, rec.city, rec.land_use)] = rec
        if rec.land_use == "residential":
            _lp_pref_res_cache.setdefault(rec.prefecture, []).append(rec)
        elif rec.land_use == "commercial":
            _lp_pref_comm_cache.setdefault(rec.prefecture, []).append(rec)
    return True


def _load_stations(station_cls) -> bool:
    if _station_cache:
        return False
    for row in station_cls.objects.values("station_name", "passenger_volume"):
        rec = StationRecord(station_name=row["station_name"], passenger_volume=int(row["passenger_volume"]))
        _station_cache[rec.station_name] = rec
    return bool(_station_cache)


def _load_hazards(hazard_cls) -> bool:
    if _hazard_cache:
        return False
    for row in hazard_cls.objects.values("prefecture", "city", "flood_risk_level", "landslide_risk_level"):
        h_rec = HazardMapRecord(
            prefecture=row["prefecture"],
            city=row["city"],
            flood_risk_level=int(row["flood_risk_level"]),
            landslide_risk_level=int(row["landslide_risk_level"]),
        )
        _hazard_cache[(h_rec.prefecture, h_rec.city)] = h_rec
    return bool(_hazard_cache)


def _load_zones(zone_cls) -> bool:
    if _zone_cache:
        return False
    for row in zone_cls.objects.values("zone_name", "max_kenpei", "max_youseki"):
        z_rec = UrbanPlanningZoneRecord(
            zone_name=row["zone_name"],
            max_kenpei=int(row["max_kenpei"]),
            max_youseki=int(row["max_youseki"]),
        )
        _zone_cache[z_rec.zone_name] = z_rec
    return bool(_zone_cache)


def _load_macros(macro_cls) -> bool:
    if _macro_cache:
        return False
    macro_fields = [
        "year_month", "repi_mansion", "repi_kodate", "repi_tochi",
        "jgb_10y_yield", "nikkei_225", "tse_reit_index", "construction_cost_index",
    ]
    for row in macro_cls.objects.values(*macro_fields):
        m_rec = MacroEconomicRecord(
            year_month=row["year_month"],
            repi_mansion=float(row["repi_mansion"]) if row["repi_mansion"] is not None else None,
            repi_kodate=float(row["repi_kodate"]) if row["repi_kodate"] is not None else None,
            repi_tochi=float(row["repi_tochi"]) if row["repi_tochi"] is not None else None,
            jgb_10y_yield=float(row["jgb_10y_yield"]) if row["jgb_10y_yield"] is not None else None,
            nikkei_225=float(row["nikkei_225"]) if row["nikkei_225"] is not None else None,
            tse_reit_index=float(row["tse_reit_index"]) if row["tse_reit_index"] is not None else None,
            construction_cost_index=float(row["construction_cost_index"]) if row["construction_cost_index"] is not None else None,
        )
        _macro_cache[m_rec.year_month] = m_rec
    return bool(_macro_cache)


def _init_misc_caches(station_cls, hazard_cls, zone_cls, macro_cls) -> bool:
    loaded = _load_stations(station_cls)
    loaded |= _load_hazards(hazard_cls)
    loaded |= _load_zones(zone_cls)
    loaded |= _load_macros(macro_cls)
    return loaded


def _fill_if_empty(cache: dict, model_cls: Any, key_func: Any) -> bool:
    """後方互換性エイリアス"""
    if cache:
        return False
    for rec in model_cls.objects.all():
        cache[key_func(rec)] = rec
    return bool(cache)


def _all_caches_populated() -> bool:
    return all((_muni_cache, _lp_cache, _station_cache, _hazard_cache, _zone_cache, _macro_cache))


def _clear_all_caches() -> None:
    for cache in (_muni_cache, _muni_pref_cache, _station_cache, _lp_cache, _lp_pref_res_cache,
                  _lp_pref_comm_cache, _hazard_cache, _zone_cache, _macro_cache):
        cache.clear()


def reset_reference_caches() -> None:
    """テスト用: 全参照キャッシュを初期化"""
    with _cache_lock:
        _clear_all_caches()


def _init_global_caches(force_refresh: bool = False) -> None:
    """全 Potential 関連マスタを一括でインメモリキャッシュ"""
    if not force_refresh and _all_caches_populated():
        return

    from package.models.evaluation import (
        HazardMapPotential,
        LandPricePotential,
        MacroEconomicIndex,
        MunicipalPotential,
        StationPotential,
        UrbanPlanningZonePotential,
    )
    with _cache_lock:
        if force_refresh:
            _clear_all_caches()
        loaded = _init_muni_cache(MunicipalPotential)
        loaded |= _init_lp_cache(LandPricePotential)
        loaded |= _init_misc_caches(StationPotential, HazardMapPotential, UrbanPlanningZonePotential, MacroEconomicIndex)

    if loaded:

        from django.db import DatabaseError, connections
        try:
            connections.close_all()
        except DatabaseError as e:
            logger.debug("ML: connections.close_all failed: %s", e)


_load_all_potential_caches_once = _init_global_caches


def _get_macro_record(ym: str) -> Any:
    macro_rec = _macro_cache.get(ym)
    if not macro_rec and _macro_cache:
        sorted_keys = sorted(_macro_cache.keys())
        if ym < sorted_keys[0]:
            return _macro_cache[sorted_keys[0]]
        return _macro_cache[sorted_keys[-1]]
    return macro_rec


def _pick_macro_repi(property_type: str, repi_m: float, repi_k: float, repi_t: float) -> float:
    if property_type == 'kodate':
        return repi_k
    if property_type == 'tochi':
        return repi_t
    return repi_m


def extract_macro_features(ref_prop_date: datetime.date, property_type: str) -> tuple[float, float, float, float, float]:
    ym = f"{ref_prop_date.year:04d}-{ref_prop_date.month:02d}"
    macro_rec = _get_macro_record(ym)

    if macro_rec:
        repi_m = float(macro_rec.repi_mansion or 100.0)
        repi_k = float(macro_rec.repi_kodate or 100.0)
        repi_t = float(macro_rec.repi_tochi or 100.0)
        jgb = float(macro_rec.jgb_10y_yield or 0.0)
        nikkei = float(macro_rec.nikkei_225 or 25000.0)
        reit = float(macro_rec.tse_reit_index or 1800.0)
        const_cost = float(macro_rec.construction_cost_index or 100.0)
    else:
        repi_m, repi_k, repi_t = 100.0, 100.0, 100.0
        jgb = 0.5
        nikkei = 30000.0
        reit = 1800.0
        const_cost = 100.0

    macro_repi = _pick_macro_repi(property_type, repi_m, repi_k, repi_t)
    return macro_repi, jgb, nikkei, reit, const_cost


def query_municipal_potential(address1: str, address2: str) -> tuple[float, int, int, float, float]:
    muni = _muni_cache.get((address1, address2))
    if muni:
        pop_growth = float(muni.population_growth_rate)
        income = muni.average_income
        total_population = muni.total_population if muni.total_population is not None else 100000
        income_growth_rate = float(muni.income_growth_rate) if muni.income_growth_rate is not None else 0.0
        pop_density = float(muni.population_density) if muni.population_density is not None else 4000.0
        return pop_growth, income, total_population, income_growth_rate, pop_density

    muni_pref_vals = _muni_pref_cache.get(address1, [])
    if muni_pref_vals:
        n = len(muni_pref_vals)
        pop_growth = sum(float(x.population_growth_rate) for x in muni_pref_vals) / n
        income = int(sum(x.average_income for x in muni_pref_vals) / n)
        has_pop = [x.total_population for x in muni_pref_vals if x.total_population is not None]
        total_population = int(sum(has_pop) / len(has_pop)) if has_pop else 100000
        has_ig = [float(x.income_growth_rate) for x in muni_pref_vals if x.income_growth_rate is not None]
        income_growth_rate = (sum(has_ig) / len(has_ig)) if has_ig else 0.0
        has_pd = [float(x.population_density) for x in muni_pref_vals if x.population_density is not None]
        pop_density = (sum(has_pd) / len(has_pd)) if has_pd else 4000.0
        return pop_growth, income, total_population, income_growth_rate, pop_density

    return 0.0, 3000, 100000, 0.0, 4000.0


def query_station_volume(station1: str) -> int:
    if not station1:
        return 10000
    station_clean = station1.replace("駅", "")
    station_pot = _station_cache.get(station_clean)
    return station_pot.passenger_volume if station_pot else 10000


def calculate_effective_walk_min(walk_min: int, bus_use: int, bus_min: float, bus_walk: float, pop_density: float) -> float:
    walk_min_penalty_scale = max(0.4, min(1.0, 0.4 + 0.6 * (pop_density / 4000.0)))
    if bus_use or bus_min > 0:
        raw_access_min = float(bus_min * 1.5 + bus_walk)
        if raw_access_min < walk_min and bus_min > 0:
            raw_access_min = float(bus_min * 1.5 + walk_min)
        if raw_access_min <= 0:
            raw_access_min = float(walk_min)
    else:
        raw_access_min = float(walk_min)
    return raw_access_min * walk_min_penalty_scale


def _extract_slash_limit(text_str: str, is_youseki: bool) -> float | None:
    if '/' not in text_str:
        return None
    parts = re.findall(r'(\d+(?:\.\d+)?)\s*%?', text_str)
    if len(parts) >= 2:
        try:
            return float(parts[1]) if is_youseki else float(parts[0])
        except (ValueError, TypeError):
            pass
    return None


def _extract_limit_by_regex(text_str: str, is_youseki: bool) -> float | None:
    pattern = r'容積率?[^\d]{0,20}(\d{1,5}(?:\.\d{1,3})?)\s*%' if is_youseki else r'建[ぺペ]い率?[^\d]{0,20}(\d{1,5}(?:\.\d{1,3})?)\s*%'
    m = re.search(pattern, text_str)
    if m:
        return float(m.group(1))
    m_pct = re.search(r'(\d{1,5}(?:\.\d{1,3})?)\s*%', text_str)
    if m_pct:
        return float(m_pct.group(1))
    m_num = re.search(r'(\d{1,5}(?:\.\d{1,3})?)', text_str)
    if m_num:
        val = float(m_num.group(1))
        if 10.0 <= val <= 1500.0:
            return val
    return None


def extract_limit_value(text: Any, is_youseki: bool = False) -> float | None:
    if not text:
        return None
    text_str = str(text)
    slash_val = _extract_slash_limit(text_str, is_youseki)
    if slash_val is not None:
        return slash_val
    return _extract_limit_by_regex(text_str, is_youseki)


def _find_zone_record_by_name(zone_name_prop: str) -> Any:
    if not zone_name_prop:
        return None
    if zone_name_prop in _zone_cache:
        return _zone_cache[zone_name_prop]
    for name, z in _zone_cache.items():
        if name in str(zone_name_prop) or str(zone_name_prop) in name:
            return z
    return None


def _find_zone_record_by_keywords(check_text: str) -> Any:
    keywords = [
        "第一種低層", "第二種低層", "第一種中高層", "第二種中高層",
        "第一種住居", "第二種住居", "準住居", "田園住居",
        "近隣商業", "商業", "準工業", "工業", "工業専用"
    ]
    for kw in keywords:
        if kw in check_text:
            for name, z in _zone_cache.items():
                if kw in name:
                    return z
    return None


def _resolve_zone_from_record(zone_rec: Any, max_kenpei: float | None, max_youseki: float | None) -> tuple[float | None, float | None, float, float]:
    if not zone_rec:
        default_k = max_kenpei if max_kenpei is not None else 60.0
        default_y = max_youseki if max_youseki is not None else 200.0
        return max_kenpei, max_youseki, default_k, default_y
    zk = float(zone_rec.max_kenpei)
    zy = float(zone_rec.max_youseki)
    k = zk if max_kenpei is None else max_kenpei
    y = zy if max_youseki is None else max_youseki
    return k, y, zk, zy


def _fallback_zone_from_keywords(
    youseki_raw: Any, zone_name_prop: Any, max_kenpei: float | None, max_youseki: float | None, zk: float, zy: float
) -> tuple[float | None, float | None, float, float]:
    if max_youseki is not None and max_kenpei is not None:
        return max_kenpei, max_youseki, zk, zy
    check_text = f"{youseki_raw or ''} {zone_name_prop or ''}"
    kw_rec = _find_zone_record_by_keywords(check_text)
    if not kw_rec:
        return max_kenpei, max_youseki, zk, zy
    rec_k = float(kw_rec.max_kenpei)
    rec_y = float(kw_rec.max_youseki)
    k = rec_k if max_kenpei is None else max_kenpei
    y = rec_y if max_youseki is None else max_youseki
    return k, y, rec_k, rec_y


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _find_first_attr(property_obj: Any, attrs: tuple[str, ...]) -> Any:
    for a in attrs:
        val = _get_attr(property_obj, a, None)
        if val is not None:
            return val
    return None


def resolve_zone_limits(property_obj: Any) -> tuple[float, float, float, float, Any]:
    youseki_raw = _find_first_attr(property_obj, ('youseki', 'yousekiStr', 'kenpeiYousekiStr', 'yousekiRitsu'))
    kenpei_raw = _find_first_attr(property_obj, ('kenpei', 'kenpeiStr', 'kenpeiYousekiStr', 'kenpeiRitsu'))
    max_youseki = extract_limit_value(youseki_raw, is_youseki=True)
    max_kenpei = extract_limit_value(kenpei_raw, is_youseki=False)

    zone_name_prop = _find_first_attr(property_obj, ('zone_name', 'youtoChiiki', 'youto'))
    zone_rec = _find_zone_record_by_name(zone_name_prop)
    max_kenpei, max_youseki, zone_max_kenpei, zone_max_youseki = _resolve_zone_from_record(zone_rec, max_kenpei, max_youseki)
    max_kenpei, max_youseki, zone_max_kenpei, zone_max_youseki = _fallback_zone_from_keywords(
        youseki_raw, zone_name_prop, max_kenpei, max_youseki, zone_max_kenpei, zone_max_youseki
    )

    max_youseki = 200.0 if max_youseki is None else max_youseki
    max_kenpei = 60.0 if max_kenpei is None else max_kenpei
    return max_youseki, max_kenpei, zone_max_kenpei, zone_max_youseki, zone_name_prop


def _calculate_commercial_weight(max_youseki: float) -> float:
    if max_youseki <= 150.0:
        return 0.0
    if max_youseki >= 450.0:
        return 1.0
    return (max_youseki - 150.0) / 300.0


def _get_land_price_stats(address1: str, address2: str, land_use: str, pref_cache: dict) -> tuple[Any, Any, Any, float | None]:
    lp = _lp_cache.get((address1, address2, land_use))
    if lp:
        growth = float(lp.land_price_growth_rate) if lp.land_price_growth_rate is not None else None
        return lp.average_land_price, lp.estimated_rosenka_price, lp.estimated_fixed_asset_price, growth

    pref_list = pref_cache.get(address1, [])
    if not pref_list:
        return None, None, None, None

    n = len(pref_list)
    price = sum(x.average_land_price for x in pref_list) / n
    rosenka = sum(x.estimated_rosenka_price for x in pref_list if x.estimated_rosenka_price is not None) / n
    fixed = sum(x.estimated_fixed_asset_price for x in pref_list if x.estimated_fixed_asset_price is not None) / n
    has_g = [float(x.land_price_growth_rate) for x in pref_list if x.land_price_growth_rate is not None]
    growth = (sum(has_g) / len(has_g)) if has_g else None
    return price, rosenka, fixed, growth


def blend_land_prices(address1: str, address2: str, max_youseki: float) -> tuple[int, int, int, float]:
    weight_comm = _calculate_commercial_weight(max_youseki)
    weight_res = 1.0 - weight_comm

    res_price, res_rosenka, res_fixed, res_growth = _get_land_price_stats(
        address1, address2, 'residential', _lp_pref_res_cache
    )
    comm_price, comm_rosenka, comm_fixed, comm_growth = _get_land_price_stats(
        address1, address2, 'commercial', _lp_pref_comm_cache
    )

    def blend_val(r_val, c_val, default):
        if r_val is not None and c_val is not None:
            return int(r_val * weight_res + c_val * weight_comm)
        if r_val is not None:
            return int(r_val)
        if c_val is not None:
            return int(c_val)
        return default

    def blend_float_val(r_val, c_val, default):
        if r_val is not None and c_val is not None:
            return float(r_val * weight_res + c_val * weight_comm)
        if r_val is not None:
            return float(r_val)
        if c_val is not None:
            return float(c_val)
        return default

    land_price_growth_rate = blend_float_val(res_growth, comm_growth, 0.0)
    def_res, def_comm = _get_nationwide_base_land_price(address1, address2)
    def_blend = blend_val(def_res, def_comm, 80000)
    average_land_price = blend_val(res_price, comm_price, def_blend)
    estimated_rosenka_price = blend_val(res_rosenka, comm_rosenka, int(average_land_price * 0.8))
    estimated_fixed_asset_price = blend_val(res_fixed, comm_fixed, int(average_land_price * 0.7))

    return average_land_price, estimated_rosenka_price, estimated_fixed_asset_price, land_price_growth_rate


def query_hazard_features(address1: str, address2: str) -> tuple[int, int]:
    hz = _hazard_cache.get((address1, address2))
    flood_risk_level = hz.flood_risk_level if hz else 0
    landslide_risk_level = hz.landslide_risk_level if hz else 0
    return flood_risk_level, landslide_risk_level


# Backward compatibility aliases
_extract_macro_features = extract_macro_features
_query_municipal_potential = query_municipal_potential
_query_station_volume = query_station_volume
_calculate_effective_walk_min = calculate_effective_walk_min
_resolve_zone_limits = resolve_zone_limits
_blend_land_prices = blend_land_prices
_calculate_hazard_features = query_hazard_features

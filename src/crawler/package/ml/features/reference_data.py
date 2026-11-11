"""
ML 参照マスタ（地価、自治体、駅、ハザード、用途地域、マクロ経済）管理およびキャッシュモジュール (Issue #713, Epic #710)
"""
from collections.abc import Sequence
import datetime
import logging
import math
import re
import threading
from typing import Any

from package.ml.features.constants import (
    PREFECTURE_BASE_LAND_PRICES,
    PREFECTURE_BASE_POP_DENSITY,
)
from package.ml.features.reference_records import (
    CapRateBenchmarkRecord,
    HazardMapRecord,
    LandPricePointRecord,
    LandPriceRecord,
    MacroEconomicRecord,
    MunicipalRecord,
    RentMarketRecord,
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
_caches_initialized: bool = False

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


def _is_rural_district(city_or_address2: str) -> bool:
    if not city_or_address2:
        return False
    s = city_or_address2.strip()
    if re.search(r'^[^市]+市', s) or re.search(r'^[^区]+区', s):
        return False
    if re.search(r'^[^郡]+郡', s):
        return True
    if re.search(r'^[^町村]+[町村]', s):
        return True
    return s.endswith(("町", "村"))


def _match_regional_hub_price(pref_clean: str, city_clean: str, base_res: int, base_comm: int) -> tuple[int, int] | None:
    if any(k in city_clean for k in ["北区", "中央区", "中区", "博多区", "東山区", "下京区", "西区"]) and any(
        p in pref_clean for p in ["大阪府", "京都府", "愛知県", "福岡県", "神奈川県", "兵庫県"]
    ):
        return max(base_res * 2, 450000), max(base_comm * 2, 1800000)
    if _is_rural_district(city_clean):
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


def _to_float_or_none(val: Any) -> float | None:
    return float(val) if val is not None else None


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
            repi_mansion=_to_float_or_none(row["repi_mansion"]),
            repi_kodate=_to_float_or_none(row["repi_kodate"]),
            repi_tochi=_to_float_or_none(row["repi_tochi"]),
            jgb_10y_yield=_to_float_or_none(row["jgb_10y_yield"]),
            nikkei_225=_to_float_or_none(row["nikkei_225"]),
            tse_reit_index=_to_float_or_none(row["tse_reit_index"]),
            construction_cost_index=_to_float_or_none(row["construction_cost_index"]),
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
    global _caches_initialized
    _caches_initialized = False
    for cache in (_muni_cache, _muni_pref_cache, _station_cache, _lp_cache, _lp_pref_res_cache,
                  _lp_pref_comm_cache, _hazard_cache, _zone_cache, _macro_cache,
                  _future_pop_cache, _future_pref_cache, _muni_yearly_cache, _muni_yearly_pref_cache,
                  _station_yearly_cache, _urban_zone_cache, _urban_zone_pref_cache,
                  _rent_market_cache, _cap_rate_cache,
                  _lp_points_by_chome, _lp_points_by_town, _lp_points_by_city,
                  _lp_points_by_pref, _lp_points_by_station):
        cache.clear()


def reset_reference_caches() -> None:
    """テスト用: 全参照キャッシュを初期化"""
    with _cache_lock:
        _clear_all_caches()


def _init_global_caches(force_refresh: bool = False) -> None:
    """全 Potential 関連マスタを一括でインメモリキャッシュ"""
    global _caches_initialized
    if not force_refresh and _caches_initialized:
        return

    from package.models.evaluation import (
        CapRateBenchmarkPotential,
        HazardMapPotential,
        LandPricePointPotential,
        LandPricePotential,
        MacroEconomicIndex,
        MunicipalPotential,
        RentMarketPotential,
        StationPotential,
        UrbanPlanningZonePotential,
        MunicipalFuturePotential,
        MunicipalYearlyPotential,
        StationYearlyPotential,
        UrbanInductionZoneMaster,
    )
    with _cache_lock:
        if force_refresh:
            _clear_all_caches()
        try:
            loaded = _init_muni_cache(MunicipalPotential)
            loaded |= _init_lp_cache(LandPricePotential)
            loaded |= _init_misc_caches(StationPotential, HazardMapPotential, UrbanPlanningZonePotential, MacroEconomicIndex)
            loaded |= _init_future_and_historical_caches(
                MunicipalFuturePotential,
                MunicipalYearlyPotential,
                StationYearlyPotential,
                UrbanInductionZoneMaster,
            )
            loaded |= _init_rent_and_cap_rate_caches(RentMarketPotential, CapRateBenchmarkPotential)
            loaded |= _init_lp_point_cache(LandPricePointPotential)
            _caches_initialized = True
        except Exception as e:
            logger.warning("ML: _init_global_caches failed to load potential caches (falling back): %s", e)
            return

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


def query_municipal_potential(address1: str, address2: str) -> tuple[float | None, int | None, int | None, float | None, float]:
    muni = _muni_cache.get((address1, address2))
    if muni:
        pop_growth = float(muni.population_growth_rate)
        income = muni.average_income
        total_population = muni.total_population
        income_growth_rate = float(muni.income_growth_rate) if muni.income_growth_rate is not None else 0.0
        pop_density = float(muni.population_density) if muni.population_density is not None else 4000.0
        return pop_growth, income, total_population, income_growth_rate, pop_density

    muni_pref_vals = _muni_pref_cache.get(address1, [])
    if muni_pref_vals:
        n = len(muni_pref_vals)
        pop_growth = sum(float(x.population_growth_rate) for x in muni_pref_vals) / n
        income = int(sum(x.average_income for x in muni_pref_vals) / n)
        has_pop = [x.total_population for x in muni_pref_vals if x.total_population is not None]
        total_population = int(sum(has_pop) / len(has_pop)) if has_pop else None
        has_ig = [float(x.income_growth_rate) for x in muni_pref_vals if x.income_growth_rate is not None]
        income_growth_rate = (sum(has_ig) / len(has_ig)) if has_ig else 0.0
        has_pd = [float(x.population_density) for x in muni_pref_vals if x.population_density is not None]
        pop_density = (sum(has_pd) / len(has_pd)) if has_pd else PREFECTURE_BASE_POP_DENSITY.get(address1, 4000.0)
        return pop_growth, income, total_population, income_growth_rate, pop_density

    base_density = PREFECTURE_BASE_POP_DENSITY.get(address1, 4000.0)
    return None, None, None, None, base_density


def query_station_volume(station1: str) -> int | None:
    if not station1:
        return None
    station_clean = station1.replace("駅", "")
    station_pot = _station_cache.get(station_clean)
    return station_pot.passenger_volume if station_pot else None


def calculate_effective_walk_min(walk_min: int, bus_use: int, bus_min: float, bus_walk: float, pop_density: float) -> float:
    if bus_use or bus_min > 0:
        raw_access_min = float(bus_min * 1.5 + bus_walk)
        if raw_access_min < walk_min and bus_min > 0:
            raw_access_min = float(bus_min * 1.5 + walk_min)
        if raw_access_min <= 0:
            raw_access_min = float(walk_min)
    else:
        raw_access_min = float(walk_min)
    return float(raw_access_min)


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


def _is_designated_city_without_ward(address2: str) -> bool:
    """政令指定都市名単体（区名が含まれていない）か判定 (Issue #1277)"""
    if not address2:
        return False
    s = address2.strip()
    return bool(re.search(r'^(名古屋|大阪|横浜|京都|神戸|福岡|札幌|さいたま|千葉|仙台|広島|静岡|浜松|新潟|相模原|堺|川崎|熊本|北九州|岡山)市$', s))


def _get_designated_city_ward_median(address1: str, city_name: str, land_use: str) -> tuple[Any, Any, Any, float | None] | None:
    """政令指定都市名単体の場合、同一市内の全区レコードからロバストな中央値（Median）を算出"""
    ward_records = [
        rec for (a1, c, u), rec in _lp_cache.items()
        if a1 == address1 and c.startswith(city_name) and "区" in c and u == land_use
    ]
    if not ward_records:
        return None
    # 中央値を算出（偶数個の場合は中央2値の平均値でロバスト化）
    def _median(vals: Sequence[float | int]) -> float | int:
        if not vals:
            return 0
        n = len(vals)
        if n % 2 == 1:
            return vals[n // 2]
        mid1, mid2 = vals[n // 2 - 1], vals[n // 2]
        return (mid1 + mid2) / 2 if isinstance(mid1, float) or isinstance(mid2, float) else (mid1 + mid2) // 2

    prices = sorted(x.average_land_price for x in ward_records)
    median_price = _median(prices)
    rosenkas = sorted(x.estimated_rosenka_price for x in ward_records if x.estimated_rosenka_price is not None)
    median_rosenka = _median(rosenkas) if rosenkas else int(median_price * 0.8)
    fixeds = sorted(x.estimated_fixed_asset_price for x in ward_records if x.estimated_fixed_asset_price is not None)
    median_fixed = _median(fixeds) if fixeds else int(median_price * 0.7)
    growths = sorted(float(x.land_price_growth_rate) for x in ward_records if x.land_price_growth_rate is not None)
    median_growth = float(_median(growths)) if growths else None
    return median_price, median_rosenka, median_fixed, median_growth


def _get_land_price_stats(address1: str, address2: str, land_use: str, pref_cache: dict) -> tuple[Any, Any, Any, float | None]:
    # 政令指定都市名単体（区名なし）の場合は、都心商業地の極端な外れ値を排除するため区中央値を使用 (Issue #1277)
    if _is_designated_city_without_ward(address2):
        ward_median = _get_designated_city_ward_median(address1, address2.strip(), land_use)
        if ward_median:
            return ward_median

    lp = _lp_cache.get((address1, address2, land_use))
    if lp:
        growth = float(lp.land_price_growth_rate) if lp.land_price_growth_rate is not None else None
        return lp.average_land_price, lp.estimated_rosenka_price, lp.estimated_fixed_asset_price, growth

    # 郡部・町・村または東京都23区（区固有基準値あり）の場合は、県平均へ安易に縮小させず地区基準値へフォールバックさせる
    if _is_rural_district(address2) or _match_tokyo_district_price(address1, address2) is not None:
        return None, None, None, None

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


def calculate_regional_sensitivity_features(
    property_type: str,
    walk_min: float,
    pop_density: float,
    passenger_volume: float,
    average_land_price: float,
    area: float,
    tatemono_area: float,
    tochi_area: float,
    chikunen: float,
    scale_discount: float,
) -> tuple[float, float, float, float]:
    """
    都市部と地方における駅徒歩・築年数・面積・駅力への感応度差を変調する4つの交互作用特徴量を算出 (Issue #1003, #1008)
    """
    walk_min_elasticity = float(walk_min * math.log1p(max(0.0, float(pop_density or 0.0))))
    effective_station_dist = float(walk_min / math.log10(max(100.0, float(passenger_volume or 100.0))))
    # 高地価都市部での面積価値強度を適切にスケーリング
    area_intensity = float(area * math.sqrt(max(0.0, float(average_land_price or 0.0) / 10000.0)))

    if property_type == 'mansion':
        potential_land_val = (area * 0.2) * (average_land_price / 10000.0)
        potential_bldg_val = area * 25.0
    else:
        potential_land_val = tochi_area * (average_land_price / 10000.0) * scale_discount
        potential_bldg_val = tatemono_area * 18.0
    total_potential = potential_land_val + potential_bldg_val
    land_share = (potential_land_val / total_potential) if total_potential > 0 else 0.5
    chikunen_resistance = float(chikunen * (1.0 - land_share))

    return walk_min_elasticity, effective_station_dist, chikunen_resistance, area_intensity


# Backward compatibility aliases
_extract_macro_features = extract_macro_features
_query_municipal_potential = query_municipal_potential
_query_station_volume = query_station_volume
_calculate_effective_walk_min = calculate_effective_walk_min
_resolve_zone_limits = resolve_zone_limits
_blend_land_prices = blend_land_prices
_calculate_hazard_features = query_hazard_features
_calculate_regional_sensitivity_features = calculate_regional_sensitivity_features


# =========================================================================
# Issue #1210: 2050年将来予測・立地適正化計画・過去10年推移マスターキャッシュと抽出関数
# =========================================================================
_future_pop_cache: dict[tuple[str, str, int], Any] = {}
_future_pref_cache: dict[tuple[str, int], list[Any]] = {}
_muni_yearly_cache: dict[tuple[str, str, int], Any] = {}
_muni_yearly_pref_cache: dict[tuple[str, int], list[Any]] = {}
_station_yearly_cache: dict[tuple[str, int], Any] = {}
_urban_zone_cache: dict[tuple[str, str, str], Any] = {}
_urban_zone_pref_cache: dict[str, list[Any]] = {}


def _init_future_and_historical_caches(future_cls, muni_yearly_cls, station_yearly_cls, urban_zone_cls) -> bool:
    loaded = False
    if not _future_pop_cache:
        for r in future_cls.objects.all():
            _future_pop_cache[(r.prefecture, r.city, r.target_year)] = r
            _future_pref_cache.setdefault((r.prefecture, r.target_year), []).append(r)
        loaded |= bool(_future_pop_cache)

    if not _muni_yearly_cache:
        for r in muni_yearly_cls.objects.all():
            _muni_yearly_cache[(r.prefecture, r.city, r.year)] = r
            _muni_yearly_pref_cache.setdefault((r.prefecture, r.year), []).append(r)
        loaded |= bool(_muni_yearly_cache)

    if not _station_yearly_cache:
        for r in station_yearly_cls.objects.all():
            _station_yearly_cache[(r.station_name, r.year)] = r
        loaded |= bool(_station_yearly_cache)

    if not _urban_zone_cache:
        for r in urban_zone_cls.objects.all():
            _urban_zone_cache[(r.prefecture, r.city, r.town_name)] = r
        loaded |= bool(_urban_zone_cache)

    return loaded


def _get_pref_future_population_fallback(address1: str) -> tuple[float, float, float, float] | None:
    pref_recs = _future_pref_cache.get((address1, 2035), [])
    if not pref_recs and _future_pref_cache:
        for (p, y), recs in _future_pref_cache.items():
            if y == 2035 and (p in address1 or address1 in p):
                pref_recs = recs
                break
    if pref_recs:
        n = len(pref_recs)
        avg_change = sum(float(r.pop_change_rate_from_2020) for r in pref_recs) / n
        avg_work = sum(float(r.working_age_ratio) for r in pref_recs) / n
        avg_eld = sum(float(r.elderly_ratio) for r in pref_recs) / n
        avg_sing = sum(float(r.single_household_ratio or 45.0) for r in pref_recs) / n
        return (avg_change, avg_work, avg_eld, avg_sing)
    return None


def query_future_population_features(address1: str, address2: str) -> tuple[float, float, float, float]:
    """
    社人研2035年・2050年推計人口・世帯数ポテンシャル特徴量を抽出
    (future_pop_change_2035, working_age_ratio_2035, elderly_ratio_2035, single_household_ratio_2035)
    """
    for yr in [2035, 2030, 2040, 2025, 2045, 2050]:
        rec = _future_pop_cache.get((address1, address2, yr))
        if rec:
            return (
                float(rec.pop_change_rate_from_2020),
                float(rec.working_age_ratio),
                float(rec.elderly_ratio),
                float(rec.single_household_ratio or 45.0),
            )

    pref_fallback = _get_pref_future_population_fallback(address1)
    if pref_fallback is not None:
        return pref_fallback

    # 全国標準デフォルト（テスト環境または新設・未登録自治体向けフォールバック）
    return (-1.5, 60.0, 28.0, 42.0)


def query_urban_induction_zone_features(address1: str, address2: str, town_name: str = "") -> tuple[float, float]:
    """
    国土交通省立地適正化計画（都市機能誘導区域・居住誘導区域）特徴量を抽出
    (is_urban_induction_zone, is_residential_induction_zone)
    """
    rec = _urban_zone_cache.get((address1, address2, town_name)) or _urban_zone_cache.get((address1, address2, ""))
    if rec:
        return (1.0 if rec.is_urban_induction_zone else 0.0, 1.0 if rec.is_residential_induction_zone else 0.0)

    # 都心部はデフォルトで誘導区域内判定
    if address1 == "東京都" and any(k in address2 for k in ["区", "市"]):
        return (1.0, 1.0)

    # デフォルトは誘導区域外（テスト環境や未策定自治体向け）
    return (0.0, 0.0)


def query_historical_momentum_features(address1: str, address2: str, station1: str, ref_year: int = 2024) -> tuple[float, float, float]:
    """
    過去実績時系列推移モメンタム特徴量を抽出
    (station_volume_3y_cagr, municipal_income_3y_cagr, municipal_pop_growth_momentum)
    """
    st_clean = (station1 or "").replace("駅", "")
    st_rec = _station_yearly_cache.get((st_clean, ref_year)) or _station_yearly_cache.get((st_clean, 2023))
    st_cagr = float(st_rec.volume_3y_cagr or 0.0) if st_rec else 0.0

    muni_rec = _muni_yearly_cache.get((address1, address2, ref_year)) or _muni_yearly_cache.get((address1, address2, 2023))
    if muni_rec:
        inc_cagr = float(muni_rec.income_3y_cagr or 0.0)
        pop_momentum = float(muni_rec.population_growth_rate or 0.0)
        return (st_cagr, inc_cagr, pop_momentum)

    # 都道府県平均フォールバック
    pref_muni_recs = _muni_yearly_pref_cache.get((address1, ref_year), []) or _muni_yearly_pref_cache.get((address1, 2023), [])
    if pref_muni_recs:
        n = len(pref_muni_recs)
        avg_inc_cagr = sum(float(r.income_3y_cagr or 0.0) for r in pref_muni_recs) / n
        avg_pop_mom = sum(float(r.population_growth_rate or 0.0) for r in pref_muni_recs) / n
        return (st_cagr, avg_inc_cagr, avg_pop_mom)

    # 全国標準デフォルト（テスト環境向け）
    return (0.0, 1.2, 0.5)


_query_future_population_features = query_future_population_features
_query_urban_induction_zone_features = query_urban_induction_zone_features
_query_historical_momentum_features = query_historical_momentum_features

_rent_market_cache: dict[tuple[str, str, str, str, str], list[RentMarketRecord]] = {}
_cap_rate_cache: dict[tuple[str, str, str, str], list[CapRateBenchmarkRecord]] = {}

_RENT_SOURCE_PRIORITY: dict[str, int] = {
    "suumo_soba": 50,
    "athome_souba": 40,
    "homes_price": 40,
    "internal_db": 35,
    "estat_housing": 10,
}

_CAP_SOURCE_PRIORITY: dict[str, int] = {
    "jrei_survey": 50,
    "internal_db": 45,
    "homes_toushi": 40,
    "japan_reit": 25,
}


def _load_rent_market_records(rent_cls: Any) -> bool:
    if _rent_market_cache:
        return False
    rows = rent_cls.objects.values(
        "prefecture", "city", "station_name", "town_name",
        "building_type", "layout_type", "age_band",
        "monthly_rent_yen", "standard_area_sqm", "rent_per_sqm",
        "sample_count", "source",
    )
    for r in rows:
        rec = RentMarketRecord(
            prefecture=r["prefecture"],
            city=r["city"] or "",
            station_name=r["station_name"] or "",
            town_name=r["town_name"] or "",
            building_type=r["building_type"] or "all",
            layout_type=r["layout_type"] or "all",
            age_band=r["age_band"] or "all",
            monthly_rent_yen=int(r["monthly_rent_yen"]),
            standard_area_sqm=float(r["standard_area_sqm"]),
            rent_per_sqm=int(r["rent_per_sqm"]),
            sample_count=r["sample_count"],
            source=r["source"],
        )
        key = (rec.prefecture, rec.city, rec.station_name, rec.building_type, rec.layout_type)
        _rent_market_cache.setdefault(key, []).append(rec)
    return bool(_rent_market_cache)


def _opt_float(val: Any) -> float | None:
    return float(val) if val is not None else None


def _opt_int(val: Any) -> int | None:
    return int(val) if val is not None else None


def _to_cap_rate_record(r: dict[str, Any]) -> CapRateBenchmarkRecord:
    return CapRateBenchmarkRecord(
        prefecture=r["prefecture"],
        city=r["city"] or "",
        station_name=r["station_name"] or "",
        asset_type=r["asset_type"] or "all",
        expected_gross_yield=_opt_float(r["expected_gross_yield"]),
        expected_net_cap_rate=_opt_float(r["expected_net_cap_rate"]),
        standard_opex_ratio=float(r["standard_opex_ratio"] or 20.0),
        rental_vacancy_rate=_opt_float(r["rental_vacancy_rate"]),
        total_vacancy_rate=_opt_float(r["total_vacancy_rate"]),
        jgb_spread_bps=_opt_int(r["jgb_spread_bps"]),
        demand_supply_score=_opt_float(r["demand_supply_score"]),
        sample_count=r["sample_count"],
        survey_period=r["survey_period"] or "",
        source=r["source"],
    )


def _load_cap_rate_records(cap_cls: Any) -> bool:
    if _cap_rate_cache:
        return False
    rows = cap_cls.objects.values(
        "prefecture", "city", "station_name", "asset_type",
        "expected_gross_yield", "expected_net_cap_rate", "standard_opex_ratio",
        "rental_vacancy_rate", "total_vacancy_rate", "jgb_spread_bps",
        "demand_supply_score", "sample_count", "survey_period", "source",
    )
    for r in rows:
        rec = _to_cap_rate_record(r)
        key = (rec.prefecture, rec.city, rec.station_name, rec.asset_type)
        _cap_rate_cache.setdefault(key, []).append(rec)
    return bool(_cap_rate_cache)


def _init_rent_and_cap_rate_caches(rent_cls: Any, cap_cls: Any) -> bool:
    loaded = False
    try:
        loaded |= _load_rent_market_records(rent_cls)
    except Exception as exc:
        logger.debug("ML: _load_rent_market_records skipped: %s", exc)
    try:
        loaded |= _load_cap_rate_records(cap_cls)
    except Exception as exc:
        logger.debug("ML: _load_cap_rate_records skipped: %s", exc)
    return loaded


def _clean_station_query(station_name: str) -> str:
    st = (station_name or "").strip()
    if st.endswith("駅") and len(st) > 1:
        st = st[:-1]
    return st.strip()


def query_rent_market_potential(
    prefecture: str,
    city: str = "",
    station_name: str = "",
    building_type: str = "all",
    layout_type: str = "all",
) -> tuple[int, str] | None:
    """駅 ➔ 市区町村 ➔ 都道府県の階層カスケードで月額賃料単価 (円/㎡, source) を O(1) 検索する。"""
    _init_global_caches()
    pref = (prefecture or "").strip()
    cty = (city or "").strip()
    st = _clean_station_query(station_name)

    geo_levels: list[tuple[str, str, str]] = []
    if st and cty:
        geo_levels.append((pref, cty, st))
    if st:
        geo_levels.append((pref, "", st))
    if cty:
        geo_levels.append((pref, cty, ""))
    geo_levels.append((pref, "", ""))

    spec_levels = [
        (building_type, layout_type),
        (building_type, "all"),
        ("all", layout_type),
        ("all", "all"),
    ]

    for g_pref, g_city, g_st in geo_levels:
        for b_type, l_type in spec_levels:
            candidates = _rent_market_cache.get((g_pref, g_city, g_st, b_type, l_type))
            if candidates:
                best = max(candidates, key=lambda r: _RENT_SOURCE_PRIORITY.get(r.source, 0))
                return (best.rent_per_sqm, best.source)
    return None


def _is_reliable_cap_yield_record(r: CapRateBenchmarkRecord) -> bool:
    if r.expected_net_cap_rate is None and r.expected_gross_yield is None:
        return False
    if r.source != "internal_db":
        return True
    samples = r.sample_count or 0
    if r.expected_net_cap_rate is not None:
        net_val = r.expected_net_cap_rate
    else:
        net_val = (r.expected_gross_yield or 0.0) * 0.8
    if samples < 3 and (net_val > 7.5 or net_val < 2.8):
        return False
    return 2.2 <= net_val <= 9.5


def _score_cap_candidate(r: CapRateBenchmarkRecord, target_asset_type: str) -> tuple[int, int]:
    is_exact = 1 if (target_asset_type != "all" and r.asset_type == target_asset_type) else 0
    return (is_exact, _CAP_SOURCE_PRIORITY.get(r.source, 0))


def _pick_best_cap_record(
    candidates: list[CapRateBenchmarkRecord],
    target_asset_type: str = "all",
) -> CapRateBenchmarkRecord | None:
    with_yield = [r for r in candidates if _is_reliable_cap_yield_record(r)]
    if not with_yield:
        return None
    best = max(with_yield, key=lambda r: _score_cap_candidate(r, target_asset_type))
    if best.rental_vacancy_rate is not None:
        return best
    vac_donor = next((r for r in candidates if r.rental_vacancy_rate is not None), None)
    if vac_donor is None:
        return best
    return CapRateBenchmarkRecord(
        prefecture=best.prefecture,
        city=best.city,
        station_name=best.station_name,
        asset_type=best.asset_type,
        expected_gross_yield=best.expected_gross_yield,
        expected_net_cap_rate=best.expected_net_cap_rate,
        standard_opex_ratio=best.standard_opex_ratio,
        rental_vacancy_rate=vac_donor.rental_vacancy_rate,
        total_vacancy_rate=vac_donor.total_vacancy_rate,
        jgb_spread_bps=best.jgb_spread_bps,
        demand_supply_score=vac_donor.demand_supply_score or best.demand_supply_score,
        sample_count=best.sample_count,
        survey_period=best.survey_period,
        source=best.source,
    )


def _build_cap_geo_levels(prefecture: str, city: str, station_name: str) -> list[tuple[str, str, str]]:
    pref = (prefecture or "").strip()
    cty = (city or "").strip()
    st = _clean_station_query(station_name)
    levels: list[tuple[str, str, str]] = []
    if st and cty:
        levels.append((pref, cty, st))
    if st:
        levels.append((pref, "", st))
    if cty:
        levels.append((pref, cty, ""))
    levels.append((pref, "", ""))
    levels.append(("全国", "", ""))
    return levels


def _search_exact_asset_cap_benchmark(
    geo_levels: list[tuple[str, str, str]],
    asset_type: str,
) -> CapRateBenchmarkRecord | None:
    for g_pref, g_city, g_st in geo_levels:
        exact_candidates = _cap_rate_cache.get((g_pref, g_city, g_st, asset_type), [])
        if not exact_candidates:
            continue
        donor_candidates = _cap_rate_cache.get((g_pref, g_city, g_st, "all"), [])
        picked = _pick_best_cap_record(exact_candidates + donor_candidates, target_asset_type=asset_type)
        if picked is not None and picked.asset_type == asset_type:
            return picked
    return None


def query_cap_rate_benchmark(
    prefecture: str,
    city: str = "",
    station_name: str = "",
    asset_type: str = "all",
) -> CapRateBenchmarkRecord | None:
    """駅 ➔ 市区町村 ➔ 都道府県 ➔ 全国の階層カスケードで期待利回り・空室率レコードを検索する。"""
    _init_global_caches()
    geo_levels = _build_cap_geo_levels(prefecture, city, station_name)
    if asset_type != "all":
        exact = _search_exact_asset_cap_benchmark(geo_levels, asset_type)
        if exact is not None:
            return exact

    for g_pref, g_city, g_st in geo_levels:
        all_candidates = _cap_rate_cache.get((g_pref, g_city, g_st, "all"), [])
        picked_all = _pick_best_cap_record(all_candidates, target_asset_type="all")
        if picked_all is not None:
            return picked_all
    return None



# =========================================================================
# Issue #1360: 地価公示(L01)・地価調査(L02) 地点座標KNN & 町丁目ミクロ地価エンジン
# =========================================================================
_lp_points_by_chome: dict[str, list[LandPricePointRecord]] = {}
_lp_points_by_town: dict[str, list[LandPricePointRecord]] = {}
_lp_points_by_city: dict[tuple[str, str], list[LandPricePointRecord]] = {}
_lp_points_by_pref: dict[str, list[LandPricePointRecord]] = {}
_lp_points_by_station: dict[tuple[str, str], list[LandPricePointRecord]] = {}
_CHOME_TRAILING_DIGITS = "0123456789０１２３４５６７８９"


def _strip_chome_digits(chome_key: str) -> str:
    return (chome_key or "").rstrip(_CHOME_TRAILING_DIGITS).strip()


def _index_land_price_point(rec: LandPricePointRecord) -> None:
    if rec.chome_key:
        _lp_points_by_chome.setdefault(rec.chome_key, []).append(rec)
        town_key = _strip_chome_digits(rec.chome_key)
        if town_key:
            _lp_points_by_town.setdefault(town_key, []).append(rec)
    _lp_points_by_city.setdefault((rec.prefecture, rec.city), []).append(rec)
    _lp_points_by_pref.setdefault(rec.prefecture, []).append(rec)
    st_clean = _clean_station_query(rec.station_name)
    if st_clean:
        _lp_points_by_station.setdefault((rec.prefecture, st_clean), []).append(rec)


def _init_lp_point_cache(lp_point_cls: Any) -> bool:
    if _lp_points_by_pref:
        return False
    try:
        rows = lp_point_cls.objects.values(
            "prefecture", "city", "chome_key", "latitude", "longitude",
            "land_price", "growth_rate", "land_use", "road_width",
            "station_name", "station_distance_m", "has_gas", "has_water", "has_sewer",
        )
        for r in rows:
            rec = LandPricePointRecord(
                prefecture=r["prefecture"],
                city=r["city"],
                chome_key=r["chome_key"] or "",
                latitude=float(r["latitude"]),
                longitude=float(r["longitude"]),
                land_price=int(r["land_price"]),
                growth_rate=_opt_float(r["growth_rate"]),
                land_use=r["land_use"] or "residential",
                road_width=_opt_float(r["road_width"]),
                station_name=r["station_name"] or "",
                station_distance_m=_opt_int(r["station_distance_m"]),
                has_gas=bool(r["has_gas"]),
                has_water=bool(r["has_water"]),
                has_sewer=bool(r["has_sewer"]),
            )
            _index_land_price_point(rec)
    except Exception as exc:
        logger.debug("ML: _init_lp_point_cache skipped: %s", exc)
    return bool(_lp_points_by_pref)


def set_land_price_point_cache_for_test(records: Sequence[LandPricePointRecord]) -> None:
    """単体テスト用: インメモリ地点地価キャッシュを直接差し替える。"""
    with _cache_lock:
        for cache in (
            _lp_points_by_chome, _lp_points_by_town,
            _lp_points_by_city, _lp_points_by_pref, _lp_points_by_station,
        ):
            cache.clear()
        for rec in records:
            _index_land_price_point(rec)


def _point_infra_score(rec: LandPricePointRecord) -> float:
    return (0.35 if rec.has_gas else 0.0) + (0.30 if rec.has_water else 0.0) + (0.35 if rec.has_sewer else 0.0)


def _point_use_weight(rec: LandPricePointRecord, comm_weight: float) -> float:
    if rec.land_use == "commercial":
        return 0.25 + 0.75 * comm_weight
    return 0.25 + 0.75 * (1.0 - comm_weight)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * r_km * math.asin(min(1.0, math.sqrt(a)))


def _aggregate_weighted_points(
    weighted_pts: Sequence[tuple[LandPricePointRecord, float]],
    fallback_price: int,
) -> tuple[int, float]:
    total_w = sum(w for _, w in weighted_pts)
    if total_w <= 0.0:
        return fallback_price, 1.0 if fallback_price >= 250000 else 0.85
    price_val = round(sum(rec.land_price * w for rec, w in weighted_pts) / total_w)
    infra_val = round(sum(_point_infra_score(rec) * w for rec, w in weighted_pts) / total_w, 4)
    return max(1000, int(price_val)), infra_val


def _knn_interpolate_points(
    candidates: Sequence[LandPricePointRecord],
    lat: float,
    lon: float,
    comm_weight: float,
    k: int = 5,
    max_dist_km: float = 15.0,
) -> list[tuple[LandPricePointRecord, float]]:
    scored: list[tuple[float, LandPricePointRecord]] = []
    for rec in candidates:
        dist_km = _haversine_km(lat, lon, rec.latitude, rec.longitude)
        if dist_km <= max_dist_km:
            scored.append((dist_km, rec))
    if not scored:
        return []
    scored.sort(key=lambda pair: pair[0])
    top_k = scored[:k]
    return [
        (rec, _point_use_weight(rec, comm_weight) / ((dist_km + 0.15) ** 2))
        for dist_km, rec in top_k
    ]


def _resolve_station_points(pref: str, cty: str, station_name: str) -> Sequence[LandPricePointRecord] | None:
    st_clean = _clean_station_query(station_name)
    st_pts = _lp_points_by_station.get((pref, st_clean)) if st_clean else None
    if not st_pts:
        return None
    if not cty:
        return st_pts
    city_filtered = [r for r in st_pts if r.city == cty]
    return city_filtered or st_pts


def _resolve_hierarchy_points(
    pref: str, cty: str, chome_group: str, station_name: str
) -> Sequence[LandPricePointRecord] | None:
    if chome_group and chome_group in _lp_points_by_chome:
        return _lp_points_by_chome[chome_group]
    town_key = _strip_chome_digits(chome_group)
    if town_key and town_key in _lp_points_by_town:
        return _lp_points_by_town[town_key]
    st_pts = _resolve_station_points(pref, cty, station_name)
    if st_pts:
        return st_pts
    return _lp_points_by_city.get((pref, cty))


def query_micro_land_price_features(
    prefecture: str,
    city: str,
    chome_group: str,
    max_youseki: float,
    fallback_muni_price: int,
    station_name: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
) -> tuple[int, float]:
    """
    座標KNN(IDW) ➔ 町丁目完全一致 ➔ 大字・町名一致 ➔ 最寄駅一致 ➔ 市区町村基準地価の順で
    ミクロ地価単価 `micro_land_price` (円/㎡) とインフラ整備度 `chome_infra_score` (0.0〜1.0) を算出する。
    """
    _init_global_caches()
    comm_w = _calculate_commercial_weight(max_youseki)
    pref = (prefecture or "").strip()
    cty = (city or "").strip()

    # 1. 緯度経度がある場合は空間KNN（逆距離二乗加重 IDW）を最優先
    if latitude is not None and longitude is not None:
        pool = _lp_points_by_pref.get(pref) or [
            rec for pts in _lp_points_by_pref.values() for rec in pts
        ]
        knn_weighted = _knn_interpolate_points(pool, float(latitude), float(longitude), comm_w)
        if knn_weighted:
            return _aggregate_weighted_points(knn_weighted, fallback_muni_price)

    # 2〜5. 町丁目完全一致 ➔ 大字・町名一致 ➔ 最寄駅一致 ➔ 市区町村平均
    matched_pts = _resolve_hierarchy_points(pref, cty, chome_group or "", station_name)
    if matched_pts:
        weighted = [(rec, _point_use_weight(rec, comm_w)) for rec in matched_pts]
        return _aggregate_weighted_points(weighted, fallback_muni_price)

    default_infra = 1.0 if fallback_muni_price >= 250000 else 0.85
    return int(max(1000, fallback_muni_price)), default_infra


def query_hierarchy_centroid(
    prefecture: str,
    city: str,
    chome_group: str,
    station_name: str = "",
) -> tuple[float | None, float | None]:
    """町丁目 ➔ 町名 ➔ 最寄駅 ➔ 市区町村の公的地点座標重心 `(lat, lon)` を O(1) で返す。"""
    _init_global_caches()
    pts = _resolve_hierarchy_points((prefecture or "").strip(), (city or "").strip(), chome_group or "", station_name)
    if not pts:
        return None, None
    return (
        sum(r.latitude for r in pts) / len(pts),
        sum(r.longitude for r in pts) / len(pts),
    )


_query_micro_land_price_features = query_micro_land_price_features
_query_hierarchy_centroid = query_hierarchy_centroid

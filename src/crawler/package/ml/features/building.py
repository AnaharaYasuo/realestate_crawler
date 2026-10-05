"""
ML 建物マスタ（一括プリフェッチ・設備・耐震・地代）モジュール (Issue #713, Epic #710)
"""
import logging
import re
from typing import Any

from package.ml.features.parsers import safe_float
from package.utils import converter

logger = logging.getLogger(__name__)

_BM_PREFETCH_CHUNK = 500  # SQLite の変数上限(999)を超えないよう IN 句を分割


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def building_master_key(property_obj: Any) -> tuple[str, str] | None:
    try:
        from package.utils.building_resolver import (
            normalize_building_address,
            normalize_building_name,
        )
        p_name = _get_attr(property_obj, 'propertyName', '') or _get_attr(property_obj, 'title', '') or ''
        p_addr = _get_attr(property_obj, 'address', '') or ''
        n_name = normalize_building_name(p_name)
        n_addr = normalize_building_address(p_addr)
    except (ImportError, AttributeError, ValueError, TypeError):
        return None
    return (n_name, n_addr) if n_name and n_addr else None


def prefetch_building_masters(properties_list: list) -> dict[tuple[str, str], Any] | None:
    """建物マスタ未紐付けの物件について、正規化キーで BuildingMaster を一括取得する"""
    keys = set()
    for prop in properties_list:
        if _get_attr(prop, 'building_master', None):
            continue
        key = building_master_key(prop)
        if key:
            keys.add(key)
    if not keys:
        return {}
    lookup = {}
    try:

        from package.models.building_master import BuildingMaster
        names = sorted({k[0] for k in keys})
        for i in range(0, len(names), _BM_PREFETCH_CHUNK):
            for bm in BuildingMaster.objects.filter(normalized_name__in=names[i:i + _BM_PREFETCH_CHUNK]):
                key = (bm.normalized_name, bm.normalized_address)
                if key in keys:
                    lookup.setdefault(key, bm)
    except Exception:
        logger.warning("ML: BuildingMaster prefetch failed; falling back to per-property lookup", exc_info=True)
        return None
    return lookup


def resolve_building_master_obj(property_obj: Any, bm_lookup: dict | None = None) -> Any:
    bm_obj = _get_attr(property_obj, 'building_master', None)
    if bm_obj:
        return bm_obj
    key = building_master_key(property_obj)
    if not key:
        return None
    if bm_lookup is not None:
        return bm_lookup.get(key)

    from django.db import DatabaseError
    try:
        from package.models.building_master import BuildingMaster
        return BuildingMaster.objects.filter(normalized_name=key[0], normalized_address=key[1]).first()
    except DatabaseError:
        return None


def _extract_bm_seismic_and_elevator(bm_obj: Any, combined_text: str) -> tuple[float, float]:
    eq_res = getattr(bm_obj, 'earthquake_resistance', '') or ''
    if "免震" in str(eq_res):
        seismic = 1.0
    elif "制震" in str(eq_res):
        seismic = 0.5
    else:
        seismic = 0.0

    ev_avail = getattr(bm_obj, 'elevator_available', None) if bm_obj else None
    if ev_avail is True:
        has_ev = 1.0
    elif ev_avail is False:
        has_ev = -1.0
    else:
        has_ev = 1.0 if re.search(r'エレベーター|EV', combined_text) else 0.0
    return seismic, has_ev


def extract_land_rent_features(property_obj: Any, combined_text: str) -> tuple[float, float, float, float]:
    raw_chidai = _get_attr(property_obj, 'chidai', None)
    if raw_chidai is None:
        raw_chidai_str = _get_attr(property_obj, 'chidaiStr', '')
        if raw_chidai_str:
            raw_chidai = converter.parse_chidai(raw_chidai_str)
    if raw_chidai is None and re.search(r'借地権|地上権|賃借権', combined_text):
        rent_match = re.search(r'((?:地代|借地料)[^\d\r\n]{0,15}\d[\d,]*(?:\.\d+)?\s*万?円(?:\s*/\s*[年月])?)', combined_text)
        if rent_match:
            raw_chidai = converter.parse_chidai(rent_match.group(1))

    monthly_land_rent = (float(raw_chidai) / 10000.0) if raw_chidai and float(raw_chidai) > 0 else 0.0
    annual_land_rent = monthly_land_rent * 12.0
    land_rent_liability = annual_land_rent / 0.05 if annual_land_rent > 0 else 0.0
    raw_p = _get_attr(property_obj, 'price', 0)
    price_man_val = (float(raw_p) / 10000.0) if raw_p and float(raw_p) > 100000 else float(raw_p or 0.0)
    land_rent_ratio = (annual_land_rent / price_man_val) if price_man_val > 0 else 0.0
    return monthly_land_rent, annual_land_rent, land_rent_liability, land_rent_ratio


def extract_building_master_and_amenity_features(
    property_obj: Any, combined_text: str, bm_lookup: dict | None = None
) -> dict[str, float]:
    bm_obj = resolve_building_master_obj(property_obj, bm_lookup)
    dev_tier = getattr(bm_obj, 'developer_tier', 'unknown') if bm_obj else 'unknown'
    dev_scores = {"major_reputable": 1.0, "standard": 0.5}
    contractor_tier = getattr(bm_obj, 'contractor_tier', 'unknown') if bm_obj else 'unknown'
    cont_scores = {"super_general": 1.0, "major": 0.6}

    seismic, has_ev = _extract_bm_seismic_and_elevator(bm_obj, combined_text)
    hallway = getattr(bm_obj, 'hallway_type', '') or ''
    is_indoor = 1.0 if "内廊下" in str(hallway) or "内廊下" in combined_text else 0.0
    gb = getattr(bm_obj, 'garbage_disposal_24h', None) if bm_obj else None
    has_gb = 1.0 if gb or "24時間ゴミ出し" in combined_text or "ゴミステーション" in combined_text else 0.0

    (
        monthly_land_rent, annual_land_rent, land_rent_liability, land_rent_ratio
    ) = extract_land_rent_features(property_obj, combined_text)

    return {
        "bm_brand_tier_score": dev_scores.get(dev_tier, 0.0),
        "bm_contractor_tier_score": cont_scores.get(contractor_tier, 0.0),
        "bm_is_seismic_isolated": seismic,
        "bm_has_elevator": has_ev,
        "bm_is_indoor_hallway": is_indoor,
        "bm_has_24h_garbage": has_gb,
        "has_disposer": 1.0 if re.search(r'ディスポーザー', combined_text) else 0.0,
        "is_corner_unit": 1.0 if re.search(r'角部屋|角住戸', combined_text) else 0.0,
        "is_leasehold": 1.0 if re.search(r'借地権|地上権|賃借権', combined_text) else 0.0,
        "has_psychological_defect": 1.0 if re.search(r'告知事項|心理的瑕疵', combined_text) else 0.0,
        "monthly_land_rent": monthly_land_rent,
        "annual_land_rent": annual_land_rent,
        "land_rent_liability": land_rent_liability,
        "land_rent_ratio": land_rent_ratio,
        "visual_adjustment_percent": safe_float(_get_attr(property_obj, 'visual_adjustment_percent', 0.0), 0.0)
    }


from package.ml.features.constants import LIFESPAN
from package.ml.features.parsers import parse_kouzou


def calculate_kanri_and_lifespan(property_obj: Any, chikunen: float) -> tuple[int, int, str, float]:
    raw_kanri = float(_get_attr(property_obj, 'kanrihi', 0) or 0)
    kanrihi = int(min(raw_kanri / 10000.0, 30000.0) if raw_kanri > 200000.0 else raw_kanri)
    raw_syuzen = float(_get_attr(property_obj, 'syuzenTsumitate', 0) or 0)
    syuzen = int(min(raw_syuzen / 10000.0, 30000.0) if raw_syuzen > 200000.0 else raw_syuzen)
    kouzou_str = _get_attr(property_obj, 'kouzou', '') or _get_attr(property_obj, 'structure', '') or ''
    kouzou_cat = parse_kouzou(kouzou_str)
    lifespan_val = LIFESPAN.get(kouzou_cat, 30)
    kouzou_lifespan_ratio = min(2.5, float(chikunen) / float(lifespan_val)) if lifespan_val > 0 else 1.0
    return kanrihi, syuzen, kouzou_str, kouzou_lifespan_ratio


_calculate_kanri_and_lifespan = calculate_kanri_and_lifespan
_prefetch_building_masters = prefetch_building_masters
_extract_building_master_and_amenity_features = extract_building_master_and_amenity_features

_extract_land_rent_features = extract_land_rent_features
_resolve_building_master_obj = resolve_building_master_obj

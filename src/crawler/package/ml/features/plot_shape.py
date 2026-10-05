"""
ML 敷地形状・旗竿地・不整形地解析モジュール (Issue #713, Epic #710)
"""
from typing import Any

from package.ml.features.parsers import safe_float
from package.utils.plot_shape_analyzer import analyze_plot_shape


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _build_shape_metrics_features(shape_metrics: Any) -> tuple[dict[str, float], float]:
    shape_code_map = {'regular': 1.0, 'irregular': 2.0, 'slender': 3.0, 'flagpole': 4.0}
    s_type = getattr(shape_metrics, 'shape_type', 'regular')
    return {
        "kagechi_ratio": shape_metrics.shadow_area_ratio,
        "plot_shadow_ratio": shape_metrics.shadow_area_ratio,
        "plot_aspect_ratio": shape_metrics.mir_aspect_ratio,
        "plot_effective_ratio": shape_metrics.mir_effective_ratio,
        "plot_shape_penalty": shape_metrics.shape_penalty_score,
        "plot_mic_diameter": shape_metrics.mic_diameter,
        "plot_bottleneck_width": shape_metrics.bottleneck_width,
        "plot_solidity": shape_metrics.solidity,
        "plot_compactness": shape_metrics.compactness,
        "plot_nta_discount": shape_metrics.nta_composite_discount,
        "plot_acute_angles": float(shape_metrics.acute_angle_count),
        "plot_flagpole_ratio": shape_metrics.flagpole_passage_ratio,
        "plot_shape_grade_num": float(shape_metrics.shape_grade_num),
        "plot_shape_score_100": shape_metrics.shape_score_100,
        "shape_type_code": shape_code_map.get(s_type, 1.0),
        "is_regular_shape": 1.0 if s_type == 'regular' else 0.0
    }, shape_metrics.shape_penalty_score


def _build_fallback_shape_features(is_hatasao: bool, is_fuseigei: bool, kagechi_ratio: float) -> tuple[dict[str, float], float]:
    shape_penalty = round(max(0.60, min(1.0, 1.0 - (kagechi_ratio * 0.35))), 4)
    if is_hatasao:
        s_type = 'flagpole'
    elif is_fuseigei:
        s_type = 'irregular'
    else:
        s_type = 'regular'
    shape_code_map = {'regular': 1.0, 'irregular': 2.0, 'slender': 3.0, 'flagpole': 4.0}
    return {
        "kagechi_ratio": kagechi_ratio,
        "plot_shadow_ratio": kagechi_ratio,
        "plot_aspect_ratio": 0.5 if is_fuseigei else 1.0,
        "plot_effective_ratio": max(0.0, 1.0 - kagechi_ratio),
        "plot_shape_penalty": shape_penalty,
        "plot_mic_diameter": 6.0 if is_fuseigei else 10.0,
        "plot_bottleneck_width": 4.0 if is_fuseigei else 10.0,
        "plot_solidity": 0.85 if is_fuseigei else 1.0,
        "plot_compactness": 0.70 if is_fuseigei else 1.0,
        "plot_nta_discount": shape_penalty,
        "plot_acute_angles": 0.0,
        "plot_flagpole_ratio": 0.0,
        "plot_shape_grade_num": 3.0 if is_fuseigei else 5.0,
        "plot_shape_score_100": round(shape_penalty * 100.0, 1),
        "shape_type_code": shape_code_map.get(s_type, 1.0),
        "is_regular_shape": 1.0 if s_type == 'regular' else 0.0
    }, shape_penalty


def _resolve_kagechi_ratio(property_obj: Any, is_hatasao: bool, is_fuseigei: bool) -> float:
    kagechi_ratio = safe_float(_get_attr(property_obj, 'kagechi_ratio', None), None)
    if kagechi_ratio is not None:
        return kagechi_ratio
    if is_hatasao:
        return 0.25
    if is_fuseigei:
        return 0.15
    return 0.0


def _apply_plot_shape_discount(
    property_type: str,
    cost_approach_value: float,
    mkt_comparison_value: float,
    residual_land_value: float,
    plot_shape_penalty: float
) -> tuple[float, float, float]:
    if property_type in ['tochi', 'kodate']:
        cost_approach_value = round(cost_approach_value * plot_shape_penalty, 2)
        mkt_comparison_value = round(mkt_comparison_value * plot_shape_penalty, 2)
        if residual_land_value > 0:
            residual_land_value = round(residual_land_value * plot_shape_penalty, 2)
    return cost_approach_value, mkt_comparison_value, residual_land_value


def calculate_plot_shape_features(
    property_obj: Any,
    property_type: str,
    cost_approach_value: float,
    mkt_comparison_value: float,
    residual_land_value: float
) -> tuple[dict[str, float], float, float, float]:
    biko_text = _get_attr(property_obj, 'biko', '') or ''
    tochi_text = _get_attr(property_obj, 'tochikenri', '') or ''
    is_hatasao = any(x in str(biko_text) or x in str(tochi_text) for x in ["旗竿", "路地状", "敷地延長", "敷延"])
    is_fuseigei = any(x in str(biko_text) or x in str(tochi_text) for x in ["不整形", "変形地", "台形地", "袋地"])

    kagechi_ratio = _resolve_kagechi_ratio(property_obj, is_hatasao, is_fuseigei)

    plot_vertices = _get_attr(property_obj, 'plot_vertices', None)
    shape_metrics = analyze_plot_shape(plot_vertices) if plot_vertices and len(plot_vertices) >= 3 else None

    if shape_metrics:
        shape_feats, plot_shape_penalty = _build_shape_metrics_features(shape_metrics)
    else:
        shape_feats, plot_shape_penalty = _build_fallback_shape_features(is_hatasao, is_fuseigei, kagechi_ratio)

    cost_approach_value, mkt_comparison_value, residual_land_value = _apply_plot_shape_discount(
        property_type, cost_approach_value, mkt_comparison_value, residual_land_value, plot_shape_penalty
    )

    return shape_feats, cost_approach_value, mkt_comparison_value, residual_land_value


# Backward compatibility alias
_calculate_plot_shape_features = calculate_plot_shape_features

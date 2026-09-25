# -*- coding: utf-8 -*-
"""
土地形状・敷地区画の数理幾何評価モジュール (plot_shape_analyzer.py)

不動産鑑定評価（相続税財産評価基本通達、不整形地補正率）に基づき、
敷地ポリゴンから最小外接矩形 (OBB)、最大内接矩形 (MIR)、かげ地割合、
うなぎの寝床判定（縦横比）、頂点数・複雑度、および統合ペナルティスコアを算出。
NumPy, SciPy, PIL を用いた完全ローカル・低コスト幾何解析。
"""
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt
from scipy.spatial import ConvexHull


@dataclass
class PlotShapeMetrics:
    plot_area: float
    obb_area: float
    shadow_area_ratio: float
    mir_area: float
    mir_effective_ratio: float
    mir_aspect_ratio: float
    is_unagi: bool
    vertex_count: int
    solidity: float
    compactness: float
    vertex_penalty: float
    shape_penalty_score: float
    shape_type: str
    # 探査手法全部盛り（MIC・ボトルネック・国税庁テーブル・吉野金次式・旗竿分解・内角・格付け）
    mic_diameter: float = 0.0
    mic_area: float = 0.0
    mic_coverage_ratio: float = 0.0
    bottleneck_width: float = 0.0
    nta_irregular_discount: float = 1.0
    nta_frontage_discount: float = 1.0
    nta_depth_discount: float = 1.0
    nta_composite_discount: float = 1.0
    yoshino_area: float = 0.0
    yoshino_shadow_ratio: float = 0.0
    yoshino_coefficient: float = 1.0
    is_flagpole: bool = False
    flagpole_passage_area: float = 0.0
    flagpole_passage_ratio: float = 0.0
    flagpole_passage_width: float = 0.0
    flagpole_body_area: float = 0.0
    acute_angle_count: int = 0
    reflex_angle_count: int = 0
    interior_angles: Optional[List[float]] = None
    shape_grade: str = "A"
    shape_grade_num: int = 5
    shape_score_100: float = 100.0



def calculate_polygon_area(vertices: List[Tuple[float, float]]) -> float:
    """Shoelace formulaによる多角形面積の計算"""
    n = len(vertices)
    if n < 3:
        return 0.0
    x = [v[0] for v in vertices]
    y = [v[1] for v in vertices]
    return 0.5 * abs(sum(x[i] * y[(i + 1) % n] - x[(i + 1) % n] * y[i] for i in range(n)))


def calculate_perimeter(vertices: List[Tuple[float, float]]) -> float:
    """多角形の周囲長を計算"""
    n = len(vertices)
    if n < 2:
        return 0.0
    perimeter = 0.0
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        perimeter += math.hypot(x2 - x1, y2 - y1)
    return perimeter


def calculate_obb(vertices: List[Tuple[float, float]]) -> Tuple[float, float, float]:
    """
    最小外接矩形 (Oriented Bounding Box) の面積、幅、高さを計算
    返り値: (obb_area, width, height)
    """
    if len(vertices) < 3:
        return 0.0, 0.0, 0.0

    pts = np.array(vertices, dtype=np.float64)

    # 各辺の角度および0〜90度のサンプリングで最小外接長方形を探索
    angles = []
    n = len(vertices)
    for i in range(n):
        dx = vertices[(i + 1) % n][0] - vertices[i][0]
        dy = vertices[(i + 1) % n][1] - vertices[i][1]
        angles.append(math.atan2(dy, dx))

    # 15度刻みの補助角度も追加
    for a in np.linspace(0, math.pi / 2, 10):
        angles.append(float(a))

    min_area = float('inf')
    best_w, best_h = 0.0, 0.0

    for angle in angles:
        cos_a = math.cos(-angle)
        sin_a = math.sin(-angle)
        rot_mat = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
        rot_pts = np.dot(pts, rot_mat.T)

        min_x, min_y = np.min(rot_pts, axis=0)
        max_x, max_y = np.max(rot_pts, axis=0)
        w = max_x - min_x
        h = max_y - min_y
        area = w * h

        if area < min_area:
            min_area = area
            best_w, best_h = w, h

    return min_area, best_w, best_h


def calculate_solidity(vertices: List[Tuple[float, float]], plot_area: float) -> float:
    """
    凸包充足率 (Solidity) = 敷地実面積 / 凸包 (Convex Hull) 面積
    """
    if len(vertices) < 3 or plot_area <= 0.0:
        return 1.0

    try:
        pts = np.array(vertices, dtype=np.float64)
        hull = ConvexHull(pts)
        hull_area = hull.volume  # 2Dではvolumeが面積
        if hull_area <= 0.0:
            return 1.0
        return float(min(1.0, max(0.0, plot_area / hull_area)))
    except Exception:
        return 1.0


def _largest_rectangle_in_histogram(heights: np.ndarray) -> Tuple[int, int, int]:
    """
    ヒストグラム内の最大長方形探索 (O(W) スタック解法)
    返り値: (max_area, width, height)
    """
    stack = []
    max_area = 0
    best_w, best_h = 0, 0
    w_len = len(heights)

    for i, h in enumerate(heights):
        start = i
        while stack and stack[-1][1] > h:
            idx, height = stack.pop()
            width = i - idx
            area = width * height
            if area > max_area:
                max_area = area
                best_w, best_h = width, height
            start = idx
        stack.append((start, h))

    for idx, height in stack:
        width = w_len - idx
        area = width * height
        if area > max_area:
            max_area = area
            best_w, best_h = width, height

    return max_area, best_w, best_h


def calculate_max_inscribed_rectangle(
    vertices: List[Tuple[float, float]],
    plot_area: float,
    grid_res: int = 150
) -> Tuple[float, float, float]:
    """
    多角形内の最大内接矩形 (Maximum Inscribed Rectangle: MIR) の面積、短辺、長辺を算出。
    ラスタライズ＋回転探索＋ヒストグラム最大長方形法 (O(H*W))。
    返り値: (mir_area, short_side, long_side)
    """
    if len(vertices) < 3 or plot_area <= 0.0:
        return 0.0, 0.0, 0.0

    pts = np.array(vertices, dtype=np.float64)

    # 探索角度（各辺の方向＋補助回転）
    angles = [0.0]
    n = len(vertices)
    for i in range(n):
        dx = vertices[(i + 1) % n][0] - vertices[i][0]
        dy = vertices[(i + 1) % n][1] - vertices[i][1]
        angles.append(math.atan2(dy, dx))

    # 重複角度を丸め
    unique_angles = sorted({round(a % (math.pi / 2), 3) for a in angles})

    best_real_area = 0.0
    best_short = 0.0
    best_long = 0.0

    for angle in unique_angles:
        cos_a = math.cos(-angle)
        sin_a = math.sin(-angle)
        rot_mat = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
        rot_pts = np.dot(pts, rot_mat.T)

        min_xy = np.min(rot_pts, axis=0)
        max_xy = np.max(rot_pts, axis=0)
        span_x = max(max_xy[0] - min_xy[0], 1e-4)
        span_y = max(max_xy[1] - min_xy[1], 1e-4)

        # グリッドスケーリング
        scale = grid_res / max(span_x, span_y)
        w_px = max(int(round(span_x * scale)), 5)
        h_px = max(int(round(span_y * scale)), 5)

        norm_pts = (rot_pts - min_xy) * scale
        poly_px = [(float(p[0]), float(p[1])) for p in norm_pts]

        # バイナリマスク描画
        img = Image.new("1", (w_px + 2, h_px + 2), 0)
        draw = ImageDraw.Draw(img)
        draw.polygon([(p[0] + 1, p[1] + 1) for p in poly_px], fill=1)
        grid = np.array(img, dtype=np.uint8)

        # 2次元配列上の最大長方形探索 (DP + Histogram Stack)
        heights = np.zeros(grid.shape[1], dtype=np.int32)
        max_px_area = 0
        cur_best_w_px, cur_best_h_px = 0, 0

        for r in range(grid.shape[0]):
            heights = np.where(grid[r] == 1, heights + 1, 0)
            area_px, w_cand, h_cand = _largest_rectangle_in_histogram(heights)
            if area_px > max_px_area:
                max_px_area = area_px
                cur_best_w_px, cur_best_h_px = w_cand, h_cand

        real_w = cur_best_w_px / scale
        real_h = cur_best_h_px / scale
        real_area = real_w * real_h

        if real_area > best_real_area:
            best_real_area = real_area
            best_short = min(real_w, real_h)
            best_long = max(real_w, real_h)

    # 敷地面積を超えないようクリップ
    best_real_area = min(best_real_area, plot_area)
    return best_real_area, best_short, best_long


def calculate_nta_irregular_discount(shadow_ratio: float) -> float:
    """国税庁 相続税財産評価基本通達 附表2（不整形地補正率表・普通住宅地）"""
    sr = max(0.0, shadow_ratio)
    if sr < 0.10:
        return 1.00
    elif sr < 0.20:
        return 0.96
    elif sr < 0.30:
        return 0.92
    elif sr < 0.40:
        return 0.86
    elif sr < 0.50:
        return 0.79
    elif sr < 0.60:
        return 0.70
    else:
        return 0.60


def calculate_nta_frontage_discount(frontage: float) -> float:
    """国税庁 相続税財産評価基本通達 附表3（間口狭小補正率表・普通住宅地）"""
    f = float(frontage)
    if f >= 8.0:
        return 1.00
    elif f >= 6.0:
        return 0.97
    elif f >= 4.0:
        return 0.94
    elif f >= 3.0:
        return 0.90
    else:
        return 0.85


def calculate_nta_depth_discount(depth_ratio: float) -> float:
    """国税庁 相続税財産評価基本通達 附表4（奥行長大補正率表・普通住宅地）"""
    dr = max(1.0, float(depth_ratio))
    if dr <= 2.0:
        return 1.00
    elif dr <= 3.0:
        return 0.98
    elif dr <= 4.0:
        return 0.94
    elif dr <= 5.0:
        return 0.90
    else:
        return 0.85


def calculate_yoshino_assumed_plot(
    vertices: List[Tuple[float, float]],
    plot_area: float
) -> Tuple[float, float, float]:
    """
    吉野金次式（想定整形地）の面積、かげ地割合、補正率を算出。
    返り値: (yoshino_area, yoshino_shadow_ratio, yoshino_coefficient)
    """
    if len(vertices) < 3 or plot_area <= 0.0:
        return 0.0, 0.0, 1.0

    obb_area, _, _ = calculate_obb(vertices)
    yoshino_area = max(plot_area, obb_area)
    if yoshino_area > 0.0:
        shadow_ratio = max(0.0, min(1.0, (yoshino_area - plot_area) / yoshino_area))
    else:
        shadow_ratio = 0.0

    coeff = max(0.60, min(1.0, 1.0 - (shadow_ratio * 0.35)))
    return round(yoshino_area, 2), round(shadow_ratio, 4), round(coeff, 4)


def calculate_interior_angles(
    vertices: List[Tuple[float, float]]
) -> Tuple[List[float], int, int]:
    """
    多角形の各頂点の内角（度数法）、鋭角頂点数（<60度）、凹角頂点数（>180度）を算出。
    返り値: (angles, acute_count, reflex_count)
    """
    n = len(vertices)
    if n < 3:
        return [], 0, 0

    x = [v[0] for v in vertices]
    y = [v[1] for v in vertices]
    signed_area = 0.5 * sum(x[i] * y[(i + 1) % n] - x[(i + 1) % n] * y[i] for i in range(n))
    pts = list(vertices)
    if signed_area < 0:
        pts.reverse()

    angles = []
    acute_count = 0
    reflex_count = 0

    for i in range(n):
        p_prev = pts[(i - 1) % n]
        p_curr = pts[i]
        p_next = pts[(i + 1) % n]

        v1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
        v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])

        cross = v1[0] * v2[1] - v1[1] * v2[0]
        dot = v1[0] * v2[0] + v1[1] * v2[1]

        turn_rad = math.atan2(cross, dot)
        turn_deg = math.degrees(turn_rad)
        interior = 180.0 - turn_deg
        if interior < 0:
            interior += 360.0
        elif interior >= 360.0:
            interior -= 360.0

        rounded = round(interior, 1)
        angles.append(rounded)
        if rounded < 60.0:
            acute_count += 1
        elif rounded > 180.0:
            reflex_count += 1

    return angles, acute_count, reflex_count


def _find_best_obb_alignment(pts: np.ndarray, vertices: List[Tuple[float, float]]) -> np.ndarray:
    n = len(vertices)
    angles = [0.0]
    for i in range(n):
        dx = vertices[(i + 1) % n][0] - vertices[i][0]
        dy = vertices[(i + 1) % n][1] - vertices[i][1]
        angles.append(math.atan2(dy, dx))

    min_area = float('inf')
    best_pts = pts
    for a in angles:
        cos_a, sin_a = math.cos(-a), math.sin(-a)
        rot_mat = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
        r_pts = np.dot(pts, rot_mat.T)
        min_xy = np.min(r_pts, axis=0)
        max_xy = np.max(r_pts, axis=0)
        span = max_xy - min_xy
        area = span[0] * span[1]
        if area < min_area:
            min_area = area
            best_pts = r_pts - min_xy
    return best_pts


def _eval_passage_segment(valid: np.ndarray, total_len: float, plot_area: float) -> Tuple[bool, float, float]:
    max_w = float(np.max(valid))
    narrow_thresh = min(4.0, max_w * 0.55)
    is_narrow = valid <= narrow_thresh
    lead_len = 0
    for val in is_narrow:
        if val:
            lead_len += 1
        else:
            break
    trail_len = 0
    for val in reversed(is_narrow):
        if val:
            trail_len += 1
        else:
            break

    chosen_len = max(lead_len, trail_len)
    seg_ratio = chosen_len / len(valid)
    passage_len = seg_ratio * total_len
    if 0.10 <= seg_ratio <= 0.75 and passage_len >= 2.0:
        p_w = float(np.median(valid[:lead_len])) if lead_len >= trail_len else float(np.median(valid[-trail_len:]))
        if p_w <= 4.0:
            return True, round(p_w, 2), round(min(plot_area * 0.8, p_w * passage_len), 2)
    return False, 0.0, 0.0


def _calc_bottleneck_width(row_widths: np.ndarray, col_widths: np.ndarray, is_flagpole: bool, p_width: float) -> float:
    if is_flagpole and p_width > 0:
        return p_width
    valid_rows = row_widths[row_widths > 0.1]
    valid_cols = col_widths[col_widths > 0.1]
    if len(valid_rows) > 0 and len(valid_cols) > 0:
        all_valid = np.concatenate([valid_rows, valid_cols])
    else:
        all_valid = valid_rows if len(valid_rows) > 0 else valid_cols
    if len(all_valid) > 10:
        trimmed = np.sort(all_valid)
        return float(trimmed[int(len(trimmed) * 0.05)])
    if len(all_valid) > 0:
        return float(np.min(all_valid))
    return 0.0


def calculate_mic_and_bottleneck(
    vertices: List[Tuple[float, float]],
    plot_area: float,
    grid_res: int = 150
) -> dict:
    """
    多角形内の最大内接円 (MIC)、ボトルネック最小幅員、および旗竿地路地部分の分解解析。
    scipy.ndimage.distance_transform_edt と 2次元ラスタライズ投影法を利用。
    """
    if len(vertices) < 3 or plot_area <= 0.0:
        return {
            "mic_diameter": 0.0,
            "mic_area": 0.0,
            "mic_coverage_ratio": 0.0,
            "bottleneck_width": 0.0,
            "is_flagpole": False,
            "flagpole_passage_area": 0.0,
            "flagpole_passage_ratio": 0.0,
            "flagpole_passage_width": 0.0,
            "flagpole_body_area": 0.0,
        }

    pts = np.array(vertices, dtype=np.float64)
    best_pts = _find_best_obb_alignment(pts, vertices)

    span_x = max(float(np.max(best_pts[:, 0])), 1e-4)
    span_y = max(float(np.max(best_pts[:, 1])), 1e-4)
    scale = grid_res / max(span_x, span_y)
    pad = 5
    w_px = int(round(span_x * scale)) + 2 * pad
    h_px = int(round(span_y * scale)) + 2 * pad

    img = Image.new('1', (w_px, h_px), 0)
    draw = ImageDraw.Draw(img)
    poly_px = [(p[0] * scale + pad, p[1] * scale + pad) for p in best_pts]
    draw.polygon(poly_px, fill=1)
    grid = np.array(img, dtype=np.uint8)

    # 1. MIC (Maximum Inscribed Circle)
    edt = distance_transform_edt(grid)
    max_radius_px = float(np.max(edt))
    mic_radius = max_radius_px / scale
    mic_diameter = round(mic_radius * 2.0, 2)
    mic_area = round(min(plot_area, math.pi * (mic_radius ** 2)), 2)
    mic_coverage_ratio = round(min(1.0, mic_area / plot_area), 4) if plot_area > 0 else 0.0

    # 2. 断面幅員プロファイル解析 (X軸・Y軸スライス)
    row_widths = np.sum(grid[pad:pad + int(round(span_y * scale)), :], axis=1) / scale
    col_widths = np.sum(grid[:, pad:pad + int(round(span_x * scale))], axis=0) / scale

    is_flagpole = False
    p_width, p_area = 0.0, 0.0

    for widths, total_len in [(row_widths, span_y), (col_widths, span_x)]:
        valid = widths[widths > 0.1]
        if len(valid) < 5:
            continue
        is_flag, pw, pa = _eval_passage_segment(valid, total_len, plot_area)
        if is_flag:
            is_flagpole, p_width, p_area = is_flag, pw, pa
            break

    bottleneck_w = _calc_bottleneck_width(row_widths, col_widths, is_flagpole, p_width)
    p_ratio = round(min(1.0, p_area / plot_area), 4) if plot_area > 0 else 0.0
    body_area = round(max(0.0, plot_area - p_area), 2)

    return {
        "mic_diameter": mic_diameter,
        "mic_area": mic_area,
        "mic_coverage_ratio": mic_coverage_ratio,
        "bottleneck_width": round(bottleneck_w, 2),
        "is_flagpole": is_flagpole,
        "flagpole_passage_area": p_area,
        "flagpole_passage_ratio": p_ratio,
        "flagpole_passage_width": p_width,
        "flagpole_body_area": body_area,
    }


def _compute_penalties_and_score(
    shadow_area_ratio: float,
    solidity: float,
    mir_aspect_ratio: float,
    is_unagi: bool,
    vertex_count: int,
    acute_count: int,
    is_flagpole: bool,
    flagpole_passage_ratio: float,
    bottleneck_width: float,
    nta_composite: float,
) -> Tuple[float, float]:
    shadow_penalty = shadow_area_ratio * 0.35
    solidity_penalty = (1.0 - solidity) * 0.25
    aspect_penalty = 0.0
    if mir_aspect_ratio < 0.50:
        unagi_bonus = 0.08 if is_unagi else 0.0
        aspect_penalty = (0.50 - mir_aspect_ratio) * 0.40 + unagi_bonus
    vertex_penalty = min(0.15, (vertex_count - 6) * 0.02) if vertex_count > 6 else 0.0
    acute_penalty = min(0.15, acute_count * 0.05)
    flagpole_penalty = 0.0
    if is_flagpole:
        bottleneck_penalty = 0.05 if bottleneck_width < 2.5 else 0.0
        flagpole_penalty = min(0.20, flagpole_passage_ratio * 0.35 + bottleneck_penalty)

    geometric_penalty = shadow_penalty + solidity_penalty + aspect_penalty + vertex_penalty + acute_penalty + flagpole_penalty
    geometric_score = max(0.60, min(1.0, 1.0 - geometric_penalty))
    raw_score = min(geometric_score, nta_composite)
    if is_unagi:
        raw_score = min(0.74, raw_score)
    shape_penalty_score = round(max(0.60, min(1.0, raw_score)), 4)
    return vertex_penalty, shape_penalty_score


def _determine_shape_type_and_grade(
    is_unagi: bool,
    is_flagpole: bool,
    shadow_area_ratio: float,
    mir_effective_ratio: float,
    solidity: float,
    vertex_count: int,
    acute_count: int,
    shape_penalty_score: float,
) -> Tuple[str, str, int, float]:
    if is_unagi:
        shape_type = "slender"
    elif is_flagpole or (shadow_area_ratio > 0.30 and mir_effective_ratio < 0.95):
        shape_type = "flagpole"
    elif shadow_area_ratio > 0.15 or solidity < 0.88 or vertex_count > 6 or acute_count > 0:
        shape_type = "irregular"
    else:
        shape_type = "regular"

    if shape_penalty_score >= 0.95:
        shape_grade = "A"
    elif shape_penalty_score >= 0.85:
        shape_grade = "B"
    elif shape_penalty_score >= 0.75:
        shape_grade = "C"
    elif shape_penalty_score >= 0.65:
        shape_grade = "D"
    else:
        shape_grade = "E"

    grade_num_map = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
    shape_grade_num = grade_num_map.get(shape_grade, 5)
    shape_score_100 = round(shape_penalty_score * 100.0, 1)
    return shape_type, shape_grade, shape_grade_num, shape_score_100


def _estimate_frontage_and_depth(
    is_flagpole: bool,
    flagpole_passage_width: float,
    obb_w: float,
    obb_h: float
) -> Tuple[float, float]:
    """接道間口および奥行の推定"""
    if is_flagpole and flagpole_passage_width > 0:
        est_frontage = flagpole_passage_width
    elif obb_w > 0:
        est_frontage = max(1.0, min(obb_w, obb_h))
    else:
        est_frontage = 5.0

    max_dim = max(obb_w, obb_h)
    est_depth = max(1.0, max_dim) if max_dim > 0 else 10.0
    return est_frontage, est_depth


def _calculate_mir_and_unagi(
    vertices: List[Tuple[float, float]],
    plot_area: float
) -> Tuple[float, float, float, bool]:
    """最大内接矩形 (MIR) & 縦横比（うなぎの寝床判定）"""
    mir_area, mir_short, mir_long = calculate_max_inscribed_rectangle(vertices, plot_area)
    mir_effective_ratio = min(1.0, mir_area / plot_area) if plot_area > 0.0 else 1.0
    mir_aspect_ratio = min(1.0, max(0.01, mir_short / mir_long)) if mir_long > 0.0 else 1.0
    is_unagi = bool(mir_aspect_ratio < 0.25)
    return mir_area, mir_effective_ratio, mir_aspect_ratio, is_unagi


def analyze_plot_shape(vertices: List[Tuple[float, float]]) -> PlotShapeMetrics:
    """
    敷地ポリゴンの幾何指標および不動産鑑定ペナルティスコアを一括算出。
    不動産鑑定基準（吉野金次式想定整形地）、国税庁通達補正率（附表2・3・4）、
    および計算幾何学（OBB, MIR, MIC, Distance Transform）を統合。
    """
    if not vertices or len(vertices) < 3:
        return PlotShapeMetrics(
            plot_area=0.0,
            obb_area=0.0,
            shadow_area_ratio=0.0,
            mir_area=0.0,
            mir_effective_ratio=1.0,
            mir_aspect_ratio=1.0,
            is_unagi=False,
            vertex_count=len(vertices) if vertices else 0,
            solidity=1.0,
            compactness=1.0,
            vertex_penalty=0.0,
            shape_penalty_score=1.0,
            shape_type="unknown",
            shape_grade="A",
            shape_grade_num=5,
            shape_score_100=100.0
        )

    # 1. 基本幾何量
    plot_area = calculate_polygon_area(vertices)
    perimeter = calculate_perimeter(vertices)
    vertex_count = len(vertices)

    # 2. 最小外接矩形 (OBB) & かげ地割合
    obb_area, obb_w, obb_h = calculate_obb(vertices)
    shadow_area_ratio = max(0.0, min(1.0, (obb_area - plot_area) / obb_area)) if obb_area > 0.0 else 0.0

    # 3. 最大内接矩形 (MIR) & 縦横比（うなぎの寝床判定）
    mir_area, mir_effective_ratio, mir_aspect_ratio, is_unagi = _calculate_mir_and_unagi(vertices, plot_area)

    # 4. 凸包充足率 (Solidity) & 等周比 (Compactness)
    solidity = calculate_solidity(vertices, plot_area)
    compactness = min(1.0, max(0.0, (4.0 * math.pi * plot_area) / (perimeter ** 2))) if perimeter > 0.0 else 1.0

    # 5. 最大内接円 (MIC)、ボトルネック幅員、および旗竿地分解
    mic_profile = calculate_mic_and_bottleneck(vertices, plot_area)
    mic_diameter = mic_profile["mic_diameter"]
    mic_area = mic_profile["mic_area"]
    mic_coverage_ratio = mic_profile["mic_coverage_ratio"]
    bottleneck_width = mic_profile["bottleneck_width"]
    is_flagpole = mic_profile["is_flagpole"]
    flagpole_passage_area = mic_profile["flagpole_passage_area"]
    flagpole_passage_ratio = mic_profile["flagpole_passage_ratio"]
    flagpole_passage_width = mic_profile["flagpole_passage_width"]
    flagpole_body_area = mic_profile["flagpole_body_area"]

    # 6. 国税庁 相続税財産評価基本通達（附表2・3・4）テーブル補正率
    nta_irreg = calculate_nta_irregular_discount(shadow_area_ratio)

    # 接道間口および奥行の推定
    est_frontage, est_depth = _estimate_frontage_and_depth(
        is_flagpole, flagpole_passage_width, obb_w, obb_h
    )
    depth_ratio = max(1.0, est_depth / est_frontage)

    nta_front = calculate_nta_frontage_discount(est_frontage)
    nta_depth = calculate_nta_depth_discount(depth_ratio)
    nta_composite = round(max(0.60, min(1.0, nta_irreg * nta_front * nta_depth)), 4)

    # 7. 吉野金次式（想定整形地評価）
    yoshino_area, yoshino_shadow, yoshino_coeff = calculate_yoshino_assumed_plot(vertices, plot_area)

    # 8. 内角解析（鋭角・凹角）
    interior_angles, acute_count, reflex_count = calculate_interior_angles(vertices)

    vertex_penalty, shape_penalty_score = _compute_penalties_and_score(
        shadow_area_ratio, solidity, mir_aspect_ratio, is_unagi,
        vertex_count, acute_count, is_flagpole, flagpole_passage_ratio,
        bottleneck_width, nta_composite
    )
    shape_type, shape_grade, shape_grade_num, shape_score_100 = _determine_shape_type_and_grade(
        is_unagi, is_flagpole, shadow_area_ratio, mir_effective_ratio,
        solidity, vertex_count, acute_count, shape_penalty_score
    )

    return PlotShapeMetrics(
        plot_area=round(plot_area, 2),
        obb_area=round(obb_area, 2),
        shadow_area_ratio=round(shadow_area_ratio, 4),
        mir_area=round(mir_area, 2),
        mir_effective_ratio=round(mir_effective_ratio, 4),
        mir_aspect_ratio=round(mir_aspect_ratio, 4),
        is_unagi=is_unagi,
        vertex_count=vertex_count,
        solidity=round(solidity, 4),
        compactness=round(compactness, 4),
        vertex_penalty=round(vertex_penalty, 4),
        shape_penalty_score=shape_penalty_score,
        shape_type=shape_type,
        mic_diameter=mic_diameter,
        mic_area=mic_area,
        mic_coverage_ratio=mic_coverage_ratio,
        bottleneck_width=bottleneck_width,
        nta_irregular_discount=round(nta_irreg, 4),
        nta_frontage_discount=round(nta_front, 4),
        nta_depth_discount=round(nta_depth, 4),
        nta_composite_discount=round(nta_composite, 4),
        yoshino_area=yoshino_area,
        yoshino_shadow_ratio=yoshino_shadow,
        yoshino_coefficient=yoshino_coeff,
        is_flagpole=is_flagpole,
        flagpole_passage_area=flagpole_passage_area,
        flagpole_passage_ratio=flagpole_passage_ratio,
        flagpole_passage_width=flagpole_passage_width,
        flagpole_body_area=flagpole_body_area,
        acute_angle_count=acute_count,
        reflex_angle_count=reflex_count,
        interior_angles=interior_angles,
        shape_grade=shape_grade,
        shape_grade_num=shape_grade_num,
        shape_score_100=shape_score_100
    )


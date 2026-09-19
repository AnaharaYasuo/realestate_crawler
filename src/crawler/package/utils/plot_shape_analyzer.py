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
        from scipy.spatial import ConvexHull
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
    unique_angles = sorted(list(set(round(a % (math.pi / 2), 3) for a in angles)))

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


def analyze_plot_shape(vertices: List[Tuple[float, float]]) -> PlotShapeMetrics:
    """
    敷地ポリゴンの幾何指標および不動産鑑定ペナルティスコアを一括算出。
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
            shape_type="unknown"
        )

    # 1. 基本幾何量
    plot_area = calculate_polygon_area(vertices)
    perimeter = calculate_perimeter(vertices)
    vertex_count = len(vertices)

    # 2. 最小外接矩形 (OBB) & かげ地割合
    obb_area, obb_w, obb_h = calculate_obb(vertices)
    if obb_area > 0.0:
        shadow_area_ratio = max(0.0, min(1.0, (obb_area - plot_area) / obb_area))
    else:
        shadow_area_ratio = 0.0

    # 3. 最大内接矩形 (MIR) & 縦横比（うなぎの寝床判定）
    mir_area, mir_short, mir_long = calculate_max_inscribed_rectangle(vertices, plot_area)
    mir_effective_ratio = min(1.0, mir_area / plot_area) if plot_area > 0.0 else 1.0

    if mir_long > 0.0:
        mir_aspect_ratio = min(1.0, max(0.01, mir_short / mir_long))
    else:
        mir_aspect_ratio = 1.0

    # 1:4 (0.25) 未満はうなぎの寝床
    is_unagi = bool(mir_aspect_ratio < 0.25)

    # 4. 凸包充足率 (Solidity) & 等周比 (Compactness)
    solidity = calculate_solidity(vertices, plot_area)
    if perimeter > 0.0:
        compactness = min(1.0, max(0.0, (4.0 * math.pi * plot_area) / (perimeter ** 2)))
    else:
        compactness = 1.0

    # 5. ペナルティ算出
    # かげ地ペナルティ (最大0.35減価)
    shadow_penalty = shadow_area_ratio * 0.35

    # 凹み・くびれペナルティ (最大0.25減価)
    solidity_penalty = (1.0 - solidity) * 0.25

    # うなぎの寝床・細長比ペナルティ (最大0.20減価)
    if mir_aspect_ratio < 0.50:
        aspect_penalty = (0.50 - mir_aspect_ratio) * 0.40
    else:
        aspect_penalty = 0.0

    # 頂点数ペナルティ (6点超で1点につき0.02減価、最大0.15)
    if vertex_count > 6:
        vertex_penalty = min(0.15, (vertex_count - 6) * 0.02)
    else:
        vertex_penalty = 0.0

    total_penalty = shadow_penalty + solidity_penalty + aspect_penalty + vertex_penalty
    shape_penalty_score = round(max(0.60, min(1.0, 1.0 - total_penalty)), 4)

    # 6. 形状種別の判定
    if is_unagi:
        shape_type = "slender"
    elif shadow_area_ratio > 0.30 and mir_effective_ratio < 0.95:
        shape_type = "flagpole"
    elif shadow_area_ratio > 0.15 or solidity < 0.88 or vertex_count > 6:
        shape_type = "irregular"
    else:
        shape_type = "regular"

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
        shape_type=shape_type
    )

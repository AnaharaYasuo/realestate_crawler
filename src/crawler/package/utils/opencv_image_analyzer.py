"""
OpenCV (`cv2`) × `plot_shape_analyzer` 決定論的画像解析モジュール (Issue #1380)

得意領域の役割分担:
1. 区画図・配置図 (`plot_plan`) / 間取り図 (`layout`):
   OpenCV による二値化・モルフォロジー閉処理・輪郭抽出 (`findContours`)・Douglas-Peucker 多角形近似 (`approxPolyDP`)
   で敷地ポリゴン頂点列を抽出し、`analyze_plot_shape` でかげ地割合 (`shadow_area_ratio`)・
   国税庁不整形地補正率 (`nta_irregular_discount`)・画地幾何スコア (`shape_score_100`) をミリ秒・無料算出。
2. 内装 (`interior`) / 外観 (`exterior`):
   HSV 明度・彩度ムラ（経年黄ばみ・汚れ指標）・コントラスト・Laplacian 鮮鋭度から
   客観フォトメトリクス採点 (`interior_score`, `maintenance_score`) を算出。
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import numpy as np
from package.utils.plot_shape_analyzer import (
    analyze_plot_shape,
    calculate_nta_irregular_discount,
)
from PIL import Image

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _pil_to_rgb_array(img: Image.Image, max_side: int = 640) -> np.ndarray:
    rgb = img.convert("RGB")
    w, h = rgb.size
    if max(w, h) > max_side:
        scale = max_side / float(max(w, h))
        rgb = rgb.resize((max(32, int(w * scale)), max(32, int(h * scale))))
    return np.asarray(rgb, dtype=np.uint8)


def _is_valid_lot_contour(cnt: Any, w: int, h: int, img_area: float) -> tuple[bool, float]:
    area = float(cv2.contourArea(cnt))
    if area < img_area * 0.04 or area > img_area * 0.92:
        return False, 0.0
    x, y, cw, ch = cv2.boundingRect(cnt)
    touches_all = x <= 2 and y <= 2 and (x + cw) >= (w - 2) and (y + ch) >= (h - 2)
    if touches_all and area > img_area * 0.85:
        return False, 0.0
    return True, area


def _select_best_lot_contour(contours: Any, w: int, h: int, img_area: float) -> tuple[Any, float]:
    best_cnt = None
    best_area = 0.0
    for cnt in contours:
        ok, area = _is_valid_lot_contour(cnt, w, h, img_area)
        if ok and area > best_area:
            best_area = area
            best_cnt = cnt
    return best_cnt, best_area


def _extract_primary_lot_vertices(rgb: np.ndarray) -> list[tuple[float, float]] | None:
    """区画図RGB配列から主要画地ポリゴンの頂点座標列（メートル換算正規化）を抽出する。"""
    if cv2 is None:
        return None
    h, w = rgb.shape[:2]
    img_area = float(h * w)
    if img_area < 2500.0:
        return None

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # 黒線輪郭・淡色塗り区画の双方を捕捉するためエッジ＋二値化を統合
    _, inv_bin = cv2.threshold(blurred, 245, 255, cv2.THRESH_BINARY_INV)
    edges = cv2.Canny(blurred, 40, 140)
    combined = cv2.bitwise_or(inv_bin, edges)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_cnt, best_area = _select_best_lot_contour(contours, w, h, img_area)
    if best_cnt is None:
        return None

    peri = float(cv2.arcLength(best_cnt, True))
    approx = cv2.approxPolyDP(best_cnt, 0.012 * peri, True)
    if len(approx) < 3:
        return None

    # 標準宅地スケール (約120㎡相当) へ等方スケーリングして analyze_plot_shape のメートル閾値と整合させる
    scale_m = (120.0 / max(1.0, best_area)) ** 0.5
    pts = approx.reshape(-1, 2)
    return [(float(px) * scale_m, float(py) * scale_m) for px, py in pts]


def _classify_shape_label(is_flagpole: bool, shadow_ratio: float) -> str:
    if is_flagpole:
        return "flagpole"
    if shadow_ratio >= 0.12:
        return "irregular"
    return "regular"


def _analyze_plot_plan_image(img: Image.Image) -> dict[str, Any]:
    rgb = _pil_to_rgb_array(img)
    vertices = _extract_primary_lot_vertices(rgb)
    if not vertices:
        return {}
    metrics = analyze_plot_shape(vertices)
    shadow = round(float(metrics.shadow_area_ratio), 4)
    nta_disc = round(float(calculate_nta_irregular_discount(shadow)), 4)
    shape_type = _classify_shape_label(bool(metrics.is_flagpole), shadow)
    return {
        "plot_shape_type": shape_type,
        "shadow_area_ratio": shadow,
        "shape_score_100": round(float(metrics.shape_score_100), 1),
        "nta_irregular_discount": nta_disc,
        "passage_width": round(float(metrics.flagpole_passage_width), 2) if metrics.is_flagpole else None,
        "plot_shape_description": (
            f"OpenCV輪郭解析: 頂点数{metrics.vertex_count}, かげ地割合{shadow:.1%}, 形状区分={shape_type}"
        ),
    }


def _score_photometric_quality(img: Image.Image) -> float:
    """内装・外観画像の明るさ・清潔感（低黄ばみ）・コントラスト・鮮鋭度から 1.0〜5.0 点に採点する。"""
    rgb = _pil_to_rgb_array(img, max_side=512)
    if cv2 is not None:
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        val_mean = float(np.mean(hsv[:, :, 2])) / 255.0
        val_std = float(np.std(hsv[:, :, 2])) / 255.0
        # 暗い黄褐色領域（経年ヤニ汚れ・水染み候補）の面積比
        hue = hsv[:, :, 0]
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]
        stain_mask = (hue >= 10) & (hue <= 28) & (sat >= 95) & (val <= 155)
        stain_ratio = float(np.mean(stain_mask))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    else:  # pragma: no cover
        lum = np.mean(rgb.astype(np.float32), axis=2) / 255.0
        val_mean = float(np.mean(lum))
        val_std = float(np.std(lum))
        stain_ratio = 0.0
        lap_var = float(np.var(np.diff(lum, axis=1))) * 2000.0

    brightness_term = np.clip((val_mean - 0.35) / 0.45, -0.6, 0.9)
    contrast_term = np.clip((val_std - 0.12) / 0.18, -0.3, 0.4)
    sharpness_term = np.clip(np.log1p(max(0.0, lap_var)) / 8.0 - 0.35, -0.3, 0.5)
    stain_penalty = min(1.2, stain_ratio * 3.5)

    score = 3.2 + brightness_term + contrast_term + sharpness_term - stain_penalty
    return round(float(np.clip(score, 1.0, 5.0)), 2)


def _score_layout_diagram(img: Image.Image) -> float:
    """間取り図の構造線密度と縦横バランスから 1.0〜5.0 の初期スコアを算出する。"""
    rgb = _pil_to_rgb_array(img, max_side=512)
    h, w = rgb.shape[:2]
    aspect = max(h, w) / max(1.0, float(min(h, w)))
    aspect_bonus = 0.4 if aspect <= 1.6 else (-0.3 if aspect >= 2.6 else 0.1)
    gray = np.mean(rgb.astype(np.float32), axis=2)
    line_ratio = float(np.mean(gray < 200.0))
    density_bonus = 0.3 if 0.04 <= line_ratio <= 0.45 else -0.2
    return round(float(np.clip(3.4 + aspect_bonus + density_bonus, 1.0, 5.0)), 2)


def analyze_pil_images_with_opencv(
    categorized_images: Sequence[tuple[str, Image.Image]],
) -> dict[str, Any]:
    """カテゴリ付き PIL 画像群を OpenCV で高速解析し、幾何・フォトメトリクス指標辞書を返す。"""
    out: dict[str, Any] = {
        "interior_score": 3.5,
        "layout_score": 3.5,
        "maintenance_score": 3.5,
        "plot_shape_type": "unknown",
        "plot_shape_description": "",
        "shadow_area_ratio": None,
        "shape_score_100": None,
        "nta_irregular_discount": None,
        "passage_width": None,
    }
    if not categorized_images:
        return out

    int_scores: list[float] = []
    ext_scores: list[float] = []
    lay_scores: list[float] = []

    for category, pil_img in categorized_images:
        cat = (category or "interior").lower()
        if cat == "plot_plan" and out["shadow_area_ratio"] is None:
            out.update(_analyze_plot_plan_image(pil_img))
        elif cat == "layout":
            lay_scores.append(_score_layout_diagram(pil_img))
        elif cat == "exterior":
            ext_scores.append(_score_photometric_quality(pil_img))
        else:
            int_scores.append(_score_photometric_quality(pil_img))

    if int_scores:
        out["interior_score"] = round(float(np.mean(int_scores)), 2)
    if ext_scores:
        out["maintenance_score"] = round(float(np.mean(ext_scores)), 2)
    if lay_scores:
        out["layout_score"] = round(float(np.mean(lay_scores)), 2)
    return out

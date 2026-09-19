# -*- coding: utf-8 -*-
"""
土地形状幾何解析モジュールの単体テスト (test_plot_shape_analyzer.py)

最小外接矩形 (OBB)、最大内接矩形 (MIR)、かげ地割合、うなぎの寝床判定（縦横比）、
頂点数・複雑度（Solidity）、および統合ペナルティスコアを検証。
"""
import pytest
from package.utils.plot_shape_analyzer import (
    analyze_plot_shape,
    calculate_polygon_area,
    calculate_obb,
    calculate_max_inscribed_rectangle,
    calculate_solidity,
    PlotShapeMetrics
)


def test_perfect_square():
    """完全な正方形 (10m x 10m) の幾何解析テスト"""
    vertices = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    metrics = analyze_plot_shape(vertices)

    assert isinstance(metrics, PlotShapeMetrics)
    assert metrics.plot_area == pytest.approx(100.0, rel=1e-2)
    assert metrics.obb_area == pytest.approx(100.0, rel=1e-2)
    assert metrics.shadow_area_ratio == pytest.approx(0.0, abs=1e-2)
    assert metrics.mir_area == pytest.approx(100.0, rel=1e-2)
    assert metrics.mir_effective_ratio == pytest.approx(1.0, abs=1e-2)
    assert metrics.mir_aspect_ratio == pytest.approx(1.0, abs=1e-2)
    assert metrics.vertex_count == 4
    assert metrics.solidity == pytest.approx(1.0, abs=1e-2)
    assert metrics.shape_penalty_score == pytest.approx(1.0, abs=1e-2)
    assert metrics.shape_type == "regular"


def test_slender_plot_unagi():
    """うなぎの寝床（短辺2m x 奥行10m = 1:5 の極端な細長地）テスト"""
    vertices = [(0.0, 0.0), (2.0, 0.0), (2.0, 10.0), (0.0, 10.0)]
    metrics = analyze_plot_shape(vertices)

    assert metrics.plot_area == pytest.approx(20.0, rel=1e-2)
    assert metrics.mir_aspect_ratio == pytest.approx(0.20, abs=1e-2)
    assert metrics.is_unagi is True
    # うなぎの寝床ペナルティにより総合スコアが減価
    assert metrics.shape_penalty_score < 0.95
    assert metrics.shape_type in ["slender", "irregular"]


def test_flagpole_and_l_shape():
    """旗竿地・L字型敷地の幾何解析テスト（大きなかげ地＋路地状敷地）"""
    # 2m幅の路地(長さ8m)の先に 8m x 10m の敷地があるL字・旗竿形状
    # 頂点: (0,0) -> (2,0) -> (2,8) -> (10,8) -> (10,18) -> (0,18) -> (0,0)
    # 面積: 路地(2x8=16) + 本体(10x10=100) = 116
    # OBB: 10 x 18 = 180
    vertices = [
        (0.0, 0.0), (2.0, 0.0), (2.0, 8.0),
        (10.0, 8.0), (10.0, 18.0), (0.0, 18.0)
    ]
    metrics = analyze_plot_shape(vertices)

    # かげ地割合 = (180 - 116) / 180 = 64/180 = 0.355 (35%超のかげ地)
    assert metrics.shadow_area_ratio > 0.30
    # 最大内接矩形は本体部分の 10x10=100 (またはそれに近い矩形)
    assert metrics.mir_area >= 95.0
    # 有効敷地利用率は 1.0 未満（路地が除外されるため）
    assert metrics.mir_effective_ratio < 0.95
    # 凹みがあるため Solidity < 0.90
    assert metrics.solidity < 0.90
    # ペナルティスコアは減価される
    assert metrics.shape_penalty_score < 0.85
    assert metrics.shape_type in ["flagpole", "irregular"]


def test_complex_polygon_many_vertices():
    """頂点数が多数（8点以上）のギザギザ多角形テスト"""
    vertices = [
        (0.0, 0.0), (3.0, 1.0), (6.0, 0.0), (8.0, 2.0),
        (7.0, 5.0), (9.0, 8.0), (5.0, 9.0), (2.0, 7.0),
        (0.0, 4.0)
    ]
    metrics = analyze_plot_shape(vertices)

    assert metrics.vertex_count == 9
    assert metrics.vertex_penalty > 0.0
    assert metrics.shape_penalty_score < 0.90


def test_degenerate_input():
    """不正な頂点リスト（空、3点未満など）のフォールバック動作"""
    metrics = analyze_plot_shape([])
    assert metrics.plot_area == 0.0
    assert metrics.shape_penalty_score == 1.0
    assert metrics.shape_type == "unknown"

    metrics_2 = analyze_plot_shape([(0.0, 0.0), (1.0, 1.0)])
    assert metrics_2.plot_area == 0.0
    assert metrics_2.shape_type == "unknown"

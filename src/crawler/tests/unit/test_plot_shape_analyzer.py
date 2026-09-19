# -*- coding: utf-8 -*-
"""
土地形状幾何解析モジュールの単体テスト (test_plot_shape_analyzer.py)

最小外接矩形 (OBB)、最大内接矩形 (MIR)、かげ地割合、うなぎの寝床判定（縦横比）、
頂点数・複雑度（Solidity）、および統合ペナルティスコアを検証。
"""
import math
import pytest
from package.utils.plot_shape_analyzer import (
    analyze_plot_shape,
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


def test_mic_and_bottleneck():
    """最大内接円 (MIC) およびボトルネック最小幅員の算出テスト"""
    # 10m x 10m の正方形
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    metrics_sq = analyze_plot_shape(square)
    # 正方形の内接円直径は約10m
    assert metrics_sq.mic_diameter == pytest.approx(10.0, rel=0.08)
    assert metrics_sq.mic_coverage_ratio == pytest.approx(math.pi * 25.0 / 100.0, rel=0.08)
    assert metrics_sq.bottleneck_width == pytest.approx(10.0, rel=0.08)

    # 旗竿地: 2m幅路地(長8m) + 10m x 10m 本体
    flagpole = [(0.0, 0.0), (2.0, 0.0), (2.0, 8.0), (10.0, 8.0), (10.0, 18.0), (0.0, 18.0)]
    metrics_fp = analyze_plot_shape(flagpole)
    # 本体部分の最大内接円直径は約10m
    assert metrics_fp.mic_diameter == pytest.approx(10.0, rel=0.08)
    # ボトルネック幅員は路地幅の約2m
    assert metrics_fp.bottleneck_width == pytest.approx(2.0, rel=0.15)


def test_nta_discount_tables():
    """国税庁 相続税財産評価基本通達（附表2・3・4）テーブル補正率テスト"""
    from package.utils.plot_shape_analyzer import (
        calculate_nta_irregular_discount,
        calculate_nta_frontage_discount,
        calculate_nta_depth_discount,
    )
    # 附表2（不整形地補正率）
    assert calculate_nta_irregular_discount(0.05) == 1.00
    assert calculate_nta_irregular_discount(0.15) == 0.96
    assert calculate_nta_irregular_discount(0.25) == 0.92
    assert calculate_nta_irregular_discount(0.35) == 0.86
    assert calculate_nta_irregular_discount(0.45) == 0.79
    assert calculate_nta_irregular_discount(0.55) == 0.70
    assert calculate_nta_irregular_discount(0.65) == 0.60

    # 附表3（間口狭小補正率）
    assert calculate_nta_frontage_discount(9.0) == 1.00
    assert calculate_nta_frontage_discount(7.0) == 0.97
    assert calculate_nta_frontage_discount(5.0) == 0.94
    assert calculate_nta_frontage_discount(3.5) == 0.90
    assert calculate_nta_frontage_discount(2.5) == 0.85

    # 附表4（奥行長大補正率）
    assert calculate_nta_depth_discount(1.5) == 1.00
    assert calculate_nta_depth_discount(2.5) == 0.98
    assert calculate_nta_depth_discount(3.5) == 0.94
    assert calculate_nta_depth_discount(4.5) == 0.90
    assert calculate_nta_depth_discount(5.5) == 0.85


def test_interior_angles_and_acute_deadspace():
    """内角解析（鋭角頂点・凹角頂点）テスト"""
    from package.utils.plot_shape_analyzer import calculate_interior_angles

    # 正方形: すべて90度、鋭角なし、凹角なし
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    angles_sq, acute_sq, reflex_sq = calculate_interior_angles(square)
    assert len(angles_sq) == 4
    for a in angles_sq:
        assert a == pytest.approx(90.0, abs=1.0)
    assert acute_sq == 0
    assert reflex_sq == 0

    # 旗竿地・L字型: 1箇所の内角270度（くびれ凹角）が存在
    flagpole = [(0.0, 0.0), (2.0, 0.0), (2.0, 8.0), (10.0, 8.0), (10.0, 18.0), (0.0, 18.0)]
    angles_fp, acute_fp, reflex_fp = calculate_interior_angles(flagpole)
    assert reflex_fp >= 1

    # 三角地（底辺10m、高さ2mの偏平三角地）: 鋭角が2点（< 60度）
    triangle = [(0.0, 0.0), (10.0, 0.0), (5.0, 2.0)]
    angles_tri, acute_tri, reflex_tri = calculate_interior_angles(triangle)
    assert acute_tri >= 2


def test_flagpole_decomposition():
    """旗竿地（路地状敷地）専用分解解析テスト"""
    flagpole = [(0.0, 0.0), (2.0, 0.0), (2.0, 8.0), (10.0, 8.0), (10.0, 18.0), (0.0, 18.0)]
    metrics = analyze_plot_shape(flagpole)

    assert metrics.is_flagpole is True
    assert metrics.flagpole_passage_width == pytest.approx(2.0, rel=0.15)
    assert metrics.flagpole_passage_area == pytest.approx(16.0, rel=0.15)
    assert metrics.flagpole_passage_ratio == pytest.approx(16.0 / 116.0, rel=0.20)


def test_yoshino_formula_and_shape_grades():
    """吉野金次式（想定整形地）および総合鑑定格付けグレード (A〜E) テスト"""
    # 正方形: 特選整形地 Grade A
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    metrics_sq = analyze_plot_shape(square)
    assert metrics_sq.shape_grade == "A"
    assert metrics_sq.yoshino_shadow_ratio == pytest.approx(0.0, abs=0.05)
    assert metrics_sq.yoshino_coefficient == pytest.approx(1.0, abs=0.05)

    # 旗竿地: 不整形・旗竿地 Grade D または E
    flagpole = [(0.0, 0.0), (2.0, 0.0), (2.0, 8.0), (10.0, 8.0), (10.0, 18.0), (0.0, 18.0)]
    metrics_fp = analyze_plot_shape(flagpole)
    assert metrics_fp.shape_grade in ["D", "E"]
    assert metrics_fp.nta_composite_discount < 0.90
    assert metrics_fp.yoshino_shadow_ratio > 0.25

    # 極端なうなぎの寝床 (1:5): 難地 Grade E または D
    unagi = [(0.0, 0.0), (2.0, 0.0), (2.0, 10.0), (0.0, 10.0)]
    metrics_unagi = analyze_plot_shape(unagi)
    assert metrics_unagi.shape_grade in ["D", "E"]


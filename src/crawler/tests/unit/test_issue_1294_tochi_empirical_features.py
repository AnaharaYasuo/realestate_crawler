import pytest
from package.ml.features.parsers import parse_chimoku_features
from package.ml.features.feature_sets import FEATURE_SETS


def test_parse_chimoku_features_empirical_discounts():
    """実データ分析に基づく地目ディスカウントスコアの検証 (Issue #1294)"""
    # 宅地
    res_takuchi = parse_chimoku_features("宅地")
    assert res_takuchi["chimoku_score"] == 1.00
    assert res_takuchi["is_residential_chimoku"] == 1.0

    # 畑 (実測中央値比率 0.94)
    res_hatake = parse_chimoku_features("畑")
    assert res_hatake["chimoku_score"] == 0.94
    assert res_hatake["is_residential_chimoku"] == 0.0

    # 雑種地 (実測中央値比率 0.92)
    res_zasshu = parse_chimoku_features("雑種地")
    assert res_zasshu["chimoku_score"] == 0.92
    assert res_zasshu["is_residential_chimoku"] == 0.0

    # 現況宅地(登記は他) (実測中央値比率 0.89-0.90)
    res_genkyo = parse_chimoku_features("畑（現況地目：宅地）")
    assert res_genkyo["chimoku_score"] == 0.90
    assert res_genkyo["is_residential_chimoku"] == 1.0

    # 原野 (実測中央値比率 0.77)
    res_genya = parse_chimoku_features("原野")
    assert res_genya["chimoku_score"] == 0.77
    assert res_genya["is_residential_chimoku"] == 0.0

    # 山林 (実測中央値比率 0.68)
    res_sanrin = parse_chimoku_features("山林")
    assert res_sanrin["chimoku_score"] == 0.68
    assert res_sanrin["is_residential_chimoku"] == 0.0

    # 田 (実測中央値比率 0.63)
    res_ta = parse_chimoku_features("田")
    assert res_ta["chimoku_score"] == 0.63
    assert res_ta["is_residential_chimoku"] == 0.0

    # 未設定 / ハイフン (実測中央値比率 0.93-0.98)
    res_none = parse_chimoku_features(None)
    assert res_none["chimoku_score"] == 0.95
    assert res_none["is_residential_chimoku"] == 1.0

    res_hyphen = parse_chimoku_features("-")
    assert res_hyphen["chimoku_score"] == 0.95
    assert res_hyphen["is_residential_chimoku"] == 1.0

    # その他 (保安林等、実測中央値比率 0.47)
    res_other = parse_chimoku_features("保安林")
    assert res_other["chimoku_score"] == 0.50
    assert res_other["is_residential_chimoku"] == 0.0


def test_tochi_feature_sets_pruned_inactive_polygon_features():
    """土地モデルから不活性（全アルゴリズムで重要度0）な区画形状特徴量が除外されていることを検証 (Issue #1294)"""
    pruned_features = [
        "plot_shape_grade_num",
        "plot_compactness",
        "plot_flagpole_ratio",
        "plot_bottleneck_width",
        "plot_solidity",
        "plot_acute_angles",
        "plot_mic_diameter",
    ]
    for stage in ["first", "second"]:
        tochi_feats = FEATURE_SETS["tochi"][stage]
        for f in pruned_features:
            assert f not in tochi_feats, f"{f} should be pruned from tochi {stage} features"

        # 保持すべき重要特徴量が存在すること
        assert "chimoku_score" in tochi_feats
        assert "is_residential_chimoku" in tochi_feats
        assert "area" in tochi_feats
        assert "maguchi" in tochi_feats
        assert "road_width" in tochi_feats

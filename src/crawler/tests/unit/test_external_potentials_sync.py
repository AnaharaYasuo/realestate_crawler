# -*- coding: utf-8 -*-
"""
外部データ同期および特徴量連携の単体テスト (test_external_potentials_sync.py)

ハザードマップ（浸水・土砂リスク）、用途地域規制、地価変動率の同期と、
build_features での特徴量への反映を検証。
"""
import pytest
from package.models.evaluation import HazardMapPotential, UrbanPlanningZonePotential, LandPricePotential
from scripts.data_import.import_hazard_and_urban_zones import import_hazard_map, import_urban_planning_zones
from scripts.sync_all_potentials import run_all_syncs
from package.ml.features import build_features, _load_all_potential_caches_once


@pytest.mark.django_db
def test_import_hazard_and_urban_zones():
    """ハザードマップおよび用途地域データのインポート動作検証"""
    # 1. ハザードマップインポート
    import_hazard_map()
    h_count = HazardMapPotential.objects.count()
    assert h_count > 0

    tokyo_minato = HazardMapPotential.objects.filter(prefecture="東京都", city="港区").first()
    assert tokyo_minato is not None
    assert tokyo_minato.flood_risk_level >= 0

    # 2. 用途地域インポート
    import_urban_planning_zones()
    z_count = UrbanPlanningZonePotential.objects.count()
    assert z_count > 0

    chogyo = UrbanPlanningZonePotential.objects.filter(zone_name="商業地域").first()
    assert chogyo is not None
    assert chogyo.max_kenpei == 80
    assert chogyo.max_youseki >= 400


@pytest.mark.django_db
def test_sync_all_potentials_runs_with_new_steps():
    """sync_all_potentials が全5ステップを正常実行できることを検証"""
    # 他の外部通信を抑え、ローカルサンプルで同期
    results = run_all_syncs(skip_estat=True)
    assert "hazard_map" in results
    assert "urban_zones" in results
    assert results["hazard_map"]["status"] == "success"
    assert results["urban_zones"]["status"] == "success"


@pytest.mark.django_db
def test_build_features_with_hazard_and_urban_potentials():
    """build_features がハザード・用途地域・地価成長率・土地形状特徴量を出力することを確認"""
    # 準備: テスト用マスタデータを投入
    HazardMapPotential.objects.update_or_create(
        prefecture="東京都", city="江東区",
        defaults={"flood_risk_level": 3, "landslide_risk_level": 0}
    )
    UrbanPlanningZonePotential.objects.update_or_create(
        zone_name="第一種住居地域",
        defaults={"max_kenpei": 60, "max_youseki": 200}
    )
    LandPricePotential.objects.update_or_create(
        prefecture="東京都", city="江東区", land_use="residential",
        defaults={"average_land_price": 650000, "land_price_growth_rate": 4.5}
    )

    # キャッシュをリフレッシュ
    import package.ml.features as feat_mod
    feat_mod._muni_cache = {}
    feat_mod._hazard_cache = {}
    feat_mod._zone_cache = {}
    feat_mod._lp_cache = {}

    prop = {
        "address1": "東京都",
        "address2": "江東区豊洲",
        "area": 120.0,
        "price": 8000.0,
        "youseki": 200.0,
        "kenpei": 60.0,
        "zone_name": "第一種住居地域",
        # 敷地ポリゴン（整形）
        "plot_vertices": [(0, 0), (10, 0), (10, 12), (0, 12)]
    }

    features = build_features(prop, "tochi")

    # 新特徴量の検証
    assert "flood_risk_level" in features
    assert features["flood_risk_level"] == 3
    assert "landslide_risk_level" in features
    assert features["landslide_risk_level"] == 0

    assert "zone_max_kenpei" in features
    assert features["zone_max_kenpei"] == 60
    assert "zone_max_youseki" in features
    assert features["zone_max_youseki"] == 200

    assert "land_price_growth_rate" in features
    assert features["land_price_growth_rate"] == 4.5

    assert "plot_shadow_ratio" in features
    assert features["plot_shadow_ratio"] == pytest.approx(0.0, abs=1e-2)
    assert "plot_shape_penalty" in features
    assert features["plot_shape_penalty"] == pytest.approx(1.0, abs=1e-2)

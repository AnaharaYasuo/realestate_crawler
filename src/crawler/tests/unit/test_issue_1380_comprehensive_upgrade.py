# -*- coding: utf-8 -*-
"""
Issue #1380 包括アップグレード単体テストスイート:
1. 下限予測値 P10 (LightGBM Quantile Regression × Split Conformal Prediction)
2. 同一マンション棟 ＆ 半径500m cKDTree 空間 k-NN OOF 特徴量 (リークゼロ検証)
3. 津波・レッドゾーン・液状化ハザード拡張 ＆ 国交省標準地GISからの用途地域・建蔽容積率自動補完
4. 主要サイトパーサー (HOME'S / 健美家 / 野村 / 基底パーサー) の間口・道路幅員・建蔽容積率充填率改善
5. OpenCV (区画図輪郭幾何・内装フォトメトリクス) × gemini-2.5-flash (レート制限・多重リトライ) ハイブリッド画像解析
6. 16並列バルク評価の PK 昇順ソート更新・重複候補プール TTL キャッシュ
"""
from __future__ import annotations

import io
import time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
from sklearn.model_selection import GroupKFold

from package.ml.evaluation.persistence import (
    _prefetch_candidate_pool,
    bulk_update_evaluation_records,
    clear_candidate_pool_cache,
)
from package.ml.evaluation.record_builder import build_or_update_eval_record
from package.ml.features.builder import build_features
from package.ml.features.reference_data import (
    LandPricePointRecord,
    reset_reference_caches,
    resolve_zone_limits,
    set_land_price_point_cache_for_test,
)
from package.ml.inference.model_registry import ModelRegistry, set_default_registry
from package.ml.training.artifacts import save_metadata, save_stage_models
from package.ml.training.ensemble import train_and_compare
from package.ml.training.target_encoding import MicroLocationTargetEncoder
from package.models.evaluation import (
    HazardMapPotential,
    PropertyEvaluation,
    UrbanPlanningZonePotential,
)


def test_spatial_knn_and_building_oof_leak_free():
    """同一マンション棟 OOF と半径500m cKDTree k-NN OOF が自己/同一棟リークを起こさず近傍相場を反映すること"""
    # Building A (渋谷駅近く: 35.6580, 139.7016) 4戸, Building B (約180m隣: 35.6595, 139.7016) 4戸,
    # Building C (約6km離れた品川: 35.6080, 139.7300) 4戸, Building D/E (CV分割数確保用)
    rows = []
    groups = []
    prices = []
    coords_and_groups = [
        ("bldg_A", "東京都渋谷区渋谷1", 35.6580, 139.7016, 5.20),
        ("bldg_B", "東京都渋谷区渋谷1", 35.6595, 139.7016, 5.10),
        ("bldg_C", "東京都品川区大井1", 35.6080, 139.7300, 4.30),
        ("bldg_D", "東京都新宿区新宿1", 35.6900, 139.7000, 4.80),
        ("bldg_E", "東京都豊島区池袋1", 35.7300, 139.7100, 4.50),
    ]
    for b_name, chome, lat, lon, base_y in coords_and_groups:
        for i in range(4):
            rows.append(
                {
                    "prefecture": "東京都",
                    "city": chome[3:6],
                    "chome_group": chome,
                    "station": "渋谷",
                    "effective_walk_min": 5.0,
                    "building_group": b_name,
                    "latitude": lat + i * 0.00002,
                    "longitude": lon + i * 0.00002,
                }
            )
            groups.append(b_name)
            prices.append(base_y)

    df = pd.DataFrame(rows)
    y_base = np.array(prices, dtype=float)
    gkf = GroupKFold(n_splits=5)

    enc1 = MicroLocationTargetEncoder(smoothing=4.0)
    res1 = enc1.fit_transform_oof_extended(df, y_base, gkf, groups=np.array(groups))

    # Building A のターゲットだけを極端に吊り上げても、GroupKFold 下では Building A 自身の OOF 予測に自己リークしないこと
    y_spiked = y_base.copy()
    y_spiked[:4] = 9.50
    enc2 = MicroLocationTargetEncoder(smoothing=4.0)
    res2 = enc2.fit_transform_oof_extended(df, y_spiked, gkf, groups=np.array(groups))

    # Building A (index 0..3) の OOF は自身の fold 外データのみで計算されるため変化しない（リークゼロ）
    np.testing.assert_allclose(res1["building_oof"][:4], res2["building_oof"][:4], atol=1e-5)
    np.testing.assert_allclose(res1["knn_500m_oof"][:4], res2["knn_500m_oof"][:4], atol=1e-5)

    # 一方、約180m隣の Building B (index 4..7) の knn_500m_oof は Building A の上昇を反映して増加すること
    assert float(np.mean(res2["knn_500m_oof"][4:8])) > float(np.mean(res1["knn_500m_oof"][4:8])) + 0.5
    assert float(np.mean(res1["knn_500m_count"][4:8])) >= 4.0

    # 6km離れた Building C (index 8..11) は 500m 以内に他棟がないため count == 0 かつ chome へフォールバック
    assert float(np.max(res1["knn_500m_count"][8:12])) == 0.0

    # 全データ fit 後の推論 transform_extended では Building A 自身の棟実績も反映されること
    enc2.fit(df, y_spiked)
    inf = enc2.transform_extended(df.iloc[:2])
    assert float(inf["building_oof"][0]) > 6.5
    assert inf["knn_500m_oof"].shape == (2,)


@pytest.mark.django_db
def test_p10_quantile_conformal_training_and_inference(tmp_path):
    """P10 分位点回帰 + Split Conformal 較正の学習・保存・推論・評価レコード反映の検証"""
    from package.ml.predict import bulk_predict_first_stage_with_p10

    rng = np.random.default_rng(42)
    n = 60
    areas = rng.uniform(50.0, 90.0, size=n)
    walk = rng.uniform(2.0, 18.0, size=n)
    unit_price = 95.0 - 1.5 * walk + rng.normal(0.0, 6.0, size=n)
    prices = np.maximum(1500.0, unit_price * areas)
    bldg_groups = np.array([f"bldg_{i // 3}" for i in range(n)])

    df = pd.DataFrame(
        {
            "price": prices,
            "area": areas,
            "walk_min": walk,
            "effective_walk_min": walk,
            "chikunen": rng.uniform(1.0, 30.0, size=n),
            "prefecture": ["東京都"] * n,
            "city": ["品川区"] * n,
            "chome_group": [f"東京都品川区小山{(i % 4) + 1}" for i in range(n)],
            "station": ["武蔵小山"] * n,
            "building_group": bldg_groups,
            "latitude": 35.6200 + rng.uniform(-0.004, 0.004, size=n),
            "longitude": 139.7040 + rng.uniform(-0.004, 0.004, size=n),
            "micro_land_price": [750000.0] * n,
            "chome_oof_unit_price": [0.0] * n,
            "station_walk_oof_unit_price": [0.0] * n,
            "building_oof_unit_price": [0.0] * n,
            "knn_500m_oof_unit_price": [0.0] * n,
            "knn_500m_comp_count": [0.0] * n,
            "anchor_log_unit_price": np.log1p(80.0) * np.ones(n),
        }
    )
    feat_cols = [
        "area",
        "walk_min",
        "chikunen",
        "chome_oof_unit_price",
        "station_walk_oof_unit_price",
        "building_oof_unit_price",
        "knn_500m_oof_unit_price",
        "knn_500m_comp_count",
        "anchor_log_unit_price",
    ]
    with patch("package.ml.training.ensemble.ALGOS", ["lgb"]):
        ens = train_and_compare(df, feat_cols, "mansion - First Stage")

    assert ens.p10_model is not None
    assert isinstance(ens.p10_conformal_offset, float)

    model_dir = str(tmp_path / "models")
    import os

    os.makedirs(model_dir, exist_ok=True)
    save_stage_models(ens, model_dir, "mansion", "first")
    save_metadata(
        model_dir,
        {"mansion": {"first": ens.weights}},
        {"mansion": {"first": ens.smearing_factor}},
        mkt_master={},
        location_encoders={"mansion": {"first": ens.location_encoder}},
        p10_conformal={"mansion": {"first": ens.p10_conformal_offset}},
    )
    assert os.path.exists(os.path.join(model_dir, "mansion_first_stage_p10.joblib"))
    assert os.path.exists(os.path.join(model_dir, "p10_conformal.joblib"))

    reg = ModelRegistry(model_dir=model_dir)
    prev_reg = None
    try:
        from package.ml.inference.model_registry import get_default_registry

        prev_reg = get_default_registry()
        set_default_registry(reg)

        prop = SimpleNamespace(
            id=101,
            pageUrl="https://example.com/mansion/101",
            price=45000000,
            senyuMenseki=Decimal("65.0"),
            address="東京都品川区小山1丁目",
            address1="東京都",
            address2="品川区",
            station1="武蔵小山",
            railwayWalkMinute1=5,
            chikunengetsuStr="2015年4月",
            propertyName="テストレジデンス武蔵小山",
            propertyType="mansion",
        )
        point_preds, p10_preds = bulk_predict_first_stage_with_p10([prop])
        assert len(point_preds) == 1 and len(p10_preds) == 1
        assert point_preds[0] > 0
        assert 0 < p10_preds[0] <= point_preds[0]

        rec, is_new = build_or_update_eval_record(
            item=prop,
            price_stage1=float(point_preds[0]),
            existing=None,
            company="mitsui",
            property_type="mansion",
            skip_duplicate_check=True,
            p10_stage1=float(p10_preds[0]),
        )
        assert is_new is True
        assert int(rec.first_stage_p10_price) == p10_preds[0]
        assert rec.prediction_uncertainty_ratio is not None
        assert 0.0 <= float(rec.prediction_uncertainty_ratio) < 1.0
    finally:
        set_default_registry(prev_reg)


@pytest.mark.django_db
def test_hazard_expansion_and_gis_zoning_imputation():
    """津波・レッドゾーン・液状化ハザード特徴量と、用途地域・建蔽容積率欠損時のGIS標準地補完の検証"""
    reset_reference_caches()
    UrbanPlanningZonePotential.objects.update_or_create(
        zone_name="商業地域",
        defaults={"max_kenpei": 80, "max_youseki": 500},
    )
    HazardMapPotential.objects.update_or_create(
        prefecture="神奈川県",
        city="鎌倉市",
        defaults={
            "flood_risk_level": 2,
            "landslide_risk_level": 2,
            "tsunami_risk_level": 3,
            "red_zone_landslide_flag": 1,
            "liquefaction_risk_level": 2,
        },
    )
    reset_reference_caches()
    set_land_price_point_cache_for_test(
        [
            LandPricePointRecord(
                prefecture="神奈川県",
                city="鎌倉市",
                chome_key="神奈川県鎌倉市小町1",
                latitude=35.3192,
                longitude=139.5504,
                land_price=620000,
                growth_rate=3.5,
                land_use="commercial",
                road_width=8.0,
                station_name="鎌倉",
                station_distance_m=150,
                has_gas=True,
                has_water=True,
                has_sewer=True,
                zone_name="商業地域",
            )
        ]
    )

    # 物件自身には youtoChiiki / kenpei / youseki が一切無いケース
    prop = SimpleNamespace(
        id=1,
        pageUrl="https://example.com/tochi/kamakura-1",
        price=58000000,
        tochiMenseki=Decimal("100.0"),
        address="神奈川県鎌倉市小町1丁目",
        address1="神奈川県",
        address2="鎌倉市",
        station1="鎌倉",
        railwayWalkMinute1=3,
        latitude=35.3193,
        longitude=139.5505,
        youtoChiiki="",
        kenpei=None,
        youseki=None,
    )
    max_youseki, max_kenpei, _, _, imputed_zone = resolve_zone_limits(
        prop,
        prefecture="神奈川県",
        city="鎌倉市",
        chome_group="神奈川県鎌倉市小町1",
        latitude=35.3193,
        longitude=139.5505,
    )
    assert imputed_zone == "商業地域"
    assert max_kenpei == 80.0
    assert max_youseki == 500.0

    feats = build_features(prop, "tochi")
    assert feats["tsunami_risk_level"] == 3
    assert feats["red_zone_landslide_flag"] == 1
    assert feats["liquefaction_risk_level"] == 2
    assert feats["max_kenpei"] == 80.0
    assert feats["max_youseki"] == 500.0
    assert feats["is_commercial_zone"] == 1.0


def test_parser_fill_rate_homes_kenbiya_nomura_base():
    """HOME'S / 健美家 / 野村 / 基底パーサーの間口・道路幅員・建蔽容積率・用途地域の抽出精度検証"""
    from package.parser.homesParser import HomesKodateParser
    from package.parser.kenbiyaParser import KenbiyaTochiParser
    from package.parser.nomuraParser import NomuraTochiParser

    # 1. HOME'S: 全角「ｍ」および「接道:南4.0ｍ 公道 接面8.5ｍ」で幅員4.0と間口8.5を取り違えないこと
    homes_html = """
    <html><body>
      <h1>ホームズ戸建テスト</h1>
      <table>
        <tr><th>価格</th><td>3,980万円</td></tr>
        <tr><th>所在地</th><td>東京都世田谷区松原1丁目</td></tr>
        <tr><th>交通</th><td>京王線 明大前駅 徒歩6分</td></tr>
        <tr><th>土地面積</th><td>92.45m²</td></tr>
        <tr><th>建物面積</th><td>88.12m²</td></tr>
        <tr><th>接道状況</th><td>一方 接道:南4.0ｍ 公道 接面8.5ｍ</td></tr>
        <tr><th>建ぺい率/容積率</th><td>60% / 160%</td></tr>
        <tr><th>用途地域</th><td>第一種低層住居専用地域</td></tr>
        <tr><th>地目</th><td>宅地</td></tr>
        <tr><th>土地権利</th><td>所有権</td></tr>
      </table>
    </body></html>
    """
    hp = HomesKodateParser()
    h_item = hp.createEntity()
    h_soup = BeautifulSoup(homes_html, "html.parser")
    h_item = hp._parsePropertyDetailPage(h_item, h_soup)
    assert h_item.roadWidth == Decimal("4.0")
    assert h_item.maguchi == Decimal("8.5")
    assert h_item.youtoChiiki == "第一種低層住居専用地域"
    assert h_item.chimoku == "宅地"
    assert h_item.tochikenri == "所有権"
    assert int(h_item.kenpei) == 60
    assert int(h_item.youseki) == 160

    # 2. 健美家 Tochi: _parsePropertyDetailPage で maguchi と roadWidth が実際に item に代入されること
    kenbiya_html = """
    <html><body>
      <h1>健美家売地テスト</h1>
      <table>
        <tr><th>価格</th><td>2,480万円</td></tr>
        <tr><th>所在地</th><td>埼玉県さいたま市浦和区高砂2丁目</td></tr>
        <tr><th>交通</th><td>JR京浜東北線 浦和駅 徒歩8分</td></tr>
        <tr><th>土地面積</th><td>120.00㎡</td></tr>
        <tr><th>接道状況</th><td>東側 公道 幅員5.2m 間口9.1m</td></tr>
        <tr><th>建ぺい率/容積率</th><td>60% / 200%</td></tr>
        <tr><th>用途地域</th><td>第一種住居地域</td></tr>
      </table>
    </body></html>
    """
    kp = KenbiyaTochiParser()
    k_item = kp.createEntity()
    k_item = kp._parsePropertyDetailPage(k_item, BeautifulSoup(kenbiya_html, "html.parser"))
    assert k_item.maguchi == Decimal("9.1")
    assert k_item.roadWidth == Decimal("5.2")
    assert k_item.kenpei == 60
    assert k_item.youseki == 200

    # 3. 野村 Tochi: 複合「建蔽率・容積率」表記からの抽出
    nomura_html = """
    <html><body>
      <h1>野村売地テスト</h1>
      <table class="c_table_spec">
        <tr><th>価格</th><td>5,500万円</td><th>所在地</th><td>東京都杉並区荻窪3丁目</td></tr>
        <tr><th>土地面積</th><td>110.5㎡</td><th>建蔽率/容積率</th><td>50% / 100%</td></tr>
        <tr><th>接道状況</th><td>南側 幅員4.5m 公道 接面7.8m</td><th>用途地域</th><td>第一種低層住居専用地域</td></tr>
      </table>
    </body></html>
    """
    np_parser = NomuraTochiParser()
    n_item = np_parser.createEntity()
    n_item = np_parser._parsePropertyDetailPage(n_item, BeautifulSoup(nomura_html, "html.parser"))
    assert int(n_item.kenpei) == 50
    assert int(n_item.youseki) == 100


def test_opencv_contour_photometrics_and_gemini_rate_limiter_hybrid(monkeypatch):
    """OpenCV の区画図ポリゴン輪郭計測＋内装採点と、Gemini 2.5 Flash 2秒レート制限・リトライ・融合の検証"""
    from package.utils.gemini_rate_limiter import GeminiFlashRateLimiter
    from package.utils.image_handler import analyze_property_images_hybrid
    from package.utils.opencv_image_analyzer import analyze_pil_images_with_opencv

    # 1. 区画図 (白背景に黒線のL字型不整形ポリゴン) と明るい内装画像を生成
    plot_img = Image.new("RGB", (400, 400), color=(255, 255, 255))
    draw_p = ImageDraw.Draw(plot_img)
    l_poly = [(60, 60), (220, 60), (220, 210), (340, 210), (340, 340), (60, 340)]
    draw_p.polygon(l_poly, fill=(235, 242, 235), outline=(20, 20, 20), width=5)

    int_img = Image.new("RGB", (400, 300), color=(235, 232, 225))
    draw_i = ImageDraw.Draw(int_img)
    for x in range(40, 360, 40):
        draw_i.rectangle((x, 40, x + 20, 250), outline=(120, 100, 80), width=2)

    cv_res = analyze_pil_images_with_opencv(
        [("plot_plan", plot_img), ("interior", int_img)]
    )
    assert cv_res["shadow_area_ratio"] is not None
    assert 0.05 <= cv_res["shadow_area_ratio"] <= 0.60
    assert cv_res["shape_score_100"] is not None
    assert cv_res["nta_irregular_discount"] is not None
    assert 1.0 <= cv_res["interior_score"] <= 5.0

    # 2. GeminiFlashRateLimiter: 間隔制御および 429 一時エラーからの自動リトライ成功
    limiter = GeminiFlashRateLimiter(min_interval_sec=0.06, max_retries=3, base_backoff_sec=0.02)
    call_times: list[float] = []
    attempts = {"n": 0}

    def flaky_fn():
        call_times.append(time.perf_counter())
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: quota rate limit")
        return {"ok": True}

    out1 = limiter.execute(flaky_fn)
    out2 = limiter.execute(lambda: (call_times.append(time.perf_counter()), {"ok": 2})[1])
    assert out1 == {"ok": True}
    assert out2 == {"ok": 2}
    assert attempts["n"] == 3
    assert call_times[-1] - call_times[-2] >= 0.05

    # 3. ハイブリッド融合: GEMINI_API_KEY 未設定時は OpenCV の実測スコアがそのまま返ること
    buf_p = io.BytesIO()
    plot_img.save(buf_p, format="PNG")
    mock_http = MagicMock(status_code=200, content=buf_p.getvalue())
    monkeypatch.setattr("requests.get", lambda url, timeout=10: mock_http)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    hybrid_no_key = analyze_property_images_hybrid(
        [{"url": "http://example.com/kukaku.png", "category": "plot_plan"}]
    )
    assert hybrid_no_key["shadow_area_ratio"] == cv_res["shadow_area_ratio"]
    assert hybrid_no_key["shape_score_100"] == cv_res["shape_score_100"]

    # GEMINI_API_KEY 設定時は Gemini の定性判定 (擁壁・リノベ規模) と OpenCV の精密幾何が融合されること
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.models.generate_content.return_value = MagicMock(
        text='{"retaining_wall_risk": "stone_masonry", "renovation_budget_tier": "tier_heavy", "layout_score": 4.2}'
    )
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
    monkeypatch.setenv("GEMINI_MIN_INTERVAL_SEC", "0.01")
    monkeypatch.setattr("google.genai.Client", lambda *a, **kw: mock_client)

    hybrid_fused = analyze_property_images_hybrid(
        [{"url": "http://example.com/kukaku.png", "category": "plot_plan"}]
    )
    assert hybrid_fused["retaining_wall_risk"] == "stone_masonry"
    assert hybrid_fused["renovation_budget_tier"] == "tier_heavy"
    assert hybrid_fused["layout_score"] == 4.2
    assert hybrid_fused["shadow_area_ratio"] == cv_res["shadow_area_ratio"]


def test_bulk_update_pk_ascending_sort_and_candidate_cache():
    """bulk_update_evaluation_records が PK 昇順ソートでデッドロックを防ぎ、候補プールを TTL キャッシュすること"""
    recs = [
        SimpleNamespace(pk=42),
        SimpleNamespace(pk=7),
        SimpleNamespace(pk=19),
        SimpleNamespace(pk=7),
        SimpleNamespace(pk=3),
    ]
    captured_pks: list[int] = []

    def fake_bulk_update(objs, fields, batch_size):
        captured_pks.extend([o.pk for o in objs])

    with patch.object(PropertyEvaluation.objects, "bulk_update", side_effect=fake_bulk_update):
        bulk_update_evaluation_records(recs, property_type="kodate", batch_size=100)

    assert captured_pks == [3, 7, 19, 42]

    # Candidate pool TTL cache: 同一 property_type の連続チャンクでは DB 再クエリしないこと
    clear_candidate_pool_cache()
    fake_eval_map = {"u1": SimpleNamespace(id=500), "u2": SimpleNamespace(id=600)}
    fake_candidate = MagicMock(id=100)
    with (
        patch.object(PropertyEvaluation.objects, "filter") as mock_filter,
        patch("package.utils.deduplication._prefetch_real_properties"),
    ):
        mock_filter.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = [
            fake_candidate
        ]
        p1 = _prefetch_candidate_pool(fake_eval_map, "kodate")
        p2 = _prefetch_candidate_pool(fake_eval_map, "kodate")
        assert p1 == [fake_candidate]
        assert p2 == [fake_candidate]
        assert mock_filter.call_count == 1
    clear_candidate_pool_cache()

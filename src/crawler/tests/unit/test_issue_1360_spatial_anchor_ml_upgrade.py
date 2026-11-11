"""Unit tests for Issue #1360: Zero-AI-Cost Spatial KNN Land Prices, Hierarchical OOF Encoding,
Anchor-Residual Learning, Parser Maguchi Disambiguation, and Fixed-Cost Valuation Features.
"""
from decimal import Decimal
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import GroupKFold

import setup_env  # noqa: F401
from package.ml.features import FEATURE_SETS, build_features
from package.ml.inference.model_registry import ModelRegistry
from package.ml.inference.predictor import bulk_predict
from package.ml.training.artifacts import save_metadata, save_stage_models
from package.ml.training.cleaning import clean_training_data
from package.ml.training.ensemble import train_and_compare
from package.parser.baseParser import TochiParserBase


@pytest.fixture(autouse=True)
def _no_db_global_cache():
    with patch("package.ml.features.builder._init_global_caches"), patch(
        "package.ml.features.reference_data._init_global_caches"
    ):
        yield


class _DummyProp:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestIssue1360ParserAndFeatureIntegrity:
    def test_maguchi_extraction_does_not_grab_road_width(self):
        """接道文字列の先頭にある道路幅員（4.0m）を間口（8.5m）として誤抽出しないことを検証"""
        text = "北側 幅員4.0m 公道 接面8.5m"
        assert TochiParserBase._extract_maguchi_decimal(text) == Decimal("8.5")

        text2 = "南東 道路6.0m 間口 約10.2ｍ 舗装有"
        assert TochiParserBase._extract_maguchi_decimal(text2) == Decimal("10.2")

        # 幅員しか書かれていない接道状況ラベルからは間口を誤抽出せず None とする
        text_only_width = "北側 公道 幅員4.2m"
        assert TochiParserBase._extract_maguchi_decimal(text_only_width, allow_bare_meter=False) is None
        # 間口専用ラベルの値（「7.5m」単体）ならそのまま抽出できる
        assert TochiParserBase._extract_maguchi_decimal("7.5m", allow_bare_meter=True) == Decimal("7.5")

    def test_missingness_flags_and_gross_area_denominator_preserved(self):
        """間口・幅員欠損フラグが正しく立ち、セットバック発生時も目的変数分母 area は公簿面積を維持することを検証"""
        prop_missing = _DummyProp(
            tochiMenseki=100.0,
            address1="東京都",
            address2="世田谷区",
            address="東京都世田谷区成城6-1-1",
            station1="成城学園前",
            railwayWalkMinute1=8,
            youtoChiiki="第一種低層住居専用地域",
        )
        feats_missing = build_features(prop_missing, "tochi")
        assert feats_missing["is_maguchi_missing"] == 1.0
        assert feats_missing["is_road_width_missing"] == 1.0
        assert feats_missing["area"] == pytest.approx(100.0)

        prop_narrow = _DummyProp(
            tochiMenseki=100.0,
            roadWidth=2.8,
            maguchi=8.0,
            address1="東京都",
            address2="世田谷区",
            address="東京都世田谷区成城6-1-1",
            station1="成城学園前",
            railwayWalkMinute1=8,
            youtoChiiki="第一種低層住居専用地域",
        )
        feats_narrow = build_features(prop_narrow, "tochi")
        assert feats_narrow["is_maguchi_missing"] == 0.0
        assert feats_narrow["is_road_width_missing"] == 0.0
        # 公簿・契約面積は 100.0㎡ を維持し、有効敷地面積のみセットバック控除される
        assert feats_narrow["area"] == pytest.approx(100.0)
        assert feats_narrow["effective_tochi_menseki"] == pytest.approx(95.2)
        assert feats_narrow["setback_ratio"] > 0.0

    def test_zero_cost_fixed_deduction_and_risk_text_features(self):
        """AI課金なしで備考・設備・接道テキストから引込費・擁壁高低差費・袋小路・確定測量・持分売買を抽出"""
        risky_land = _DummyProp(
            tochiMenseki=100.0,
            address1="神奈川県",
            address2="横浜市青葉区",
            address="神奈川県横浜市青葉区美しが丘2-1",
            biko="道路より約2.5m高い ひな段 間知石擁壁あり 個別プロパン 浄化槽 上水道引込無 位置指定道路（行き止まり） 公簿取引",
        )
        f_risky = build_features(risky_land, "tochi")
        assert f_risky["infra_connection_score"] < 0.70
        assert f_risky["estimated_infra_cost_man"] >= 150.0
        assert f_risky["elevation_diff_m"] == pytest.approx(2.5)
        assert f_risky["retaining_wall_cost_man"] >= 200.0
        assert f_risky["estimated_fixed_cost_man"] >= (
            f_risky["estimated_infra_cost_man"] + f_risky["retaining_wall_cost_man"]
        )
        assert f_risky["fixed_cost_per_sqm"] == pytest.approx(f_risky["estimated_fixed_cost_man"] / 100.0, rel=1e-2)
        assert f_risky["is_cul_de_sac_road"] == 1.0
        assert f_risky["is_measured_boundary"] == 0.0

        clean_land = _DummyProp(
            tochiMenseki=210.0,
            maguchi=11.5,
            roadWidth=6.0,
            address1="神奈川県",
            address2="横浜市青葉区",
            address="神奈川県横浜市青葉区美しが丘2-2",
            biko="確定測量済 境界明示 公共下水・都市ガス・公営水道敷地内引込済",
        )
        f_clean = build_features(clean_land, "tochi")
        assert f_clean["infra_connection_score"] == pytest.approx(1.0)
        assert f_clean["estimated_infra_cost_man"] == pytest.approx(0.0)
        assert f_clean["is_measured_boundary"] == 1.0
        assert f_clean["is_cul_de_sac_road"] == 0.0
        assert f_clean["subdivision_potential_score"] > f_risky["subdivision_potential_score"]
        assert f_clean["dcf_theoretical_value"] > 0.0

        share_land = _DummyProp(
            tochiMenseki=120.0,
            address1="東京都",
            address2="足立区",
            biko="共有持分1/2のみ売買 現況有姿",
        )
        f_share = build_features(share_land, "tochi")
        assert f_share["is_special_sale_share"] == 1.0

    def test_tochi_second_stage_excludes_paid_ai_interior_layout_scores(self):
        """土地の二次モデル特徴量に不要な内装・間取りAIスコアが含まれないこと"""
        assert "interior_score" not in FEATURE_SETS["tochi"]["second"]
        assert "layout_score" not in FEATURE_SETS["tochi"]["second"]

    def test_stage2_skips_gemini_image_billing_for_tochi(self):
        """_resolve_stage2_analysis_inputs が土地(tochi)では check_api_budget_cap や Gemini 画像APIを一切呼ばないこと"""
        import asyncio
        from unittest.mock import MagicMock
        from package.api.api import ParseDetailPageAsyncBase

        item = _DummyProp(propertyName="世田谷区成城土地", pageUrl="https://example.com/tochi/1")
        eval_rec = _DummyProp(
            plot_shape_type="regular",
            plot_shape_description="整形地",
            maintenance_score=4,
            maintenance_comment="",
        )
        budget_mock = MagicMock(side_effect=AssertionError("budget check must not be called for tochi"))
        gemini_mock = MagicMock(side_effect=AssertionError("paid Gemini API must not be called for tochi"))

        res = asyncio.run(
            ParseDetailPageAsyncBase._resolve_stage2_analysis_inputs(
                None, item, eval_rec, "tochi", ["https://example.com/1.jpg"], budget_mock, gemini_mock
            )
        )
        assert res is not None
        assert res["interior_score"] == 3.0
        assert res["plot_shape_type"] == "regular"
        budget_mock.assert_not_called()
        gemini_mock.assert_not_called()

    def test_gsi_free_geocoder_cache_and_bounds(self, tmp_path):
        """国土地理院無料ジオコーダが日本国内座標のみ受理しローカルキャッシュで外部通信ゼロ参照できること"""
        from unittest.mock import MagicMock
        from package.utils import gsi_geocoder

        cache_file = tmp_path / "gsi_cache.json"
        gsi_geocoder._MEMORY_CACHE.clear()
        gsi_geocoder._DISK_LOADED = False

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = [{"geometry": {"coordinates": [139.6001, 35.6412]}}]
        with patch("package.utils.gsi_geocoder.requests.get", return_value=fake_resp) as mock_get:
            coords = gsi_geocoder.geocode_address_gsi(
                "東京都世田谷区成城 6-1-1", persist_cache=True, cache_path=cache_file
            )
            assert coords == pytest.approx((35.6412, 139.6001))
            assert mock_get.call_count == 1

            # 2回目はキャッシュヒットし通信ゼロ
            cached = gsi_geocoder.lookup_cached_coordinates("東京都世田谷区成城6-1-1", cache_path=cache_file)
            assert cached == pytest.approx((35.6412, 139.6001))
            assert mock_get.call_count == 1


class TestIssue1360SpatialPointKnnAndGeoJson:
    def teardown_method(self):
        from package.ml.features import reference_data as ref_mod

        if hasattr(ref_mod, "set_land_price_point_cache_for_test"):
            ref_mod.set_land_price_point_cache_for_test([])

    def test_extract_point_records_from_l01_and_l02_geojson(self):
        """国土数値情報 L01(地価公示)・L02(地価調査) GeoJSONから座標・町丁目・インフラフラグを保持抽出"""
        from scripts.data_import.import_mlit_land_prices import extract_point_records_from_geojson_features
        features = [
            {
                "geometry": {"type": "Point", "coordinates": [139.6001, 35.6412]},
                "properties": {
                    "L01_001": "13-112-001",
                    "L01_006": 920000,
                    "L01_007": 4.5,
                    "L01_024": "東京都世田谷区成城６丁目１０番１号",
                    "L01_027": "住宅",
                    "L01_037": 60,
                    "L01_044": "1",
                    "L01_045": "1",
                    "L01_046": "1",
                    "L01_047": "成城学園前",
                    "L01_048": 450,
                    "L01_051": "1低専",
                },
            },
            {
                "geometry": {"type": "Point", "coordinates": [139.6125, 35.6210]},
                "properties": {
                    "L02_001": "13-112-L02-05",
                    "L02_006": 390000,
                    "L02_007": 1.2,
                    "L02_022": "東京都世田谷区宇奈根１丁目５番",
                    "L02_025": "住宅",
                    "L02_035": 4.0,
                    "L02_042": True,
                    "L02_043": True,
                    "L02_044": False,
                },
            },
        ]
        pts = extract_point_records_from_geojson_features(features, default_survey="L01")
        assert len(pts) == 2
        p0 = pts[0]
        assert p0["prefecture"] == "東京都"
        assert p0["city"] == "世田谷区"
        assert p0["chome_key"] == "東京都世田谷区成城6"
        assert p0["latitude"] == pytest.approx(35.6412)
        assert p0["longitude"] == pytest.approx(139.6001)
        assert p0["land_price"] == 920000
        assert p0["has_gas"] is True
        assert p0["has_sewer"] is True

    def test_spatial_knn_and_chome_micro_land_price_across_all_types(self):
        """同一市区町村内でも町丁目・座標KNNにより一等地と郊外バス便地で micro_land_price が明確に分離される"""
        from package.ml.features.reference_data import (
            query_micro_land_price_features,
            set_land_price_point_cache_for_test,
        )
        from package.ml.features.reference_records import LandPricePointRecord

        set_land_price_point_cache_for_test([
            LandPricePointRecord(
                prefecture="東京都",
                city="世田谷区",
                chome_key="東京都世田谷区成城6",
                latitude=35.6412,
                longitude=139.6001,
                land_price=950000,
                growth_rate=4.8,
                land_use="residential",
                road_width=6.0,
                station_name="成城学園前",
                station_distance_m=400,
                has_gas=True,
                has_water=True,
                has_sewer=True,
            ),
            LandPricePointRecord(
                prefecture="東京都",
                city="世田谷区",
                chome_key="東京都世田谷区宇奈根1",
                latitude=35.6180,
                longitude=139.6080,
                land_price=360000,
                growth_rate=1.0,
                land_use="residential",
                road_width=4.0,
                station_name="二子玉川",
                station_distance_m=2400,
                has_gas=False,
                has_water=True,
                has_sewer=True,
            ),
        ])

        prime_prop = _DummyProp(
            senyuMenseki=70.0,
            tochiMenseki=120.0,
            tatemonoMenseki=100.0,
            address1="東京都",
            address2="世田谷区",
            address="東京都世田谷区成城6-8-2",
            station1="成城学園前",
            railwayWalkMinute1=5,
        )
        suburb_prop = _DummyProp(
            senyuMenseki=70.0,
            tochiMenseki=120.0,
            tatemonoMenseki=100.0,
            address1="東京都",
            address2="世田谷区",
            address="東京都世田谷区宇奈根1-12-3",
            station1="二子玉川",
            railwayWalkMinute1=28,
        )

        for ptype in ("tochi", "kodate", "mansion", "apartment"):
            f_prime = build_features(prime_prop, ptype)
            f_suburb = build_features(suburb_prop, ptype)
            assert f_prime["micro_land_price"] > f_suburb["micro_land_price"] * 2.0
            assert f_prime["micro_to_muni_land_ratio"] > f_suburb["micro_to_muni_land_ratio"]
            assert f_prime["chome_infra_score"] > f_suburb["chome_infra_score"]

        # 未知町丁目でも緯度経度が与えられれば空間KNN(IDW)で近傍地点単価へ補間される
        knn_price, _ = query_micro_land_price_features(
            "東京都", "世田谷区", "東京都世田谷区成城99", 100.0, 620000, latitude=35.6415, longitude=139.6005
        )
        assert knn_price > 850000


class TestIssue1360HierarchicalOofAnchorResidualAndCleansing:
    def test_hierarchical_oof_encoder_shrinks_to_city_not_global(self):
        """少数サンプル町丁目のOOFエンコーディングが全国平均ではなく同一市区町村水準へ階層縮小されること"""
        from package.ml.training.target_encoding import MicroLocationTargetEncoder
        df = pd.DataFrame({
            "prefecture": ["東京都"] * 6 + ["秋田県"] * 6,
            "city": ["港区"] * 6 + ["能代市"] * 6,
            "chome_group": [
                "東京都港区赤坂1", "東京都港区赤坂1", "東京都港区赤坂1",
                "東京都港区赤坂2", "東京都港区赤坂2", "東京都港区元麻布9",
                "秋田県能代市柳町1", "秋田県能代市柳町1", "秋田県能代市柳町1",
                "秋田県能代市柳町2", "秋田県能代市柳町2", "秋田県能代市落合9",
            ],
            "station": ["赤坂"] * 6 + ["能代"] * 6,
            "effective_walk_min": [4.0, 5.0, 4.0, 7.0, 8.0, 6.0, 12.0, 15.0, 14.0, 20.0, 22.0, 18.0],
            "building_group": [f"g_{i}" for i in range(12)],
            "price": [24000, 25000, 23500, 22000, 21500, 23000, 300, 320, 280, 260, 250, 290],
            "area": [100.0] * 12,
        })
        y = pd.Series(np.log1p(df["price"] / df["area"]))
        cv = GroupKFold(n_splits=3)
        groups = df["building_group"].to_numpy()

        enc = MicroLocationTargetEncoder(smoothing=5.0)
        oof_chome, oof_st = enc.fit_transform_oof(df, y, cv, groups=groups)
        assert len(oof_chome) == 12
        assert len(oof_st) == 12
        # 単発町丁目「元麻布9」(idx=5)でも港区の他Fold水準にシュリンクされるため、能代市(idx=11)より圧倒的に高い
        assert oof_chome[5] > oof_chome[11] + 2.0

        # 推論時: 港区の未知町丁目「東京都港区白金99」でも港区平均へフォールバックする
        test_df = pd.DataFrame({
            "prefecture": ["東京都", "秋田県"],
            "city": ["港区", "能代市"],
            "chome_group": ["東京都港区白金99", "秋田県能代市未知99"],
            "station": ["未知駅", "未知駅"],
            "effective_walk_min": [5.0, 20.0],
        })
        chome_pred, _ = enc.transform(test_df)
        assert chome_pred[0] > chome_pred[1] + 2.5

    def test_anchor_residual_estimator_preserves_log_unit_interface(self):
        """AnchorResidualEstimator が基準単価からの残差を学習し、推論時に log1p(unit_price) スケールを正確に返す"""
        from sklearn.ensemble import RandomForestRegressor
        from package.ml.training.anchor_residual import AnchorResidualEstimator

        rng = np.random.default_rng(42)
        n = 60
        anchors = np.concatenate([np.full(30, np.log1p(5.0)), np.full(30, np.log1p(50.0))])
        corner = rng.integers(0, 2, size=n).astype(float)
        # 角地なら単価 +12% プレミアム
        y = anchors + corner * 0.12
        X = pd.DataFrame({
            "anchor_log_unit_price": anchors,
            "is_corner_lot": corner,
        })

        rf = RandomForestRegressor(n_estimators=20, max_depth=3, random_state=42, n_jobs=2)
        est = AnchorResidualEstimator(rf, anchor_col="anchor_log_unit_price")
        sw = np.ones(n, dtype=float)
        sw[:30] = 0.01  # sample_weight 転送確認用
        assert est.fit(X, y, sample_weight=sw) is est
        assert list(est.feature_names_in_) == ["anchor_log_unit_price", "is_corner_lot"]
        assert est.n_jobs == 2
        assert len(est.feature_importances_) == 2
        assert est.get_params(deep=False)["anchor_col"] == "anchor_log_unit_price"
        assert est.set_params(n_jobs=1) is est
        assert est.n_jobs == 1

        # 決定木単体では外挿不可能な超高額アンカー(800万円/㎡)でも、残差学習なら正確に外挿復元できる！
        X_unseen = pd.DataFrame({
            "anchor_log_unit_price": [np.log1p(800.0), np.log1p(800.0)],
            "is_corner_lot": [0.0, 1.0],
        })
        preds = est.predict(X_unseen)
        assert preds[0] == pytest.approx(np.log1p(800.0), abs=0.04)
        assert preds[1] - preds[0] == pytest.approx(0.12, abs=0.04)

        # numpy 配列入力およびアンカー列欠落 DataFrame フォールバック検証
        preds_np = est.predict(X_unseen.to_numpy())
        assert preds_np[0] == pytest.approx(preds[0], abs=1e-5)

        X_no_anchor = pd.DataFrame({"is_corner_lot": corner})
        est_plain = AnchorResidualEstimator(RandomForestRegressor(n_estimators=10, random_state=42))
        assert est_plain.fit(X_no_anchor, corner * 1.5, sample_weight=None) is est_plain
        plain_pred = est_plain.predict(pd.DataFrame({"is_corner_lot": [1.0]}))
        assert plain_pred[0] == pytest.approx(1.5, abs=0.2)

        class _CatStub:
            def fit(self, X, y):
                return self

            def predict(self, X):
                return np.ones(len(X))

            def get_feature_importance(self):
                return [0.7, 0.3]

        cat_wrap = AnchorResidualEstimator(_CatStub())
        cat_wrap.fit(X, y)
        assert cat_wrap.get_feature_importance() == [0.7, 0.3]
        # アンカー列がない推論入力時は raw_pred にフォールバックする
        assert cat_wrap.predict(pd.DataFrame({"other": [1.0]}))[0] == pytest.approx(1.0)

    def test_anchor_ratio_cleansing_protects_prime_tokyo_and_removes_anomalies(self):
        """基準地価比クレンジングが都心高額物件を保護しつつ、地方の桁ミス異常値や共有持分売買を正確に除外する"""
        rows = []
        for i in range(25):
            rows.append({
                "price": 3000.0 + i * 50,
                "area": 100.0,
                "tochi_menseki": 100.0,
                "chikunen": 0.0,
                "prefecture": "埼玉県",
                "city": f"さいたま市_{i}",
                "micro_land_price": 300000.0,
                "average_land_price": 300000.0,
                "is_special_sale_share": 0.0,
            })
        # 正当な港区超高額宅地（坪1000万＝300万円/㎡ × 150㎡ ＝ 4.5億円＝45,000万円、基準地価も280万円/㎡）
        rows.append({
            "price": 45000.0,
            "area": 150.0,
            "tochi_menseki": 150.0,
            "chikunen": 0.0,
            "prefecture": "東京都",
            "city": "港区赤坂",
            "micro_land_price": 2800000.0,
            "average_land_price": 2800000.0,
            "is_special_sale_share": 0.0,
        })
        # 地方の入力桁ミス異常値（基準地価 2万円/㎡＝総額200万円相当なのに 40,000万円で登録）
        rows.append({
            "price": 40000.0,
            "area": 100.0,
            "tochi_menseki": 100.0,
            "chikunen": 0.0,
            "prefecture": "茨城県",
            "city": "桁ミス町",
            "micro_land_price": 20000.0,
            "average_land_price": 20000.0,
            "is_special_sale_share": 0.0,
        })
        # 共有持分のみ売買（相場3000万エリアで持分のみ300万円）
        rows.append({
            "price": 300.0,
            "area": 100.0,
            "tochi_menseki": 100.0,
            "chikunen": 0.0,
            "prefecture": "東京都",
            "city": "持分区",
            "micro_land_price": 300000.0,
            "average_land_price": 300000.0,
            "is_special_sale_share": 1.0,
        })

        cleaned = clean_training_data(pd.DataFrame(rows), "tochi")
        cities = set(cleaned["city"].tolist())
        assert "港区赤坂" in cities
        assert "桁ミス町" not in cities
        assert "持分区" not in cities

    def test_end_to_end_training_encoder_persistence_and_inference(self, tmp_path):
        """学習〜location_encoders.joblib保存〜ModelRegistryロード〜bulk_predict推論の一貫結合検証"""
        props = []
        records = []
        for i in range(30):
            is_high = i >= 15
            chome = "東京都世田谷区成城6" if is_high else "千葉県八街市八街1"
            pref = "東京都" if is_high else "千葉県"
            city = "世田谷区" if is_high else "八街市"
            base_lp = 850000 if is_high else 40000
            area = 100.0 + (i % 5) * 10.0
            unit_man = (92.0 if is_high else 4.2) * (1.08 if i % 2 == 0 else 1.0)
            p = _DummyProp(
                tochiMenseki=area,
                maguchi=8.0,
                roadWidth=6.0 if i % 2 == 0 else 4.2,
                roadStructure="角地" if i % 2 == 0 else "中間地",
                address1=pref,
                address2=city,
                address=f"{chome}-{i + 1}",
                station1="成城学園前" if is_high else "八街",
                railwayWalkMinute1=6 if is_high else 20,
            )
            props.append(p)
            f = build_features(p, "tochi")
            f["micro_land_price"] = float(base_lp)
            f["average_land_price"] = float(base_lp)
            f["price"] = round(area * unit_man, 1)
            f["building_group"] = f"grp_{i}"
            records.append(f)

        df = pd.DataFrame(records)
        cols = FEATURE_SETS["tochi"]["first"]
        ens = train_and_compare(df, cols, "tochi - First Stage")
        assert ens.location_encoder is not None

        model_dir = str(tmp_path)
        save_stage_models(ens, model_dir, "tochi", "first")
        save_metadata(
            model_dir,
            {"tochi": {"first": ens.weights}},
            {"tochi": {"first": ens.smearing_factor}},
            mkt_master={},
            location_encoders={"tochi": {"first": ens.location_encoder}},
        )

        reg = ModelRegistry(model_dir=model_dir)
        preds = bulk_predict(props[:2] + props[15:17], stage="first", registry=reg)
        assert len(preds) == 4
        # 高価格エリア(idx 2,3)は低価格エリア(idx 0,1)より大幅に高い予測価格となること
        assert preds[2] > preds[0] * 5
        assert preds[3] > preds[1] * 5

        from package.ml.inference.predictor import predict_both_stages

        save_stage_models(ens, model_dir, "tochi", "second")
        save_metadata(
            model_dir,
            {"tochi": {"first": ens.weights, "second": ens.weights}},
            {"tochi": {"first": ens.smearing_factor, "second": ens.smearing_factor}},
            mkt_master={},
            location_encoders={"tochi": {"first": ens.location_encoder, "second": ens.location_encoder}},
        )
        reg_both = ModelRegistry(model_dir=model_dir)
        both_preds = predict_both_stages(props[:2] + props[15:17], registry=reg_both)
        assert len(both_preds) == 4
        assert both_preds[2][0] > both_preds[0][0] * 5
        assert both_preds[2][1] > both_preds[0][1] * 5

    def test_dcf_valuation_first_import_order_has_no_circular_import(self):
        """main.py 起動順（dcf_valuation ➔ features ➔ land_valuation_extras）で循環インポートが起きないことを検証"""
        import subprocess
        import sys
        from pathlib import Path

        crawler_dir = str(Path(__file__).resolve().parents[2])
        res = subprocess.run(
            [
                sys.executable,
                "-c",
                "import setup_env; import package.ml.dcf_valuation; import package.ml.features; import main",
            ],
            cwd=crawler_dir,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        assert res.returncode == 0, f"Circular import detected:\n{res.stderr}\n{res.stdout}"

    def test_migration_0071_applies_forwards_idempotently_and_backwards(self):
        """0071 マイグレーションが空の ProjectState 上でも LookupError を起こさず冪等に forward/backward 適用できること"""
        import importlib
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from django.db.migrations.state import ProjectState

        mig_mod = importlib.import_module("package.migrations.0071_add_land_price_point_potential")
        mig = mig_mod.Migration("0071_add_land_price_point_potential", "package")

        existing: set[str] = set()
        editor = MagicMock()
        editor.atomic_migration = True
        editor.connection.introspection.get_table_list.side_effect = (
            lambda _cur: [SimpleNamespace(name=t) for t in existing]
        )
        editor.create_model.side_effect = lambda m: existing.add(m._meta.db_table)
        editor.delete_model.side_effect = lambda m: existing.discard(m._meta.db_table)

        after_state = mig.apply(ProjectState(), editor)
        assert "land_price_point_potential" in existing
        assert editor.create_model.call_count == 1

        # 既にテーブルが存在する状態で再実行しても create_model が重複呼出しされないこと
        mig_mod.create_land_price_point_table_if_not_exists(after_state.apps, editor)
        assert editor.create_model.call_count == 1

        # ロールバックで delete_model が呼ばれること
        mig.unapply(after_state, editor)
        assert "land_price_point_potential" not in existing
        assert editor.delete_model.call_count == 1

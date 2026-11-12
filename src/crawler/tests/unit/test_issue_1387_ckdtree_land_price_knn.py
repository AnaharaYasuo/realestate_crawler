# -*- coding: utf-8 -*-
"""Issue #1387: LandPricePoint 単位球面 cKDTree による大圏距離完全一致・高速空間検索テスト."""

import random
import time

from package.ml.features.reference_data import (
    _aggregate_weighted_points,
    _calculate_commercial_weight,
    _chord_to_km,
    _haversine_km,
    _knn_interpolate_points,
    _latlon_to_unit_vec,
    query_micro_land_price_features,
    reset_reference_caches,
    resolve_zone_limits,
    set_land_price_point_cache_for_test,
)
from package.ml.features.reference_records import LandPricePointRecord


def _build_tokyo_points(count: int = 3800) -> list[LandPricePointRecord]:
    rng = random.Random(1387)
    zones = ["第一種低層住居専用地域", "第一種中高層住居専用地域", "近隣商業地域", "商業地域", ""]
    points: list[LandPricePointRecord] = []
    for idx in range(count):
        lat = 35.53 + rng.random() * 0.32
        lon = 139.55 + rng.random() * 0.35
        points.append(
            LandPricePointRecord(
                prefecture="東京都",
                city="世田谷区" if idx % 2 == 0 else "港区",
                chome_key=f"東京都_世田谷区_三軒茶屋{(idx % 5) + 1}",
                latitude=lat,
                longitude=lon,
                land_price=450_000 + (idx % 90) * 15_000,
                growth_rate=3.5,
                land_use="commercial" if idx % 4 == 0 else "residential",
                road_width=6.0,
                station_name="三軒茶屋",
                station_distance_m=450,
                has_gas=True,
                has_water=True,
                has_sewer=(idx % 3 != 0),
                zone_name=zones[idx % len(zones)],
            )
        )
    return points


def test_unit_sphere_chord_matches_haversine_and_linear_knn():
    """単位球面弦長変換が Haversine 大圏距離および線形 k-NN IDW 出力と完全一致し、高速に動作すること."""
    pts = _build_tokyo_points(3800)
    try:
        set_land_price_point_cache_for_test(pts)

        u1 = _latlon_to_unit_vec(35.6580, 139.7016)
        u2 = _latlon_to_unit_vec(35.6895, 139.6917)
        chord = ((u1[0] - u2[0]) ** 2 + (u1[1] - u2[1]) ** 2 + (u1[2] - u2[2]) ** 2) ** 0.5
        assert abs(_chord_to_km(chord) - _haversine_km(35.6580, 139.7016, 35.6895, 139.6917)) < 1e-11

        queries = [
            (35.6436, 139.6713, 200.0, 500_000),
            (35.6812, 139.7671, 400.0, 900_000),
            (35.5900, 139.6200, 150.0, 420_000),
            (43.0621, 141.3544, 200.0, 180_000),  # 15km圏外フォールバック確認
        ]
        for lat, lon, max_youseki, fallback_price in queries:
            comm_w = _calculate_commercial_weight(max_youseki)
            linear_w = _knn_interpolate_points(pts, lat, lon, comm_w)
            if linear_w:
                expected = _aggregate_weighted_points(linear_w, fallback_price)
            else:
                expected = query_micro_land_price_features(
                    "北海道", "札幌市中央区", "北海道_札幌市中央区_大通西1", max_youseki, fallback_price
                )
                actual_far = query_micro_land_price_features(
                    "北海道",
                    "札幌市中央区",
                    "北海道_札幌市中央区_大通西1",
                    max_youseki,
                    fallback_price,
                    latitude=lat,
                    longitude=lon,
                )
                assert actual_far == expected
                continue

            actual = query_micro_land_price_features(
                "東京都",
                "世田谷区",
                "東京都_世田谷区_太子堂1",
                max_youseki,
                fallback_price,
                latitude=lat,
                longitude=lon,
            )
            assert actual == expected

        # 200クエリ × 3,800点のスループット検証 (線形では約4〜6秒かかる処理が 0.25秒未満)
        t0 = time.perf_counter()
        for i in range(200):
            query_micro_land_price_features(
                "東京都",
                "世田谷区",
                "東京都_世田谷区_三軒茶屋1",
                200.0,
                500_000,
                latitude=35.60 + (i % 50) * 0.004,
                longitude=139.60 + (i % 50) * 0.004,
            )
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.25, f"Expected cKDTree 200 queries < 0.25s, got {elapsed:.3f}s"
    finally:
        reset_reference_caches()


def test_gis_zone_imputation_skips_unzoned_nearest_point():
    """最寄標準地の zone_name が空でも、800m以内の次に近い標準地から用途地域が補完されること."""
    pts = [
        LandPricePointRecord(
            prefecture="東京都",
            city="目黒区",
            chome_key="東京都_目黒区_自由が丘1",
            latitude=35.6075,
            longitude=139.6688,
            land_price=1_200_000,
            growth_rate=4.2,
            land_use="commercial",
            road_width=8.0,
            station_name="自由が丘",
            station_distance_m=120,
            has_gas=True,
            has_water=True,
            has_sewer=True,
            zone_name="",  # 最寄だが用途地域未設定
        ),
        LandPricePointRecord(
            prefecture="東京都",
            city="目黒区",
            chome_key="東京都_目黒区_自由が丘2",
            latitude=35.6085,
            longitude=139.6695,
            land_price=980_000,
            growth_rate=3.8,
            land_use="commercial",
            road_width=6.0,
            station_name="自由が丘",
            station_distance_m=220,
            has_gas=True,
            has_water=True,
            has_sewer=True,
            zone_name="近隣商業地域",
        ),
    ]
    try:
        set_land_price_point_cache_for_test(pts)
        _, _, _, _, resolved_zone = resolve_zone_limits(
            {},
            prefecture="東京都",
            city="目黒区",
            chome_group="東京都_目黒区_緑が丘1",
            latitude=35.6076,
            longitude=139.6689,
        )
        assert resolved_zone == "近隣商業地域"
    finally:
        reset_reference_caches()

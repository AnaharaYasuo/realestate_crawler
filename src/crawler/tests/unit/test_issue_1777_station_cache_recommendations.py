# -*- coding: utf-8 -*-
"""Issue #1777: 駅乗降客数キャッシュ初期化保証・複数路線最大値集約・表記ゆれ正規化テスト"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from package.ml.features import reference_data as rd
from scripts.ops import send_recommendations as sr


def _make_fake_station_cls(rows: list[dict]):
    cls = MagicMock()
    cls.objects.values.return_value = rows
    return cls


def test_load_stations_keeps_max_passenger_volume_across_multiple_lines():
    """同一駅名で複数路線（副路線0人等）がある場合、後勝ち上書きではなく最大値を保持すること"""
    rd.reset_reference_caches()
    fake_cls = _make_fake_station_cls([
        {"station_name": "渋谷", "passenger_volume": 650000},
        {"station_name": "渋谷", "passenger_volume": 828303},
        {"station_name": "渋谷", "passenger_volume": 0},
        {"station_name": "品川", "passenger_volume": 425004},
        {"station_name": "品川", "passenger_volume": 0},
        {"station_name": "早稲田", "passenger_volume": 58991},
        {"station_name": "早稲田", "passenger_volume": 3179},
    ])
    loaded = rd._load_stations(fake_cls)
    assert loaded is True
    assert rd.query_station_volume("渋谷") == 828303
    assert rd.query_station_volume("品川") == 425004
    assert rd.query_station_volume("早稲田") == 58991
    rd.reset_reference_caches()


def test_query_station_volume_auto_initializes_station_cache_when_empty():
    """_station_cache が空の状態でも query_station_volume が自動でキャッシュを初期化して値を返すこと"""
    rd.reset_reference_caches()
    fake_cls = _make_fake_station_cls([
        {"station_name": "渋谷", "passenger_volume": 650000},
    ])
    with patch("package.models.evaluation.StationPotential", fake_cls):
        vol = rd.query_station_volume("渋谷駅")
    assert vol == 650000
    rd.reset_reference_caches()


def test_query_station_volume_normalizes_station_name_variants():
    """全角英数・カギ括弧・路線名中黒・小書きカタカナ揺れを正規化して検索できること"""
    rd.reset_reference_caches()
    fake_cls = _make_fake_station_cls([
        {"station_name": "原宿", "passenger_volume": 92910},
        {"station_name": "羽村", "passenger_volume": 21510},
        {"station_name": "JR長瀬", "passenger_volume": 5552},
        {"station_name": "三ツ沢上町", "passenger_volume": 12584},
        {"station_name": "三好ヶ丘", "passenger_volume": 6996},
        {"station_name": "天神橋筋六丁目", "passenger_volume": 45000},
    ])
    rd._load_stations(fake_cls)

    assert rd.query_station_volume("山手線・原宿") == 92910
    assert rd.query_station_volume("「羽村」駅") == 21510
    assert rd.query_station_volume("JR青梅線「羽村」駅") == 21510
    assert rd.query_station_volume("ＪＲ長瀬") == 5552
    assert rd.query_station_volume("三ッ沢上町") == 12584
    assert rd.query_station_volume("三好ケ丘") == 6996
    assert rd.query_station_volume("谷町線・天神橋筋六丁目") == 45000
    assert rd.query_station_volume(" 羽村駅 ") == 21510
    rd.reset_reference_caches()


def test_is_depopulated_station_area_passes_major_station_from_cold_cache():
    """キャッシュ未初期化のコールドスタート状態でも主要駅物件が誤除外されないこと"""
    rd.reset_reference_caches()
    fake_cls = _make_fake_station_cls([
        {"station_name": "渋谷", "passenger_volume": 650000},
        {"station_name": "渋谷", "passenger_volume": 0},
    ])
    prop = SimpleNamespace(
        pageUrl="https://example.com/shibuya",
        price=50000000,
        station1="渋谷",
        railwayWalkMinute1=5,
    )
    with patch("package.models.evaluation.StationPotential", fake_cls):
        assert sr.is_depopulated_station_area(prop) is False
    rd.reset_reference_caches()


def test_send_recommendations_ensures_station_cache_before_screening():
    """send_recommendations 実行時に駅乗降客数キャッシュ初期化が呼び出されること"""
    with (
        patch.object(sr, "close_old_connections"),
        patch.object(sr, "connections"),
        patch.object(sr, "bound_mysql_timeouts"),
        patch.object(sr, "_notify_status"),
        patch.object(sr, "ensure_station_cache") as mock_ensure_cache,
        patch.object(sr, "_fetch_recommendation_candidates", return_value=[]),
        patch.object(sr, "batch_resolve_properties", return_value={}),
    ):
        sr.send_recommendations()
        mock_ensure_cache.assert_called_once()

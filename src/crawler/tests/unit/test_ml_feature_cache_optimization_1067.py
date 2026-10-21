import pytest
from unittest.mock import patch, MagicMock
from package.ml.features.reference_data import _init_global_caches, reset_reference_caches
from package.ml.features.building import prefetch_building_masters, resolve_building_master_obj
from package.ml.features.builder import build_features_batch


def test_init_global_caches_skips_when_initialized():
    """空テーブル時でも初期化試行済みであれば再度のDBクエリをスキップすることを検証 (Issue #1067)"""
    reset_reference_caches()
    
    with patch("package.ml.features.reference_data._init_muni_cache") as mock_muni, \
         patch("package.ml.features.reference_data._init_lp_cache") as mock_lp, \
         patch("package.ml.features.reference_data._init_misc_caches") as mock_misc:
        
        mock_muni.return_value = False
        mock_lp.return_value = False
        mock_misc.return_value = False
        
        # 1回目の呼び出し: DBクエリが実行される
        _init_global_caches()
        assert mock_muni.call_count == 1
        assert mock_lp.call_count == 1
        assert mock_misc.call_count == 1
        
        # 2回目の呼び出し: キャッシュフラグによりDBクエリがスキップされる
        _init_global_caches()
        assert mock_muni.call_count == 1
        assert mock_lp.call_count == 1
        assert mock_misc.call_count == 1


def test_prefetch_building_masters_caches_not_found_keys():
    """建物マスタに存在しないキーについても lookup に None を登録して個別クエリを防ぐことを検証 (Issue #1067)"""
    mock_prop1 = MagicMock()
    mock_prop1.building_master = None
    mock_prop1.propertyName = "テストマンションA"
    mock_prop1.address = "東京都千代田区1-1"

    with patch("package.models.building_master.BuildingMaster.objects.filter") as mock_filter:
        mock_filter.return_value = []
        lookup = prefetch_building_masters([mock_prop1])
        assert isinstance(lookup, dict)
        assert len(lookup) == 1
        key = list(lookup.keys())[0]
        assert lookup[key] is None
        
        # resolve_building_master_obj に渡した際、個別のDB検索が一切走らないこと
        with patch("package.models.building_master.BuildingMaster.objects.filter") as mock_single_filter:
            res = resolve_building_master_obj(mock_prop1, bm_lookup=lookup)
            assert res is None
            assert mock_single_filter.call_count == 0

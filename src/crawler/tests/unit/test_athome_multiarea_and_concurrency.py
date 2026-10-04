# -*- coding: utf-8 -*-
"""
Issue #635: athome の対応エリア拡大（東京・埼玉・神奈川・千葉・愛知）と
詳細並行度引き上げ（1 -> 3）の回帰テスト。
"""
from routes import athome_routes
from package.api import athome


def test_athome_detail_parallel_limit_is_three():
    assert athome.DETAIL_PARARELL_LIMIT == 3
    assert athome.ParseAthomeMansionDetailFuncAsync()._getLocalPararellLimit() == 3
    assert athome.ParseAthomeMansionDetailFuncAsync()._getCloudPararellLimit() == 3
    assert athome.ParseAthomeKodateDetailFuncAsync()._getLocalPararellLimit() == 3
    assert athome.ParseAthomeInvestApartmentDetailFuncAsync()._getLocalPararellLimit() == 3
    assert athome.ParseAthomeTochiDetailFuncAsync()._getLocalPararellLimit() == 3


def test_athome_routes_target_areas():
    expected_areas = ["tokyo", "saitama", "kanagawa", "chiba", "aichi"]
    assert hasattr(athome_routes, "ATHOME_TARGET_AREAS")
    assert athome_routes.ATHOME_TARGET_AREAS == expected_areas

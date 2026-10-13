import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import realestateSettings
realestateSettings.configure()

from package.models.mitsui import MitsuiKodate
from scripts.maintenance.restore_missing_traffic_data import synthesize_traffic_str


def test_synthesize_traffic_str():
    """駅・路線・徒歩分数から正しい交通文字列が合成されること"""
    item = MitsuiKodate()
    item.railway1 = "JR山手線"
    item.station1 = "渋谷駅"
    item.railwayWalkMinute1 = 8

    res = synthesize_traffic_str(item)
    assert res == "JR山手線 渋谷駅 徒歩8分"

    item.busStation1 = "渋谷西口"
    item.busWalkMinute1 = 3
    res2 = synthesize_traffic_str(item)
    assert "JR山手線 渋谷駅 徒歩8分" in res2
    assert "バス停 渋谷西口 徒歩3分" in res2

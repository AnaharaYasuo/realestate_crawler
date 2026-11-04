# -*- coding: utf-8 -*-
"""交通テキストからの徒歩/バス分数取りこぼし防止テスト (Daikyo / Keio / Mizuho)."""
import pytest
from bs4 import BeautifulSoup

from package.parser.daikyoParser import DaikyoKodateParser, DaikyoMansionParser
from package.parser.keioParser import KeioKodateParser
from package.parser.mizuhoParser import MizuhoKodateParser


def test_keio_traffic_lines_split_after_walk_minutes():
    # <br> が get_text() で消え連結された実データ形式
    raw = "多摩モノレール 万願寺駅 徒歩12分多摩モノレール 甲州街道駅 徒歩14分"
    lines = KeioKodateParser._parseTrafficLines(raw)
    assert lines == ["多摩モノレール 万願寺駅 徒歩12分", "多摩モノレール 甲州街道駅 徒歩14分"]


def test_keio_detail_page_keeps_full_traffic():
    html = """<table class="spec_table_default"><tr><th>交通</th>
    <td class="kokoku-detail-data__access"><a>京王線</a> <a>調布駅</a> 徒歩9分<br/>
    <a>京王相模原線</a> <a>京王多摩川駅</a> 徒歩15分</td></tr></table>"""
    p = KeioKodateParser()
    item = p.createEntity()
    item = p._parsePropertyDetailPage(item, BeautifulSoup(html, "lxml"))
    assert "徒歩9分" in item.traffic
    assert "徒歩15分" in item.traffic
    assert item.railwayWalkMinute1 == 9


def test_mizuho_traffic_lines_split_concatenated_routes():
    html = """<table><tr><th>交通</th><td>ＪＲ京浜東北・根岸線 『大宮』駅 バス20分 バス停『南中野』 徒歩9分湘南新宿ライン宇須 『大宮』駅 徒歩30分</td></tr></table>"""
    p = MizuhoKodateParser()
    lines = p._parseTrafficLines(BeautifulSoup(html, "lxml"))
    assert len(lines) == 2
    assert lines[0].endswith("徒歩9分")
    assert lines[1].startswith("湘南新宿ライン宇須")


@pytest.mark.parametrize("cls", [DaikyoMansionParser, DaikyoKodateParser])
def test_daikyo_bus_stop_walk_minutes(cls):
    p = cls()
    item = p.createEntity()
    item.traffic = "工業高校前バス停４分"
    item.station1 = "工業高校前バス停"
    p._parseBusStopWalk(item, item.traffic)
    assert item.busStation1 == "工業高校前"
    assert item.busWalkMinute1 == 4
    assert item.busUse1 == 1
    assert item.station1 == ""


def test_daikyo_car_distance_has_no_walk():
    p = DaikyoKodateParser()
    item = p.createEntity()
    p._parseBusStopWalk(item, "内房線 「大貫」駅 より車5.5km")
    assert item.busWalkMinute1 is None

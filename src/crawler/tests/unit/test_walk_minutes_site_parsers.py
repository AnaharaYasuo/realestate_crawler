# -*- coding: utf-8 -*-
"""交通テキストからの徒歩/バス分数取りこぼし防止テスト (Daikyo / Keio / Mizuho)."""
import pytest
from bs4 import BeautifulSoup

from package.parser.daikyoParser import DaikyoKodateParser, DaikyoMansionParser
from package.parser.keioParser import KeioKodateParser
from package.parser.mizuhoParser import MizuhoKodateParser
from package.parser.odakyuParser import OdakyuKodateParser, OdakyuMansionParser
from scripts.ops.send_recommendations import _format_single_access, is_bus_access_property


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


def test_odakyu_bus_traffic_is_not_parsed_as_station_walk_minutes():
    """Issue #1336: 小田急不動産 W01417-002041 のバス9分・停歩7分が徒歩9分と誤判定されないこと"""
    html = """
    <html><body>
      <h1>海老名市大谷南三丁目</h1>
      <dl>
        <dt>価格</dt><dd>3,480万円</dd>
        <dt>所在地</dt><dd>海老名市大谷南３丁目</dd>
        <dt>交通</dt><dd><a href="/line">小田急線</a>「<a href="/st">海老名</a>」駅バス9分 国分寺台第８ 停歩7分</dd>
      </dl>
      <dl class="outline-table">
        <dt class="outline-table-head">交通</dt>
        <dd class="outline-table-body">
          <a href="/line1">小田急線</a>「<a href="/st1">海老名</a>」駅バス9分 国分寺台第８ 停歩7分<br/>
          <a href="/line2">相鉄線</a>「<a href="/st2">海老名</a>」駅バス9分 国分寺台第８ 停歩7分
        </dd>
      </dl>
    </body></html>
    """
    p = OdakyuKodateParser()
    item = p.createEntity()
    item = p._parsePropertyDetailPage(item, BeautifulSoup(html, "html.parser"))

    assert item.railway1 == "小田急線"
    assert item.station1 == "海老名"
    assert item.busUse1 == 1
    assert item.busWalkMinute1 == 9
    assert item.busWalkMinute1Str == "9"
    assert item.busStation1 == "国分寺台第８"
    assert item.railwayWalkMinute1 == 7
    assert item.railwayWalkMinute1Str == "7"

    assert item.railway2 == "相鉄線"
    assert item.station2 == "海老名"
    assert item.busUse2 == 1
    assert item.busWalkMinute2 == 9
    assert item.busWalkMinute2Str == "9"
    assert item.busStation2 == "国分寺台第８"
    assert item.railwayWalkMinute2 == 7
    assert item.railwayWalkMinute2Str == "7"

    assert is_bus_access_property(item) is True
    assert _format_single_access(item, 1) == "小田急線 海老名 バス9分(停 国分寺台第８) 徒歩7分"


def test_base_parser_populate_traffic_bus_does_not_conflate_bus_and_walk():
    """Issue #1336: ParserBase._populateTraffic 単体でもバスN分を駅徒歩分数に誤設定しないこと"""
    p = OdakyuMansionParser()
    item = p.createEntity()
    p._populateTraffic(item, "小田急線「海老名」駅バス9分 国分寺台第８ 停歩7分")

    assert item.railway1 == "小田急線"
    assert item.station1 == "海老名"
    assert item.busUse1 == 1
    assert item.busWalkMinute1 == 9
    assert item.busStation1 == "国分寺台第８"
    assert item.railwayWalkMinute1 == 7


def test_sumifu_tochi_urawa_bus_traffic_parsing():
    """Issue #1372: 今回問題が発生した住友不動産ステップの浦和駅バス11分・停歩2分のパースおよびSlack表示検証"""
    from package.parser.sumifuParser import SumifuTochiParser
    p = SumifuTochiParser()
    item = p.createEntity()
    traffic_text = "高崎線「浦和」駅バス11 分「稲荷越」バス停徒歩2 分武蔵野線「東浦和」駅バス8 分「広ヶ谷戸」バス停徒歩2 分"
    p._populateTraffic(item, traffic_text)

    assert item.railway1 == "高崎線"
    assert item.station1 == "浦和"
    assert item.busUse1 == 1
    assert item.busWalkMinute1 == 11
    assert item.busWalkMinute1Str == "11"
    assert item.busStation1 == "稲荷越"
    assert item.railwayWalkMinute1 == 2
    assert item.railwayWalkMinute1Str == "2"

    assert is_bus_access_property(item) is True
    assert _format_single_access(item, 1) == "高崎線 浦和 バス11分(停 稲荷越) 徒歩2分"


def test_athome_bracket_bus_traffic_parsing():
    """Issue #1372: アットホーム形式の【バス】10分 停歩10分のパースおよびSlack表示検証"""
    from package.parser.athomeParser import AthomeTochiParser
    p = AthomeTochiParser()
    item = p.createEntity()
    traffic_text = "西武新宿線 / 東村山駅 【バス】10分 廻田町三丁目 停歩10分"
    p._populateTraffic(item, traffic_text)

    assert item.railway1 == "西武新宿線"
    assert item.station1 == "東村山"
    assert item.busUse1 == 1
    assert item.busWalkMinute1 == 10
    assert item.busStation1 == "廻田町三丁目"
    assert item.railwayWalkMinute1 == 10

    assert is_bus_access_property(item) is True
    assert _format_single_access(item, 1) == "西武新宿線 東村山 バス10分(停 廻田町三丁目) 徒歩10分"



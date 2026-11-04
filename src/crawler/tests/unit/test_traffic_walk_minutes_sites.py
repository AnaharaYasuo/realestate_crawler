# -*- coding: utf-8 -*-
"""
交通 (traffic) 全文保持 ＆ 徒歩/バス分抽出の回帰テスト

対象: 三井(rehouse) / 三井住友トラスト(smtrc) / 東急(ttfuhan) / 京急 / 京成
フィクスチャ: 2026-11-04 取得の実詳細ページ生HTML (tests/fixtures/walk_minutes/)
"""
import os

import pytest
from bs4 import BeautifulSoup

from package.parser.keikyuParser import KeikyuKodateParser, KeikyuMansionParser
from package.parser.keiseiParser import KeiseiMansionParser
from package.parser.mitsuiParser import MitsuiMansionParser, MitsuiTochiParser
from package.parser.smtrcParser import SmtrcKodateParser, SmtrcParser
from package.parser.totateParser import TotateMansionParser

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "walk_minutes")


def _parse(parser_cls, fixture):
    with open(os.path.join(FIXTURE_DIR, fixture), encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "lxml")
    parser = parser_cls(None)
    item = parser.createEntity()
    item = parser._parsePropertyDetailPage(item, soup)
    # 本番経路 (parsePropertyDetailPage) と同様に clean_parsed_item まで通す
    item = parser.clean_parsed_item(item)
    return item


@pytest.mark.parametrize(
    "parser_cls, fixture, station, walk",
    [
        (MitsuiMansionParser, "mitsui_m.html", "つくば", 6),
        (MitsuiTochiParser, "mitsui_t.html", "極楽寺", 5),
        (TotateMansionParser, "totate_live.html", "二子玉川", 11),
        (KeikyuMansionParser, "keikyu1.html", None, 2),
        (KeikyuKodateParser, "keikyu2.html", None, 20),
        (KeiseiMansionParser, "keisei1.html", "青砥", 11),
    ],
)
def test_traffic_keeps_walk_minutes(parser_cls, fixture, station, walk):
    item = _parse(parser_cls, fixture)
    assert f"徒歩{walk}分" in item.traffic
    assert item.railwayWalkMinute1 == walk
    if station:
        assert item.station1 == station


def test_keisei_multi_route_traffic_is_line_separated():
    item = _parse(KeiseiMansionParser, "keisei1.html")
    # 旧実装では '徒歩11分京成本線青砥駅' と路線間が連結されていた
    assert "徒歩11分京成本線" not in item.traffic
    assert "お花茶屋駅 徒歩21分" in item.traffic


def test_totate_multi_route_traffic_is_line_separated():
    item = _parse(TotateMansionParser, "totate_live.html")
    assert "徒歩11分東急田園都市線" not in item.traffic
    assert "東急田園都市線" in item.traffic


def test_smtrc_bus_route_fixture():
    item = _parse(SmtrcKodateParser, "smtrc1.html")
    assert "バス乗車12分" in item.traffic and "徒歩3分" in item.traffic
    assert item.busUse1 == 1
    assert item.busWalkMinute1 == 12
    assert item.railwayWalkMinute1 == 3
    assert item.busStation1 == "桜台二丁目"


def test_smtrc_apply_bus_access_snippet():
    parser = SmtrcKodateParser(None)
    item = parser.createEntity()
    SmtrcParser._applyBusAccess1(item, ["京王線 聖蹟桜ヶ丘駅 バス15分 永山停 徒歩5分"])
    assert (item.busUse1, item.busWalkMinute1, item.railwayWalkMinute1) == (1, 15, 5)


def test_smtrc_apply_bus_access_noop_for_walk_only():
    parser = SmtrcKodateParser(None)
    item = parser.createEntity()
    item.railwayWalkMinute1 = 7
    SmtrcParser._applyBusAccess1(item, ["小田急小田原線 鶴川駅 徒歩7分"])
    assert item.railwayWalkMinute1 == 7
    assert not item.busUse1

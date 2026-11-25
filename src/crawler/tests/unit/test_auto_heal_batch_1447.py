from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from package.parser.heimParser import HeimTochiParser


@pytest.mark.parametrize(
    ("traffic_text", "expected_min"),
    [
        ("JR中央線「武蔵境」駅 徒歩24~25分", 24),
        ("西武池袋線「東久留米」駅 徒歩19～20分", 19),
        ("東急田園都市線「たまプラーザ」駅 徒歩8-10分", 8),
        ("JR山手線「目黒」駅 徒歩7分", 7),
    ],
)
def test_heim_supplement_traffic_field_supports_range_walk_minutes(traffic_text, expected_min):
    item = SimpleNamespace(
        traffic=traffic_text,
        railwayWalkMinute1=None,
        railwayWalkMinute1Str="",
    )
    HeimTochiParser._supplement_traffic_field(item, {})
    assert item.railwayWalkMinute1 == expected_min
    assert item.railwayWalkMinute1Str == str(expected_min)


def test_heim_apply_outline_specs_supplements_ratios_and_address():
    html = """
    <html><body>
      <dl>
        <dt>所在地</dt><dd>東京都三鷹市深大寺２丁目3801-38他</dd>
        <dt>建ぺい率</dt><dd>40%</dd>
        <dt>容積率</dt><dd>80%</dd>
        <dt>交通</dt><dd>JR中央線「武蔵境」駅 徒歩24~25分</dd>
      </dl>
    </body></html>
    """
    item = SimpleNamespace(
        address="スマートハイムシティ三鷹市深大寺II",
        address1="",
        kenpei=None,
        kenpeiStr="",
        youseki=None,
        yousekiStr="",
        traffic="",
        railwayWalkMinute1=None,
        railwayWalkMinute1Str="",
        kenchikuJoken="",
        chimoku="",
        youtoChiiki="",
        setsudou="",
    )
    parser = HeimTochiParser()
    parser._apply_outline_specs(item, BeautifulSoup(html, "html.parser"))
    assert item.kenpei == 40
    assert item.youseki == 80
    assert item.railwayWalkMinute1 == 24
    assert item.address == "東京都三鷹市深大寺２丁目3801-38他"
    assert item.address1 == "東京都"

from types import SimpleNamespace

import pytest

from package.parser.athomeParser import AthomeParser


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("西武池袋線/東久留米駅 徒歩19～20分", 19),
        ("西武池袋線/清瀬駅 徒歩24~25分", 24),
        ("JR中央線/国分寺駅 徒歩8-10分", 8),
        ("JR東海道線/横浜駅 徒歩1500～1600m", 19),
        ("東急東横線/自由が丘駅 徒歩7分", 7),
    ],
)
def test_athome_extract_walk_minutes_supports_range_format(text, expected):
    assert AthomeParser._extract_walk_minutes(text) == expected


def test_athome_apply_access_minutes_extracts_range_walk_and_bus():
    item = SimpleNamespace(
        railway1="",
        station1="",
        railwayWalkMinute1=None,
        railwayWalkMinute1Str="",
        busWalkMinute1=None,
        busWalkMinute1Str="",
        busUse1=0,
        busStation1="",
    )
    AthomeParser._apply_athome_access_minutes(
        item,
        "西武池袋線/東久留米駅 徒歩19～20分\nJR中央線/三鷹駅 バス10～12分",
    )
    assert item.railwayWalkMinute1 == 19
    assert item.railwayWalkMinute1Str == "19分"

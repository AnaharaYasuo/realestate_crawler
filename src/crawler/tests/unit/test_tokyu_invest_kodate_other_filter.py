import pytest
from package.parser.tokyuParser import TokyuInvestmentKodateParser


@pytest.fixture
def parser():
    return TokyuInvestmentKodateParser()


def test_filter_excludes_non_kodate_labels(parser):
    # ホテル、旅館、車庫、ビル一棟、マンション一棟売など
    test_cases = [
        {"detailUrl": "/fudosan-toushi/H001/", "labelList": [{"listText": "ホテル"}], "propertyDetail": []},
        {"detailUrl": "/fudosan-toushi/H002/", "labelList": [{"listText": "旅館"}], "propertyDetail": []},
        {"detailUrl": "/fudosan-toushi/H003/", "labelList": [{"listText": "ビル一棟"}], "propertyDetail": []},
        {"detailUrl": "/fudosan-toushi/H004/", "labelList": [{"listText": "マンション一棟売"}], "propertyDetail": []},
        {"detailUrl": "/fudosan-toushi/H005/", "labelList": [{"listText": "車庫・立体駐車場"}], "propertyDetail": []},
        {"detailUrl": "/fudosan-toushi/H006/", "labelList": [{"listText": "店舗/その他(土地・建物)"}], "propertyDetail": []},
        {"detailUrl": "/fudosan-toushi/H007/", "labelList": [{"listText": "事務所/倉庫"}], "propertyDetail": []},
        {"detailUrl": "/fudosan-toushi/H008/", "labelList": [{"listText": "リゾートマンション・別荘"}], "propertyDetail": []},
    ]
    for case in test_cases:
        res = parser._parse_nextjs_property_item(case)
        assert res is None, f"Expected {case} to be excluded"


def test_filter_excludes_multi_units(parser):
    # その他(土地・建物) だが、2戸以上の複数戸物件
    item = {
        "detailUrl": "/fudosan-toushi/M001/",
        "labelList": [{"listText": "その他(土地・建物)"}],
        "propertyDetail": ["建物 159.66m2", "土地 303.01m2", "6戸", "2000年12月築", "軽量鉄骨 2階 地上2階建"]
    }
    assert parser._parse_nextjs_property_item(item) is None

    item_14units = {
        "detailUrl": "/fudosan-toushi/M002/",
        "labelList": [{"listText": "その他(土地・建物)"}],
        "propertyDetail": ["建物 142.85m2", "土地 151.88m2", "14戸", "2015年11月築", "木造 2階 地上2階建"]
    }
    assert parser._parse_nextjs_property_item(item_14units) is None


def test_filter_excludes_high_floor_buildings(parser):
    # その他(土地・建物) だが、4階建以上のビル構造
    item = {
        "detailUrl": "/fudosan-toushi/B001/",
        "labelList": [{"listText": "その他(土地・建物)"}],
        "propertyDetail": ["建物 1056.39m2", "土地 354.16m2", "-", "1977年3月築", "鉄骨造 4階 地上4階建"]
    }
    assert parser._parse_nextjs_property_item(item) is None


def test_filter_accepts_valid_kodate(parser):
    # 正当な一戸建て投資物件
    item_single_unit = {
        "detailUrl": "/fudosan-toushi/K001/",
        "price": 19800000,
        "labelList": [{"listText": "その他(土地・建物)"}],
        "propertyDetail": ["建物 45.88m2", "土地 42.46m2", "-", "1972年12月築", "木造 2階 地上2階建"]
    }
    res = parser._parse_nextjs_property_item(item_single_unit)
    assert res is not None
    assert res.url == "https://www.livable.co.jp/fudosan-toushi/K001/"
    assert res.price == 19800000

    item_1unit = {
        "detailUrl": "/fudosan-toushi/K002/",
        "price": 25000000,
        "labelList": [{"listText": "その他(土地・建物)"}, {"listText": "NEW 10/10"}],
        "propertyDetail": ["建物 97.30m2", "土地 67.79m2", "1戸", "2020年7月築", "木造 3階 地上3階建"]
    }
    res2 = parser._parse_nextjs_property_item(item_1unit)
    assert res2 is not None
    assert res2.url == "https://www.livable.co.jp/fudosan-toushi/K002/"
    assert res2.price == 25000000

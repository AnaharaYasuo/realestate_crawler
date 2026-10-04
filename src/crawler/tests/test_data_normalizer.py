import datetime
from decimal import Decimal

from package.utils.normalizer import DataNormalizer


def test_normalize_price():
    assert DataNormalizer.normalize_price("3,980万円") == 39800000
    assert DataNormalizer.normalize_price("1億2,500万円") == 125000000
    assert DataNormalizer.normalize_price("3億円") == 300000000
    assert DataNormalizer.normalize_price("3980万 (税込)") == 39800000
    assert DataNormalizer.normalize_price("5000円") == 5000
    assert DataNormalizer.normalize_price("相談") is None
    assert DataNormalizer.normalize_price("-") is None
    assert DataNormalizer.normalize_price(None) is None


def test_normalize_area():
    # 平米
    res1 = DataNormalizer.normalize_area("70.52㎡")
    assert res1.area_m2 == Decimal("70.52")
    assert res1.area_tsubo == Decimal("21.33")
    assert res1.is_wall_center is False

    # 壁芯付き
    res2 = DataNormalizer.normalize_area("70.52m² (壁芯)")
    assert res2.area_m2 == Decimal("70.52")
    assert res2.is_wall_center is True

    # 内法
    res3 = DataNormalizer.normalize_area("65.00㎡ (内法)")
    assert res3.area_m2 == Decimal("65.00")
    assert res3.is_inner_measurement is True

    # 坪換算
    res4 = DataNormalizer.normalize_area("25.3坪")
    assert res4.area_tsubo == Decimal("25.30")
    # 25.3 * 3.30578 = 83.636234 -> 83.64
    assert res4.area_m2 == Decimal("83.64")

    # 無効値
    assert DataNormalizer.normalize_area("未定") is None
    assert DataNormalizer.normalize_area("-") is None
    assert DataNormalizer.normalize_area(None) is None


def test_normalize_built_date():
    # 西暦
    assert DataNormalizer.normalize_built_date("2015年3月") == datetime.date(2015, 3, 1)
    assert DataNormalizer.normalize_built_date("2015/03") == datetime.date(2015, 3, 1)
    assert DataNormalizer.normalize_built_date("2015-03-01") == datetime.date(2015, 3, 1)
    assert DataNormalizer.normalize_built_date("2015年築") == datetime.date(2015, 1, 1)

    # 元号
    assert DataNormalizer.normalize_built_date("令和3年築") == datetime.date(2021, 1, 1)
    assert DataNormalizer.normalize_built_date("平成27年3月") == datetime.date(2015, 3, 1)
    assert DataNormalizer.normalize_built_date("昭和58年11月") == datetime.date(1983, 11, 1)
    assert DataNormalizer.normalize_built_date("令和元年5月") == datetime.date(2019, 5, 1)

    # 無効値
    assert DataNormalizer.normalize_built_date("不詳") is None
    assert DataNormalizer.normalize_built_date("-") is None
    assert DataNormalizer.normalize_built_date(None) is None


def test_clean_text():
    assert DataNormalizer.clean_text("  １２３　ABC  ") == "123 ABC"
    assert DataNormalizer.clean_text("東京都\r\n港区\t赤坂") == "東京都 港区 赤坂"
    assert DataNormalizer.clean_text(None) == ""

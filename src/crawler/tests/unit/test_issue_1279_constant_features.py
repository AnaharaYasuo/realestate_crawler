import datetime
from package.ml.features.parsers import (
    parse_company_features,
    resolve_company_name,
    resolve_eval_dates_and_diff,
    calculate_chikunen_feature,
    parse_kouzou,
)
from package.ml.features.builder import FEATURE_SETS


def test_resolve_company_name_from_model():
    class DummySumifuMansion:
        company = None
        propertyName = "グランドメゾン白金"

    DummySumifuMansion.__name__ = "SumifuMansion"
    comp = resolve_company_name(DummySumifuMansion())
    assert comp == "sumifu"
    feats = parse_company_features(comp)
    assert feats["company_tier"] == 3.0
    assert feats["is_major_company"] == 1.0


def test_resolve_company_name_from_portal_brand():
    class DummyAthomeProud:
        company = None
        propertyName = "プラウドタワー名古屋錦"
        bunjoKaisya = ""

    DummyAthomeProud.__name__ = "AthomeMansion"
    comp = resolve_company_name(DummyAthomeProud())
    feats = parse_company_features(comp)
    assert feats["company_tier"] == 3.0
    assert feats["is_major_company"] == 1.0


def test_time_diff_months_default_uses_today():
    class DummyProp:
        inputDate = datetime.date.today() - datetime.timedelta(days=91)
        inputDateTime = None

    _, _, diff, _ = resolve_eval_dates_and_diff(DummyProp(), base_date=None)
    # 91 / 30.4375 ≈ 2.99
    assert 2.8 <= diff <= 3.2


def test_chikunen_unknown_feature():
    class DummyKnown:
        chikunengetsu = "2020年01月"
        kouzou = "RC造"

    class DummyUnknown:
        chikunengetsu = None
        chikunengetsuStr = None
        kouzou = "木造"

    eval_date = datetime.date(2024, 1, 1)
    age_known, is_unk_known = calculate_chikunen_feature(DummyKnown(), "mansion", eval_date)
    assert is_unk_known == 0.0
    assert 3.8 <= age_known <= 4.2

    age_unk, is_unk_unk = calculate_chikunen_feature(DummyUnknown(), "kodate", eval_date)
    assert is_unk_unk == 1.0
    assert age_unk == 38.0


def test_parse_kouzou_expanded():
    assert parse_kouzou("S造") == "S"
    assert parse_kouzou("SRC造") == "SRC"
    assert parse_kouzou("PC造") == "RC"
    assert parse_kouzou("軽量鉄骨造") == "LS"
    assert parse_kouzou("コンクリートブロック造") == "S"


def test_feature_sets_chikunen_unknown_and_no_land_leak():
    for ptype in ["mansion", "kodate", "apartment"]:
        assert "is_chikunen_unknown" in FEATURE_SETS[ptype]["first"]
        assert "is_chikunen_unknown" in FEATURE_SETS[ptype]["second"]

    assert "chikunen" not in FEATURE_SETS["tochi"]["first"]
    assert "is_chikunen_unknown" not in FEATURE_SETS["tochi"]["first"]
    assert "max_building_area" not in FEATURE_SETS["mansion"]["first"]
    assert "scale_discount" not in FEATURE_SETS["mansion"]["first"]

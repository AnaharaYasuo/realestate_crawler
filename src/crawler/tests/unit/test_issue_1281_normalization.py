from package.ml.features.parsers import extract_clean_address, parse_kouzou


def test_clean_address_postal_code_removal():
    class DummyProp:
        address1 = "東京都"
        address2 = "〒180-0003 武蔵野市吉祥寺南町"
        address = "〒180-0003 東京都武蔵野市吉祥寺南町1-1"
        station1 = "吉祥寺"

    a1, a2, _st, _comp = extract_clean_address(DummyProp())
    assert a1 == "東京都"
    assert a2 == "武蔵野市"


def test_infer_prefecture_when_address1_is_empty():
    class DummyProp:
        address1 = ""
        address2 = "武蔵野市"
        address = "武蔵野市吉祥寺南町1-1"
        station1 = "吉祥寺"

    a1, a2, _st, _comp = extract_clean_address(DummyProp())
    assert a1 == "東京都"
    assert a2 == "武蔵野市"


def test_infer_prefecture_designated_city_ward():
    class DummyProp:
        address1 = ""
        address2 = "名古屋市中村区"
        address = "名古屋市中村区名駅1-1"
        station1 = "名古屋"

    a1, a2, _st, _comp = extract_clean_address(DummyProp())
    assert a1 == "愛知県"
    assert a2 == "名古屋市中村区"


def test_parse_kouzou_full_normalization():
    # 全角・略称・各種表記揺れのテスト
    assert parse_kouzou("ＲＣ造") == "RC"
    assert parse_kouzou("RC") == "RC"
    assert parse_kouzou("鉄筋コンクリート造") == "RC"
    assert parse_kouzou("鉄骨鉄筋コンクリート造") == "SRC"
    assert parse_kouzou("ＳＲＣ造") == "SRC"
    assert parse_kouzou("SRC") == "SRC"
    assert parse_kouzou("木造 2階建") == "W"
    assert parse_kouzou("Ｗ造") == "W"
    assert parse_kouzou("軽量鉄骨造") == "LS"
    assert parse_kouzou("重量鉄骨造") == "S"
    assert parse_kouzou("Ｓ造") == "S"

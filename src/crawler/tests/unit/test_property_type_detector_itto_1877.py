from package.utils.property_type_detector import PropertyTypeDetector


def test_mansion_name_containing_isolated_itto_detects_mansion():
    title = "大和サニーハイツ高槻一棟 6階3LDK｜高槻市の中古マンション購入【OAL07324】｜大京穴吹不動産"
    detected = PropertyTypeDetector.detect(
        url="https://www.daikyo-anabuki.co.jp/buy/detail/OAL07324/",
        title=title,
        html_text="",
        specs={},
        default="mansion",
    )
    assert detected == "mansion"


def test_explicit_itto_mansion_still_detects_apartment():
    assert (
        PropertyTypeDetector.detect(
            url="https://example.com/detail/1",
            title="一棟マンション 中古マンション投資物件",
            html_text="",
            specs={},
        )
        == "apartment"
    )
    assert (
        PropertyTypeDetector.detect(
            url="https://example.com/detail/2",
            title="一棟売りマンション 高槻市",
            html_text="",
            specs={},
        )
        == "apartment"
    )


def test_isolated_itto_without_explicit_mansion_compound_detects_apartment():
    assert (
        PropertyTypeDetector.detect(
            url="https://example.com/detail/3",
            title="高槻一棟 物件詳細",
            html_text="",
            specs={},
        )
        == "apartment"
    )

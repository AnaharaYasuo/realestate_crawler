from package.utils.property_type_detector import PropertyTypeDetector


def test_toho_mansion_title_with_kodate_branding_suffix_detects_mansion():
    title = (
        "クリオ小平壱番館 （小平市鈴木町１丁目 3190万円 マンション）"
        "｜物件検索｜物件詳細｜国分寺の新築戸建て4LDK超物件不動産なら東宝ハウス国分寺"
    )
    detected = PropertyTypeDetector.detect(
        url="https://www.toho-house.co.jp/sch/detail.php?k_number=83999&div=001",
        title=title,
        html_text="",
        specs={},
        default="mansion",
    )
    assert detected == "mansion"

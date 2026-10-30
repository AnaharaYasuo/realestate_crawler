"""Unit tests for Phase 3: 4-Layer Property-Type Misclassification Defense."""
from bs4 import BeautifulSoup

from package.utils.property_type_detector import PropertyTypeDetector


def test_layer1_extract_clean_body_text_strips_nav_header_sidebar_noise():
    html = """
    <html>
      <head><title>世田谷区 売地</title></head>
      <body>
        <header class="site-header">一棟アパート 表面利回り 12.5% マンション 一戸建て</header>
        <nav class="gnav"><ul><li>マンション</li><li>一棟アパート 利回り10%</li></ul></nav>
        <aside class="sidebar recommend-box">おすすめ収益物件 利回り 9.8% 一棟マンション</aside>
        <main>
          <h1>世田谷区深沢 売土地 120㎡</h1>
          <p>閑静な住宅街の整形地。建築条件なし。</p>
        </main>
        <footer>Copyright 一棟ビル 投資アパート</footer>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    clean_text = PropertyTypeDetector.extract_clean_body_text(soup)
    assert "利回り 12.5%" not in clean_text
    assert "利回り 9.8%" not in clean_text
    assert "世田谷区深沢 売土地" in clean_text

    detected = PropertyTypeDetector.detect(
        url="https://example.com/tochi/detail/123",
        title="世田谷区 売地",
        html_text=clean_text,
        specs={"物件種別": "売地", "土地面積": "120.00㎡"},
    )
    assert detected == "tochi"


def test_layer2_owner_change_sectional_mansion_and_orthogonal_classification():
    specs = {
        "管理費": "12,500円/月",
        "修繕積立金": "9,800円/月",
        "バルコニー面積": "8.40㎡",
        "表面利回り": "5.4%",
        "現況": "賃貸中（オーナーチェンジ）",
    }
    detected = PropertyTypeDetector.detect(
        url="https://example.com/mansion/detail/999",
        title="パークホームズ渋谷 402号室 オーナーチェンジ",
        html_text="表面利回り 5.4% 賃貸中",
        specs=specs,
    )
    assert detected == "mansion"

    ortho = PropertyTypeDetector.detect_physical_and_tenancy(
        url="https://example.com/mansion/detail/999",
        title="パークホームズ渋谷 402号室 オーナーチェンジ",
        specs=specs,
    )
    assert ortho["physical_type"] == "mansion"
    assert ortho["is_tenanted"] is True
    assert ortho["is_non_residential"] is False

    office_ortho = PropertyTypeDetector.detect_physical_and_tenancy(
        url="https://example.com/invest/detail/888",
        title="新橋駅前 商業ビル・オフィスビル一棟",
        specs={"物件種別": "一棟売りビル（事務所・店舗）"},
    )
    assert office_ortho["is_non_residential"] is True


def test_layer3_free_text_remarks_do_not_trigger_spec_misclassification():
    # Land listing with remarks mentioning apartments and mansions nearby
    specs_land = {
        "土地面積": "150.25㎡",
        "建ぺい率": "60%",
        "容積率": "200%",
        "備考": "アパート用地に最適！近隣に大型分譲マンション・一戸建て多数あり。",
        "周辺環境": "〇〇マンションまで徒歩2分、△△一棟アパート隣",
    }
    detected = PropertyTypeDetector.detect(
        url="https://example.com/tochi/detail/555",
        title="練馬区石神井町 土地",
        html_text="練馬区石神井町の整形地です。",
        specs=specs_land,
    )
    assert detected == "tochi"


def test_layer4_post_parse_physical_invariants_gate():
    # 1. Misclassified as 'tochi' when it actually has senyuMenseki and no land area
    fake_land = {"senyuMenseki": 68.5, "tochiMenseki": None, "kaisuStr": "5階"}
    ok, corrected, reason = PropertyTypeDetector.validate_physical_invariants(fake_land, "tochi")
    assert ok is False
    assert corrected == "mansion"
    assert reason

    # 2. Misclassified as 'kodate' when tochiMenseki=0 and RC structure + senyuMenseki
    fake_kodate = {"tochiMenseki": 0, "senyuMenseki": 55.0, "kouzou": "RC造"}
    ok2, corrected2, _ = PropertyTypeDetector.validate_physical_invariants(fake_kodate, "kodate")
    assert ok2 is False
    assert corrected2 == "mansion"

    # 3. Misclassified as 'mansion' when senyuMenseki is None but both tochiMenseki and tatemonoMenseki > 0
    fake_mansion = {"senyuMenseki": None, "tochiMenseki": 110.0, "tatemonoMenseki": 92.5}
    ok3, corrected3, _ = PropertyTypeDetector.validate_physical_invariants(fake_mansion, "mansion")
    assert ok3 is False
    assert corrected3 == "kodate"

    # 4. Valid sectional mansion passes cleanly
    valid_mansion = {"senyuMenseki": 72.3, "tochiMenseki": None, "kanrihi": 15000}
    ok4, corrected4, reason4 = PropertyTypeDetector.validate_physical_invariants(valid_mansion, "mansion")
    assert ok4 is True
    assert corrected4 == "mansion"
    assert reason4 == ""

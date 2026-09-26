# -*- coding: utf-8 -*-
from package.utils.property_type_detector import PropertyTypeDetector


def test_detect_from_title_apartment():
    """タイトルから一棟アパート・一棟マンション・投資用収益物件が正しく判定されること"""
    title1 = "【ホームズ】埼玉県さいたま市の一棟売りアパート (利回り: 6.02％ 価格: 4,120万円) 円阿弥ビル。不動産投資・収益物件を検索するなら【LIFULL HOME'S 不動産投資】"
    assert PropertyTypeDetector.detect(title=title1) == "apartment"

    title2 = "東京都中野区の一棟マンション 満室想定利回り7.2%"
    assert PropertyTypeDetector.detect(title=title2) == "apartment"

    title3 = "横浜市青葉区 収益アパート 10室 表面利回り8.5%"
    assert PropertyTypeDetector.detect(title=title3) == "apartment"

    title4 = "一棟売りビル 商業地域 満室稼働中"
    assert PropertyTypeDetector.detect(title=title4) == "apartment"


def test_detect_precedence_one_building_mansion():
    """『一棟マンション』という語句が『マンション』ではなく『apartment』と優先判定されること"""
    title = "駅徒歩5分 一棟マンション 鉄筋コンクリート造"
    assert PropertyTypeDetector.detect(title=title) == "apartment"


def test_detect_from_title_mansion():
    """タイトルから区分マンション・中古マンションが正しく判定されること"""
    title1 = "パークホームズ桜丘 3LDK 中古マンション"
    assert PropertyTypeDetector.detect(title=title1) == "mansion"

    title2 = "区分マンション 投資用ワンルーム 新宿区"
    assert PropertyTypeDetector.detect(title=title2) == "mansion"

    title3 = "ライオンズマンション吉祥寺 5階部分 南向き"
    assert PropertyTypeDetector.detect(title=title3) == "mansion"


def test_detect_from_title_kodate():
    """タイトルから一戸建て・戸建が正しく判定されること"""
    title1 = "世田谷区桜丘 新築一戸建て 4LDK 駐車2台"
    assert PropertyTypeDetector.detect(title=title1) == "kodate"

    title2 = "田園調布 中古戸建 2階建 庭付き"
    assert PropertyTypeDetector.detect(title=title2) == "kodate"

    title3 = "杉並区 一戸建 南西角地"
    assert PropertyTypeDetector.detect(title=title3) == "kodate"


def test_detect_from_title_tochi():
    """タイトルから土地・売地が正しく判定されること"""
    title1 = "目黒区自由が丘 売地 建築条件なし 50坪"
    assert PropertyTypeDetector.detect(title=title1) == "tochi"

    title2 = "練馬区東大泉 土地 更地渡し 角地"
    assert PropertyTypeDetector.detect(title=title2) == "tochi"

    title3 = "世田谷区 建築条件付土地 好立地"
    assert PropertyTypeDetector.detect(title=title3) == "tochi"


def test_detect_from_specs():
    """スペック辞書から種別が最優先で判定されること"""
    specs_apt = {"物件種別": "一棟売りアパート", "価格": "4,500万円"}
    assert PropertyTypeDetector.detect(specs=specs_apt) == "apartment"

    specs_mansion = {"種別": "区分マンション", "専有面積": "65.0m2"}
    assert PropertyTypeDetector.detect(specs=specs_mansion) == "mansion"

    specs_kodate = {"建物種別": "中古一戸建て"}
    assert PropertyTypeDetector.detect(specs=specs_kodate) == "kodate"

    specs_tochi = {"種別": "売土地", "地目": "宅地"}
    assert PropertyTypeDetector.detect(specs=specs_tochi) == "tochi"


def test_detect_from_url():
    """URLパスパターンから種別が判定されること"""
    assert PropertyTypeDetector.detect(url="https://www.rehouse.co.jp/buy/mansion/bkdetail/123/") == "mansion"
    assert PropertyTypeDetector.detect(url="https://www.rehouse.co.jp/buy/kodate/bkdetail/123/") == "kodate"
    assert PropertyTypeDetector.detect(url="https://www.rehouse.co.jp/buy/tochi/bkdetail/123/") == "tochi"
    assert PropertyTypeDetector.detect(url="https://toushi.homes.co.jp/bukkendetail/index/4721792/") == "apartment"


def test_detect_from_html():
    """HTML本文やパンくずリストから種別が判定されること"""
    html_apt = """
    <html>
        <body>
            <div class="pankuzu"><a href="/">TOP</a> &gt; <span>一棟売りアパート</span></div>
            <h1>さいたま市物件</h1>
        </body>
    </html>
    """
    assert PropertyTypeDetector.detect(html_text=html_apt) == "apartment"

    html_mansion = """
    <html>
        <body>
            <nav class="breadcrumb"><span>中古マンション</span></nav>
        </body>
    </html>
    """
    assert PropertyTypeDetector.detect(html_text=html_mansion) == "mansion"


def test_detect_precedence():
    """specs > title > html > url の優先順位で正しく解決されること"""
    # URLは汎用だがtitleが一棟アパート
    assert PropertyTypeDetector.detect(
        url="https://example.com/property/1001",
        title="埼玉県の一棟売りアパート",
    ) == "apartment"

    # titleは曖昧だがspecsに区分マンション
    assert PropertyTypeDetector.detect(
        url="https://example.com/property/1001",
        title="新宿区の素敵な物件",
        specs={"物件種別": "区分マンション"}
    ) == "mansion"


def test_detect_fallback_and_default():
    """判定不能な場合のフォールバックおよびデフォルト値の返却"""
    assert PropertyTypeDetector.detect() is None
    assert PropertyTypeDetector.detect(default="mansion") == "mansion"
    assert PropertyTypeDetector.detect(title="会社概要・プライバシーポリシー", default="unknown") == "unknown"


def test_detect_from_object_dict():
    """辞書オブジェクトからの種別判定（predict.pyの共通化ロジック検証）"""
    # 1. 専有面積あり -> mansion
    assert PropertyTypeDetector.detect_from_object({"senyuMenseki": 55.0}) == "mansion"

    # 2. 土地面積0のRC構造 -> mansion
    assert PropertyTypeDetector.detect_from_object({
        "tochiMenseki": 0,
        "structure": "鉄筋コンクリート造",
        "propertyType": "kodate"
    }) == "mansion"

    # 3. 建物面積 + 表面利回り -> apartment
    assert PropertyTypeDetector.detect_from_object({
        "tatemonoMenseki": 120.0,
        "grossYield": 7.5
    }) == "apartment"

    # 4. 建物面積のみ -> kodate
    assert PropertyTypeDetector.detect_from_object({
        "tatemonoMenseki": 95.0
    }) == "kodate"

    # 5. 土地面積または間口 -> tochi
    assert PropertyTypeDetector.detect_from_object({
        "tochiMenseki": 80.0
    }) == "tochi"
    assert PropertyTypeDetector.detect_from_object({
        "maguchi": 6.5
    }) == "tochi"


def test_detect_from_object_django_model():
    """Djangoモデルクラスインスタンスからの種別判定"""
    class MockSumifuMansion:
        pass

    class MockMitsuiKodate:
        pass

    class MockTokyuTochi:
        pass

    class MockNomuraInvestment:
        pass

    assert PropertyTypeDetector.detect_from_object(MockSumifuMansion()) == "mansion"
    assert PropertyTypeDetector.detect_from_object(MockMitsuiKodate()) == "kodate"
    assert PropertyTypeDetector.detect_from_object(MockTokyuTochi()) == "tochi"
    assert PropertyTypeDetector.detect_from_object(MockNomuraInvestment()) == "apartment"


def test_detect_investment_type():
    """投資物件のサブ種別判定（Apartment, Mansion, Building）"""
    assert PropertyTypeDetector.detect_investment_type("○○アパート一棟売り") == "Apartment"
    assert PropertyTypeDetector.detect_investment_type("○○レジデンス 区分") == "Mansion"
    assert PropertyTypeDetector.detect_investment_type("○○ビル 一棟売り店舗") == "Building"
    assert PropertyTypeDetector.detect_investment_type("新宿区 事務所ビル") == "Building"
    assert PropertyTypeDetector.detect_investment_type("タイトル不明", default="Apartment") == "Apartment"


def test_yield_guard_in_detect():
    """利回り表記・オーナーチェンジ等がある場合、通常キーワードより優先してapartmentと判定"""
    # 1. タイトルに「中古マンション」とあっても「利回り」があれば apartment
    assert PropertyTypeDetector.detect(title="品川区中古マンション 表面利回り7.8%") == "apartment"
    assert PropertyTypeDetector.detect(title="新宿区区分マンション オーナーチェンジ物件") == "apartment"
    assert PropertyTypeDetector.detect(title="世田谷区新築一戸建て 想定利回り6.2%") == "apartment"

    # 2. specsに利回り表記がある場合
    specs = {"物件名": "グランドメゾン", "現況利回り": "8.5%"}
    assert PropertyTypeDetector.detect(specs=specs) == "apartment"

    # 3. 本文テキストに年間予定賃料がある場合
    assert PropertyTypeDetector.detect(html_text="満室想定年間賃料 300万円 満室時利回り 7.2%") == "apartment"


def test_yield_guard_in_detect_from_object():
    """辞書やモデルオブジェクトにおける利回り・収益指標の強制判定"""
    # propertyTypeがmansionと指定されていても grossYield があれば apartment
    data = {
        "propertyType": "mansion",
        "propertyName": "ライオンズマンション",
        "grossYield": 6.8,
    }
    assert PropertyTypeDetector.detect_from_object(data) == "apartment"

    # オーナーチェンジ等のテキストを含む場合も apartment
    data2 = {
        "propertyName": "高級分譲マンション（オーナーチェンジ）",
        "senyuMenseki": 30.0,
    }
    assert PropertyTypeDetector.detect_from_object(data2) == "apartment"


def test_detect_with_ai_fallback_and_sanitizer(monkeypatch):
    """AI分類フォールバックおよび事後サニタイザーの検証"""
    class MockResponse:
        def __init__(self, text):
            self.text = text

    class MockClient:
        def __init__(self, *args, **kwargs):
            self.models = self

        def generate_content(self, model, contents):
            # プロンプト内のテキストに応じて応答をシミュレート
            if "山林" in contents:
                return MockResponse("tochi")
            if "豪邸" in contents:
                return MockResponse("kodate")
            return MockResponse("mansion")

    class MockGenAI:
        Client = MockClient

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-1234")
    monkeypatch.setattr("package.utils.property_type_detector.genai", MockGenAI())

    # 1. AI分類の正常応答
    res1 = PropertyTypeDetector.detect_with_ai(title="自然に囲まれた山林 眺望良好")
    assert res1 == "tochi"

    res2 = PropertyTypeDetector.detect_with_ai(title="閑静な住宅街の豪邸 ガレージ付き")
    assert res2 == "kodate"

    # 2. 事後サニタイザー: AIが「kodate」と答えても「利回り」があれば「apartment」へ強制上書き
    res3 = PropertyTypeDetector.detect_with_ai(title="閑静な住宅街の豪邸（想定利回り8.0% オーナーチェンジ）")
    assert res3 == "apartment"

    # 3. エラー時・キー未設定時の安全フォールバック
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res_fallback = PropertyTypeDetector.detect_with_ai(title="謎の物件", default="mansion")
    assert res_fallback == "mansion"


def test_ai_called_once_per_property(monkeypatch):
    """同一物件に対するAI呼び出しが最大1回に制限されること（キャッシュ）の検証"""
    call_counts = {"count": 0}

    class MockResponse:
        def __init__(self, text):
            self.text = text

    class CountingMockClient:
        def __init__(self, *args, **kwargs):
            self.models = self

        def generate_content(self, model, contents):
            call_counts["count"] += 1
            return MockResponse("kodate")

    class MockGenAI:
        Client = CountingMockClient

    PropertyTypeDetector.clear_ai_cache()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-1234")
    monkeypatch.setattr("package.utils.property_type_detector.genai", MockGenAI())

    # 同一URL物件に対して複数回呼び出し
    url = "https://example.com/property/12345"
    res1 = PropertyTypeDetector.detect_with_ai(url=url, title="緑豊かな邸宅")
    res2 = PropertyTypeDetector.detect_with_ai(url=url, title="緑豊かな邸宅")
    res3 = PropertyTypeDetector.detect(url=url, title="緑豊かな邸宅", use_ai=True)

    assert res1 == "kodate"
    assert res2 == "kodate"
    assert res3 == "kodate"
    # AI APIの呼び出し回数が厳密に1回であること
    assert call_counts["count"] == 1


def test_edge_cases_and_error_paths(monkeypatch):
    """エッジケースおよびエラーハンドリングの網羅検証"""
    # 1. detect_from_object(None)
    assert PropertyTypeDetector.detect_from_object(None) == "mansion"

    # 2. detect_investment_type 非文字列・None
    assert PropertyTypeDetector.detect_investment_type(None) == "Apartment"
    assert PropertyTypeDetector.detect_investment_type(12345) == "Apartment"

    # 3. _get_field(None)
    assert PropertyTypeDetector._get_field(None, "field") is None

    # 4. _has_yield_signal_specs with numeric grossYield
    assert PropertyTypeDetector.detect(specs={"grossYield": "8.5%"}) == "apartment"
    assert PropertyTypeDetector.detect(specs={"grossYield": "invalid"}) is None

    # 5. _detect_from_specs fallback values
    assert PropertyTypeDetector.detect(specs={"その他備考": "区分マンションにつきオーナー募集"}) == "mansion"

    # 6. _detect_from_url subdomains
    assert PropertyTypeDetector.detect(url="https://toushi.homes.co.jp/detail/123") == "apartment"

    # 7. detect_with_ai exception handling
    class FailingMockClient:
        def __init__(self, *args, **kwargs):
            self.models = self

        def generate_content(self, model, contents):
            raise RuntimeError("Gemini API timeout error")

    class FailingGenAI:
        Client = FailingMockClient

    PropertyTypeDetector.clear_ai_cache()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-1234")
    monkeypatch.setattr("package.utils.property_type_detector.genai", FailingGenAI())

    res = PropertyTypeDetector.detect_with_ai(title="珍しい形状の住宅", default="mansion")
    assert res == "mansion"


def test_property_type_detector_helpers_and_guards():
    """変異テスト耐性: ヘルパーおよびガード関数の網羅的検証"""
    # 1. _get_field
    class SampleObj:
        senyuMenseki = 72.5
        tochiMenseki = 0.0
        kouzou = "RC造"

    obj = SampleObj()
    assert PropertyTypeDetector._get_field(obj, "senyuMenseki") == 72.5
    assert PropertyTypeDetector._get_field(obj, "unknown", default="def") == "def"
    assert PropertyTypeDetector._get_field(None, "senyuMenseki") is None
    assert PropertyTypeDetector._get_field(None, "senyuMenseki", default="def_val") == "def_val"

    # 2. _is_rc_zero_land
    assert PropertyTypeDetector._is_rc_zero_land(obj) is True
    assert PropertyTypeDetector._is_rc_zero_land(None) is False

    class NonRcObj:
        tochiMenseki = 100.0
        kouzou = "木造"

    assert PropertyTypeDetector._is_rc_zero_land(NonRcObj()) is False

    # 3. _has_yield_signal (正例・負例)
    assert PropertyTypeDetector._has_yield_signal("表面利回り 6.5%") is True
    assert PropertyTypeDetector._has_yield_signal("東京都目黒区の閑静な住宅街") is False
    assert PropertyTypeDetector._has_yield_signal(None) is False
    assert PropertyTypeDetector._has_yield_signal(123) is False

    # 4. _has_yield_signal_specs (正例・負例)
    assert PropertyTypeDetector._has_yield_signal_specs({"grossYield": "5.0%"}) is True
    assert PropertyTypeDetector._has_yield_signal_specs({"間取り": "3LDK", "所在地": "新宿区"}) is False

    # 5. _compute_cache_key fallback (specs + html_text)
    cache_key = PropertyTypeDetector._compute_cache_key(
        url="",
        title="",
        specs={"a": 1},
        html_text="<div>test_html</div>"
    )
    assert cache_key == "{'a': 1}_<div>test_html</div>"

    # 6. _detect_from_area_fields fallback
    assert PropertyTypeDetector._detect_from_area_fields({}) == "mansion"

    # 7. is_investment
    assert PropertyTypeDetector.is_investment("apartment") is True
    assert PropertyTypeDetector.is_investment("investment") is True
    assert PropertyTypeDetector.is_investment("invest_kodate") is True
    assert PropertyTypeDetector.is_investment("kodate") is False
    assert PropertyTypeDetector.is_investment("mansion") is False
    assert PropertyTypeDetector.is_investment(None) is False



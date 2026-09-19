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

    class MockModel:
        def __init__(self, name):
            self.name = name

        def generate_content(self, prompt):
            # プロンプト内のテキストに応じて応答をシミュレート
            if "山林" in prompt:
                return MockResponse("tochi")
            if "豪邸" in prompt:
                return MockResponse("kodate")
            return MockResponse("mansion")

    class MockGenAI:
        def configure(self, api_key):
            pass

        def GenerativeModel(self, name):
            return MockModel(name)

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


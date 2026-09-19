# -*- coding: utf-8 -*-
import pytest
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

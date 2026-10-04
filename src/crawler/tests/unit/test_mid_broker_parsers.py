# -*- coding: utf-8 -*-
"""
都内近郊中堅不動産4社（大成有楽・長谷工・アドキャスト・東宝ハウス）パーサー単体・統合テスト (Issue #653)
"""
import pytest
from bs4 import BeautifulSoup
from decimal import Decimal

from package.parser.baseParser import ListingEndedException
from package.parser.ietanParser import IetanMansionParser
from package.parser.hasekoParser import HasekoMansionParser
from package.parser.adcastParser import AdCastKodateParser
from package.parser.tohoParser import TohoKodateParser


# --- 1. Ietan Tests ---
def test_ietan_mansion_parser():
    html = """
    <html>
      <head><title>月島シティタワー｜月島｜中古マンション｜不動産売買のietan(イエタン)[MHF95987]</title></head>
      <body>
        <div class="price">10,780万円</div>
        <section class="estateProfile">
          <dl><dt>物件名</dt><dd>月島シティタワー</dd></dl>
          <dl><dt>所在地</dt><dd>東京都中央区月島２丁目周辺地図を見る</dd></dl>
          <dl><dt>交通</dt><dd>有楽町線「月島」駅 徒歩1分</dd></dl>
          <dl><dt>専有面積</dt><dd>56.38㎡(17.05坪) 壁芯</dd></dl>
          <dl><dt>間取り</dt><dd>2ＬＤＫ</dd></dl>
          <dl><dt>築年月</dt><dd>1999年01月</dd></dl>
          <dl><dt>構造・階建</dt><dd>ＳＲＣ 12階建 5階部分</dd></dl>
          <dl><dt>総戸数</dt><dd>44戸</dd></dl>
          <dl><dt>管理費</dt><dd>15,700円</dd></dl>
          <dl><dt>修繕積立金</dt><dd>18,070円</dd></dl>
        </section>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = IetanMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.ietan.jp/mansion/detail/MHF95987"
    res = parser._parsePropertyDetailPage(item, soup)

    assert res.propertyName == "月島シティタワー"
    assert res.price == 107800000
    assert res.priceStr == "10,780万円"
    assert res.address == "東京都中央区月島２丁目"
    assert "有楽町線" in res.traffic
    assert res.senyuMenseki == Decimal("56.38")
    assert res.madori == "2ＬＤＫ"
    assert str(res.chikunengetsu) == "1999-01-01"
    assert res.kouzou == "ＳＲＣ"
    assert res.kaisu == "5階部分"
    assert res.kanrihi == 15700
    assert res.syuzenTsumitate == 18070


def test_ietan_listing_ended():
    html = "<html><head><title>指定された物件は掲載を終了しました</title></head><body>お探しの物件は見つかりませんでした</body></html>"
    soup = BeautifulSoup(html, "html.parser")
    parser = IetanMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.ietan.jp/mansion/detail/old"
    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(item, soup)


# --- 2. Haseko Tests ---
def test_haseko_mansion_parser():
    html = """
    <html>
      <head><title>サンヴェール日本橋水天宮｜首都圏の不動産仲介なら【長谷工の仲介】</title></head>
      <body>
        <div class="price">9,980万円</div>
        <dl><dt>交通</dt><dd>東京メトロ半蔵門線「水天宮前駅」徒歩5分</dd></dl>
        <dl><dt>所在地</dt><dd>東京都中央区日本橋蛎殻町１丁目</dd></dl>
        <dl><dt>専有面積</dt><dd>55.50㎡</dd></dl>
        <dl><dt>間取り</dt><dd>2LDK</dd></dl>
        <dl><dt>築年月</dt><dd>2002年03月</dd></dl>
        <dl><dt>構造・階建て</dt><dd>RC造 10階建て 3階</dd></dl>
        <dl><dt>総戸数</dt><dd>38戸</dd></dl>
        <dl><dt>管理費</dt><dd>14,200円</dd></dl>
        <dl><dt>修繕積立金</dt><dd>16,500円</dd></dl>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = HasekoMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.haseko-chukai.com/detail/HRA64237/"
    res = parser._parsePropertyDetailPage(item, soup)

    assert "サンヴェール日本橋水天宮" in res.propertyName
    assert res.price == 99800000
    assert res.priceStr == "9,980万円"
    assert res.address == "東京都中央区日本橋蛎殻町１丁目"
    assert "水天宮前駅" in res.traffic
    assert res.senyuMenseki == Decimal("55.50")
    assert res.madori == "2LDK"
    assert str(res.chikunengetsu) == "2002-03-01"
    assert res.kanrihi == 14200
    assert res.syuzenTsumitate == 16500


def test_haseko_listing_ended():
    html = "<html><body>掲載を終了いたしました</body></html>"
    soup = BeautifulSoup(html, "html.parser")
    parser = HasekoMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.haseko-chukai.com/detail/ended/"
    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(item, soup)


# --- 3. AdCast Tests ---
def test_adcast_kodate_parser():
    html = """
    <html>
      <head><title>品川区戸越３丁目 戸建て 【12,980万円】 | 物件詳細｜アドキャスト</title></head>
      <body>
        <div class="price">販売価格12,980万円</div>
        <table>
          <tr><th>所在地</th><td>東京都品川区戸越３丁目地図で表示</td></tr>
          <tr><th>交通</th><td>都営浅草線「戸越」駅徒歩4分</td></tr>
          <tr><th>間取り</th><td>2SLDK</td></tr>
          <tr><th>土地面積</th><td>65.76m²(実測)</td></tr>
          <tr><th>建物面積</th><td>84.02m²</td></tr>
          <tr><th>築年月</th><td>2024年05月</td></tr>
          <tr><th>構造</th><td>木造3階建</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AdCastKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.ad-cast.info/sch/detail.php?k_number=20261002z&div=005"
    res = parser._parsePropertyDetailPage(item, soup)

    assert "品川区戸越３丁目" in res.propertyName
    assert res.price == 129800000
    assert res.priceStr == "12,980万円"
    assert res.address == "東京都品川区戸越３丁目"
    assert "戸越" in res.traffic
    assert res.tochiMenseki == Decimal("65.76")
    assert res.tatemonoMenseki == Decimal("84.02")
    assert res.madori == "2SLDK"
    assert str(res.chikunengetsu) == "2024-05-01"


def test_adcast_listing_ended():
    html = "<html><body>こちらの物件は成約済または掲載終了いたしました</body></html>"
    soup = BeautifulSoup(html, "html.parser")
    parser = AdCastKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.ad-cast.info/sch/detail.php?k_number=ended"
    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(item, soup)


# --- 4. Toho House Tests ---
def test_toho_house_kodate_parser():
    html = """
    <html>
      <head><title>横浜市西区西戸部町２丁目 / 中古戸建 【東宝ハウス横浜】</title></head>
      <body>
        <dl><dt>物件種別</dt><dd>中古戸建</dd></dl>
        <dl><dt>価格</dt><dd>2,780万円(税込)</dd></dl>
        <dl><dt>所在地</dt><dd>横浜市西区西戸部町２丁目</dd></dl>
        <dl><dt>交通</dt><dd>相鉄本線 / 西横浜駅 徒歩17分</dd></dl>
        <dl><dt>土地面積</dt><dd>62.53m² （18.92坪）</dd></dl>
        <dl><dt>建物面積</dt><dd>86.11m² （26.05坪）</dd></dl>
        <dl><dt>築年月</dt><dd>平成 15年 4月</dd></dl>
        <dl><dt>構造・階建て</dt><dd>木造 2階建</dd></dl>
        <dl><dt>間取り</dt><dd>3SLDK</dd></dl>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = TohoKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://th-yokohama.com/estate_detail_61109_1530.html"
    res = parser._parsePropertyDetailPage(item, soup)

    assert "横浜市西区西戸部町２丁目" in res.propertyName
    assert res.price == 27800000
    assert "2,780万円" in res.priceStr
    assert res.address == "横浜市西区西戸部町２丁目"
    assert "西横浜駅" in res.traffic
    assert res.tochiMenseki == Decimal("62.53")
    assert res.tatemonoMenseki == Decimal("86.11")
    assert str(res.chikunengetsu) == "2003-04-01"
    assert res.madori == "3SLDK"


def test_toho_listing_ended():
    html = "<html><body>お探しの物件は見つかりませんでした（成約済）</body></html>"
    soup = BeautifulSoup(html, "html.parser")
    parser = TohoKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://th-yokohama.com/estate_detail_ended.html"
    with pytest.raises(ListingEndedException):
        parser._parsePropertyDetailPage(item, soup)

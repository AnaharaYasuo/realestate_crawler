import pytest
from bs4 import BeautifulSoup
from package.parser.hasekoParser import HasekoMansionParser

SAMPLE_DETAIL_HTML = """
<!DOCTYPE html>
<html>
<head><title>売マンションファミール亀戸グランデージ</title></head>
<body>
<h1>売マンションファミール亀戸グランデージ</h1>
<div class="price">8,800万円</div>
<dl class="typo_access_address">
  <dt>交通</dt><dd>ＪＲ総武・中央緩行線「亀戸駅」徒歩11分</dd>
  <dt>所在地</dt><dd>東京都江東区亀戸３丁目５６－９</dd>
</dl>
<dl>
  <dt>物件種別</dt><dd>売マンション</dd>
  <dt>間取り</dt><dd>3LDK +納戸</dd>
  <dt>専有面積</dt><dd>77.05 ㎡ (壁芯)</dd>
  <dt>建物面積</dt><dd>㎡</dd>
  <dt>土地面積</dt><dd>2985.30 ㎡</dd>
  <dt>建ぺい率</dt><dd>-</dd>
  <dt>容積率</dt><dd>-</dd>
  <dt>完成時期</dt><dd>1999年8月</dd>
</dl>
<dl>
  <dt>物件所在地</dt><dd>東京都江東区亀戸３丁目５６－９</dd>
  <dt>建物構造</dt><dd>RC</dd>
  <dt>所在階</dt><dd>12階</dd>
  <dt>総戸数</dt><dd>123戸</dd>
  <dt>管理費</dt><dd>11,200円/月</dd>
  <dt>修繕積立金</dt><dd>26,960円/月</dd>
</dl>
</body>
</html>
"""

def test_haseko_mansion_parser_specs():
    soup = BeautifulSoup(SAMPLE_DETAIL_HTML, "html.parser")
    parser = HasekoMansionParser()
    item = parser.createEntity()
    item = parser._parsePropertyDetailPage(item, soup)
    assert item.address == "東京都江東区亀戸３丁目５６－９"
    assert item.madori == "3LDK +納戸"
    assert float(item.senyuMenseki) == 77.05
    assert item.price == 88000000
    assert item.kouzou == "RC"
    assert item.kaisu == "12階"
    assert item.chikunengetsuStr == "1999年8月"

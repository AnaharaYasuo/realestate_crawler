import asyncio
from decimal import Decimal

from package.parser.heimParser import HeimParser, HeimTochiParser


HUB_HTML = """
<html>
<head><title>スマートハイムシティ三鷹市深大寺II</title></head>
<body>
  <h1>スマートハイムシティ三鷹市深大寺II</h1>
  <table class="planTblWrap">
    <tr>
      <td>種別 土地</td>
      <td>販売価格 6,480万円</td>
      <td>土地面積 110.76㎡</td>
    </tr>
  </table>
  <p>所在地：東京都三鷹市深大寺2丁目</p>
  <a href="/bunjou/property/240044020/outline/">物件概要</a>
</body>
</html>
"""

OUTLINE_HTML = """
<html>
<head><title>物件概要｜スマートハイムシティ三鷹市深大寺II</title></head>
<body>
  <table>
    <tr><th>所在地</th><td>東京都三鷹市深大寺2丁目</td></tr>
    <tr><th>交通</th><td>JR中央線「武蔵境」駅 徒歩24分</td></tr>
    <tr><th>土地面積</th><td>110.76m2（33.5坪）</td></tr>
    <tr><th>建ぺい率</th><td>40%</td></tr>
    <tr><th>容積率</th><td>80%</td></tr>
    <tr><th>建築条件</th><td>建築条件あり</td></tr>
    <tr><th>現況</th><td>更地</td></tr>
  </table>
</body>
</html>
"""


def test_build_outline_url_patterns():
    assert (
        HeimParser._build_outline_url(
            "https://www.tokyo816.jp/bunjou/property/240044020/index.html"
        )
        == "https://www.tokyo816.jp/bunjou/property/240044020/outline/"
    )
    assert (
        HeimParser._build_outline_url(
            "https://www.tokyo816.jp/bunjou/property/240044020/"
        )
        == "https://www.tokyo816.jp/bunjou/property/240044020/outline/"
    )
    assert (
        HeimParser._build_outline_url(
            "https://www.tokyo816.jp/bunjou/property/240044020/outline/"
        )
        is None
    )
    assert (
        HeimParser._build_outline_url("https://www.sumu-heim.jp/detail/123/")
        is None
    )


def test_heim_tochi_supplements_kenpei_youseki_and_traffic_from_outline():
    parser = HeimTochiParser()
    hub_url = "https://www.tokyo816.jp/bunjou/property/240044020/index.html"
    outline_url = "https://www.tokyo816.jp/bunjou/property/240044020/outline/"

    async def fake_get_content(session, target_url, **kwargs):
        if target_url == outline_url:
            return OUTLINE_HTML.encode("utf-8")
        return HUB_HTML.encode("utf-8")

    parser._getContent = fake_get_content
    item = asyncio.run(parser.parsePropertyDetailPage(None, hub_url))

    assert item is not None
    assert item.kenpeiStr == "40%"
    assert item.kenpei == Decimal(40)
    assert item.yousekiStr == "80%"
    assert item.youseki == Decimal(80)
    assert "武蔵境" in (item.traffic or "")
    assert item.railwayWalkMinute1 == 24


def test_heim_tochi_tolerates_outline_fetch_failure():
    parser = HeimTochiParser()
    hub_url = "https://www.tokyo816.jp/bunjou/property/240044020/index.html"
    outline_url = "https://www.tokyo816.jp/bunjou/property/240044020/outline/"

    async def fake_get_content(session, target_url, **kwargs):
        if target_url == outline_url:
            raise RuntimeError("outline 404")
        return HUB_HTML.encode("utf-8")

    parser._getContent = fake_get_content
    item = asyncio.run(parser.parsePropertyDetailPage(None, hub_url))

    assert item is not None
    assert item.price == 64800000

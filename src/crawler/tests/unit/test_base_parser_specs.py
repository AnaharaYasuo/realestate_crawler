# -*- coding: utf-8 -*-
"""
ParserBase._get_specs の単位テスト (TDD)
テーブルの th/td, dt/dd, .table-row, td.table-header / td.table-data 等のパースを検証
"""
from bs4 import BeautifulSoup
from package.parser.mitsuiParser import MitsuiMansionParser


def test_get_specs_table_row_with_td_labels_and_contents():
    html = """
    <div class="property-detail">
      <table>
        <tr class="table-row">
          <td class="table-header label">価格</td>
          <td class="table-data content"><p>11,050万円</p></td>
        </tr>
        <tr class="table-row">
          <td class="table-header label">専有面積</td>
          <td class="table-data content"><p>43.56㎡</p></td>
        </tr>
        <tr class="table-row">
          <td class="table-header label">所在地</td>
          <td class="table-data content"><p>東京都港区東新橋１丁目</p></td>
        </tr>
        <tr class="table-row">
          <td class="table-header label">階数</td>
          <td class="table-data content">22階</td>
        </tr>
      </table>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiMansionParser(None)
    specs = parser._get_specs(soup)

    assert specs.get("価格") == "11,050万円"
    assert specs.get("専有面積") == "43.56㎡"
    assert specs.get("所在地") == "東京都港区東新橋１丁目"
    assert specs.get("階数") == "22階"


def test_get_specs_multi_th_td_in_single_tr():
    html = """
    <table>
      <tr>
        <th>価格</th><td>5,000万円</td>
        <th>間取り</th><td>3LDK</td>
      </tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiMansionParser(None)
    specs = parser._get_specs(soup)

    assert specs.get("価格") == "5,000万円"
    assert specs.get("間取り") == "3LDK"


def test_get_specs_excludes_footer_and_nav_noise():
    """Verify that specs inside footer, nav, or footer-related containers are excluded from _get_specs."""
    html = """
    <div class="property-detail">
      <table>
        <tr><th>価格</th><td>3,280万円</td></tr>
        <tr><th>所在地</th><td>埼玉県さいたま市</td></tr>
      </table>
    </div>
    <div id="footer">
      <nav class="footer-links">
        <dl>
          <dt>利回りから収益物件を探す</dt>
          <dd>想定利回り5％以上</dd>
        </dl>
        <table>
          <tr><th>表面利回り</th><td>8.5%</td></tr>
        </table>
      </nav>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = MitsuiMansionParser(None)
    specs = parser._get_specs(soup)

    assert specs.get("価格") == "3,280万円"
    assert specs.get("所在地") == "埼玉県さいたま市"
    assert "利回りから収益物件を探す" not in specs
    assert "表面利回り" not in specs


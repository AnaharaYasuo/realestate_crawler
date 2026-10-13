import os
import sys
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import realestateSettings

realestateSettings.configure()

from package.models.sumifu import SumifuMansion
from package.parser.kenbiyaParser import KenbiyaInvestmentApartmentParser
from package.parser.sumifuParser import SumifuMansionParser


def test_base_parser_populate_traffic_sets_item_traffic():
    """BaseParser._populateTraffic が item.traffic に交通文字列を確実に設定すること"""
    parser = SumifuMansionParser()
    item = SumifuMansion()
    item.traffic = ""

    traffic_input = "JR山手線 渋谷駅 徒歩5分"
    parser._populateTraffic(item, traffic_input)

    assert item.traffic == "JR山手線 渋谷駅 徒歩5分"
    assert item.station1 in ("渋谷", "渋谷駅")
    assert item.railway1 == "JR山手線"
    assert item.railwayWalkMinute1 == 5


def test_base_parser_populate_traffic_handles_list_input():
    """リスト形式の交通アクセス文字列でも item.traffic が正しく設定されること"""
    parser = SumifuMansionParser()
    item = SumifuMansion()
    item.traffic = ""

    traffic_list = ["東京メトロ銀座線 表参道駅 徒歩3分", "JR山手線 原宿駅 徒歩8分"]
    parser._populateTraffic(item, traffic_list)

    assert "表参道駅" in item.traffic
    assert "原宿駅" in item.traffic


def test_kenbiya_parser_filters_out_help_explanation_text():
    """健美家パーサーがページ下部のヘルプ用語解説テーブルで本物のスペックを上書きしないこと"""
    html_content = """
    <html>
      <body>
        <!-- 本物の物件スペックテーブル -->
        <table class="property-detail">
          <tr><th>所在地</th><td>東京都墨田区江東橋1丁目</td></tr>
          <tr><th>交通</th><td>JR総武線 錦糸町駅 徒歩5分</td></tr>
          <tr><th>築年月</th><td>1998年3月</td></tr>
          <tr><th>価格</th><td>5,000万円</td></tr>
        </table>

        <!-- ページ下部の用語解説ヘルプテーブル -->
        <table class="help-guide">
          <tr><th>所在地</th><td>物件所在地の住所または地番を表示。</td></tr>
          <tr><th>交通</th><td>最寄の沿線駅名及び駅までの徒歩分数または距離を表示。</td></tr>
          <tr><th>築年月</th><td>建物が完成した年月を表示。新築の場合は新築マークを表示。</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html_content, "html.parser")
    parser = KenbiyaInvestmentApartmentParser()
    specs = parser._get_specs(soup)

    # 用語解説テキストではなく、本物のスペックが保持されていること
    assert specs.get("所在地") == "東京都墨田区江東橋1丁目"
    assert specs.get("交通") == "JR総武線 錦糸町駅 徒歩5分"
    assert specs.get("築年月") == "1998年3月"
    assert specs.get("価格") == "5,000万円"


def test_kenbiya_parser_cleans_help_links_while_retaining_valid_values():
    """スペック値に付加されたヘルプリンク（情報の見方を表示 等）のみが除去され値本体が保持されること"""
    html_content = """
    <html>
      <body>
        <table class="property-detail">
          <tr><th>所在地</th><td>東京都世田谷区桜新町1丁目 (情報の見方を表示)</td></tr>
          <tr><th>交通</th><td>東急田園都市線 桜新町駅 徒歩7分 (見方を表示)</td></tr>
          <tr><th>築年月</th><td>2005年8月 (マークを表示)</td></tr>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html_content, "html.parser")
    parser = KenbiyaInvestmentApartmentParser()
    specs = parser._get_specs(soup)

    assert specs.get("所在地") == "東京都世田谷区桜新町1丁目"
    assert specs.get("交通") == "東急田園都市線 桜新町駅 徒歩7分"
    assert specs.get("築年月") == "2005年8月"

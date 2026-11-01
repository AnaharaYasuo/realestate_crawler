from unittest.mock import patch, MagicMock
import urllib.error

from package.ml.report_generator import (
    fetch_property_page_text,
    _build_rag_prompt,
    _generate_fallback_for_mansion,
    _generate_fallback_for_building,
    _generate_fallback_for_land,
    _generate_fallback_report,
)


def test_fetch_property_page_text_success():
    sample_html = b"""
    <html>
        <head><title>Test Property</title></head>
        <body>
            <nav>Menu item</nav>
            <h1>Test Mansion</h1>
            <p>2026/08 Full Renovation Completed</p>
            <footer>Footer text</footer>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.read.return_value = sample_html
    mock_resp.headers.get_content_charset.return_value = "utf-8"
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        text = fetch_property_page_text("https://example.com/property/1")
        assert "Full Renovation" in text
        assert "Menu item" not in text
        assert "Footer text" not in text


def test_fetch_property_page_text_failure_resilience():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network down")):
        text = fetch_property_page_text("https://example.com/property/error")
        assert text == ""


def test_build_rag_prompt_includes_site_text():
    mock_eval = MagicMock()
    mock_eval.estimated_sekisan_price = 4500
    mock_eval.cash_flow = 120
    mock_eval.dscr = 1.4
    mock_prop = MagicMock()
    mock_prop.tochiMenseki = 100
    mock_prop.tatemonoMenseki = 80
    mock_prop.chikunengetsuStr = "2015年1月"
    mock_prop.kouzou = "RC"
    mock_prop.setsudou = "公道 6m"

    prompt = _build_rag_prompt(
        eval_rec=mock_eval,
        prop=mock_prop,
        ptype_jp="区分マンション",
        asking_price_man=5000,
        pred_price=6000,
        address="東京都渋谷区",
        access="渋谷駅 徒歩5分",
        matched_kb=[{"title": "修繕積立金", "essence": "残高重要"}],
        far_slack=15.0,
        site_text="【備考】2026年8月新規内装リノベーション完了済み、大規模修繕実施中。"
    )
    assert "【物件詳細サイト（Web）掲載の個別情報・備考・アピールポイント】" in prompt
    assert "2026年8月新規内装リノベーション完了済み" in prompt


def test_fallback_mansion_with_site_text_keywords():
    site_text = "2026年8月新規フルリノベーション完成！専有部給排水管更新済み。大規模修繕工事中。"
    res = _generate_fallback_for_mansion(
        diff_man=1000,
        ratio=20.0,
        address="東京都港区",
        kb_top={"essence": "配管確認"},
        site_text=site_text,
    )
    assert "リノベーション" in res["highest_and_best_use"] or "リノベーション" in res["ai_evaluation_summary"]
    assert "リノベーション" in res["ai_positive_points"] or "給排水設備" in res["ai_positive_points"]


def test_fallback_building_with_site_text_keywords():
    site_text = "満室稼働中、全部賃貸中。プロパンガス会社による無償貸与設備あり。"
    res = _generate_fallback_for_building(
        diff_man=1500,
        ratio=20.0,
        asking_price_man=6000,
        sekisan_price=7000,
        far_slack=25.0,
        address="神奈川県小田原市",
        kb_top={"essence": "原契約確認"},
        site_text=site_text,
    )
    assert "満室" in res["ai_evaluation_summary"] or "満室" in res["ai_positive_points"]
    assert "プロパン" in res["ai_negative_points"]


def test_fallback_land_with_site_text_keywords():
    site_text = "建築条件なし売地。南道路接道、幅員5.6m公道。確定測量済み。"
    res = _generate_fallback_for_land(
        diff_man=800,
        ratio=21.0,
        address="兵庫県明石市",
        kb_top={"essence": "境界確認"},
        far_slack=0.0,
        prop=None,
        site_text=site_text,
    )
    assert "建築条件なし" in res["ai_positive_points"]
    assert "確定測量" in res["ai_positive_points"] or "南道路" in res["ai_positive_points"]


def test_generate_fallback_report_routing():
    mock_kb = [{"title": "test", "essence": "test essence"}]
    res = _generate_fallback_report(
        matched_kb=mock_kb,
        ptype_jp="区分マンション",
        asking_price_man=3000,
        pred_price=3500,
        sekisan_price=2000,
        far_slack=0.0,
        address="東京都",
        site_text="2026年リフォーム済"
    )
    assert "リノベーション" in res["highest_and_best_use"] or "リノベ" in res["ai_positive_points"]

# -*- coding: utf-8 -*-
import io
from PIL import Image, ImageDraw
from django.utils import timezone
from package.utils.image_handler import clean_images, verify_image_bytes, check_api_budget_cap, MAX_DAILY_IMAGE_ANALYSIS
from package.models.evaluation import PropertyEvaluation

def test_clean_images():
    # テストデータ
    raw_images = [
        {"url": "http://example.com/logo.png", "label": "会社ロゴ"},
        {"url": "http://example.com/madori.jpg", "label": "間取り図面"},
        {"url": "http://example.com/gaikan.jpg", "label": "マンション外観"},
        {"url": "http://example.com/living.jpg", "label": "広々リビング"},
        {"url": "http://example.com/kitchen.jpg", "label": "システムキッチン"},
        {"url": "http://example.com/station.jpg", "label": "最寄り駅"},
        {"url": "http://example.com/map.png", "label": "案内地図"},
        {"url": "http://example.com/toilet.jpg", "label": "温水洗浄便座"},
    ]

    cleaned = clean_images(raw_images)

    # 期待される結果:
    # - 会社ロゴ、最寄り駅、案内地図は除外されるはず
    # - 間取り図面 -> layout
    # - マンション外観 -> exterior
    # - リビング、キッチン、トイレ -> interior
    assert len(cleaned) == 5
    
    categories = {c["url"]: c["category"] for c in cleaned}
    
    assert categories["http://example.com/madori.jpg"] == "layout"
    assert categories["http://example.com/gaikan.jpg"] == "exterior"
    assert categories["http://example.com/living.jpg"] == "interior"
    assert categories["http://example.com/kitchen.jpg"] == "interior"
    assert categories["http://example.com/toilet.jpg"] == "interior"

    # 除外されたURLが含まれていないことの確認
    assert "http://example.com/logo.png" not in categories
    assert "http://example.com/station.jpg" not in categories
    assert "http://example.com/map.png" not in categories


def test_verify_image_bytes():
    # 1. 正常な画像 (400x300 でグラデーション状の模様あり)
    img_valid = Image.new("RGB", (400, 300), color="blue")
    draw = ImageDraw.Draw(img_valid)
    draw.line((0, 0, 400, 300), fill="red", width=10) # 色に変化をつける
    draw.rectangle((50, 50, 150, 150), fill="yellow")
    
    buf_valid = io.BytesIO()
    img_valid.save(buf_valid, format="JPEG")
    assert verify_image_bytes(buf_valid.getvalue()) is True

    # 2. 小さすぎる画像 (100x100)
    img_small = Image.new("RGB", (100, 100), color="blue")
    buf_small = io.BytesIO()
    img_small.save(buf_small, format="JPEG")
    assert verify_image_bytes(buf_small.getvalue()) is False

    # 3. 極端なアスペクト比 (600x100)
    img_wide = Image.new("RGB", (600, 100), color="blue")
    buf_wide = io.BytesIO()
    img_wide.save(buf_wide, format="JPEG")
    assert verify_image_bytes(buf_wide.getvalue()) is False

    # 4. 単色プレースホルダー画像 (400x300, 白単色 ➔ 分散0)
    img_mono = Image.new("RGB", (400, 300), color="white")
    buf_mono = io.BytesIO()
    img_mono.save(buf_mono, format="JPEG")
    assert verify_image_bytes(buf_mono.getvalue()) is False


def test_check_api_budget_cap():
    # 初期状態 (当日の解析数は 0 なので True)
    assert check_api_budget_cap() is True

    # 予算上限（MAX_DAILY_IMAGE_ANALYSIS - 1）件のレコードを挿入
    today = timezone.now()
    evals = []
    for i in range(MAX_DAILY_IMAGE_ANALYSIS - 1):
        evals.append(
            PropertyEvaluation(
                company="mitsui",
                property_type="mansion",
                property_id=i,
                property_url=f"http://example.com/prop/{i}",
                analysis_status="completed",
                analyzed_at=today
            )
        )
    PropertyEvaluation.objects.bulk_create(evals)

    # まだ上限未満なので True
    assert check_api_budget_cap() is True

    # さらにもう1件挿入して上限に到達させる
    PropertyEvaluation.objects.create(
        company="mitsui",
        property_type="mansion",
        property_id=9999,
        property_url="http://example.com/prop/limit",
        analysis_status="completed",
        analyzed_at=today
    )

    # 上限に達したため False になるべき
    assert check_api_budget_cap() is False


def test_clean_images_with_plot_plan():
    """区画図キーワードによる plot_plan カテゴリ分類の検証"""
    raw_images = [
        {"url": "http://example.com/kukaku.jpg", "label": "区画図面"},
        {"url": "http://example.com/haichi.png", "label": "敷地配置図"},
        {"url": "http://example.com/kozu.jpg", "label": "公図・測量図"},
        {"url": "http://example.com/madori.jpg", "label": "間取り図"},
    ]
    cleaned = clean_images(raw_images)
    assert len(cleaned) == 4
    categories = {c["url"]: c["category"] for c in cleaned}
    assert categories["http://example.com/kukaku.jpg"] == "plot_plan"
    assert categories["http://example.com/haichi.png"] == "plot_plan"
    assert categories["http://example.com/kozu.jpg"] == "plot_plan"
    assert categories["http://example.com/madori.jpg"] == "layout"


def test_parse_gemini_analysis_response():
    """Gemini APIレスポンスパースおよび不整形地補正・画地スコア算出の検証"""
    from package.utils.image_handler import _parse_gemini_analysis_response

    default_result = {
        'frontage_length_est': None,
        'road_width_est': None,
        'passage_width': None,
        'shape_score_100': None,
        'nta_irregular_discount': None,
        'retaining_wall_risk': 'none',
        'ground_elevation_diff_m': None,
        'demolition_difficulty': 'medium',
        'utility_pole_risk': 'none',
        'foundation_crack_risk': None,
        'water_leak_risk': None,
        'stair_steepness': 'unknown',
        'indoor_washing_machine_space': 'unknown',
        'exposed_pipes_risk': None,
        'renovation_budget_tier': 'tier_medium',
    }

    # 1. 正常系: かげ地あり
    resp_text = """
    ```json
    {
        "shadow_area_ratio": 0.25,
        "frontage_length_est": 8.5,
        "road_width_est": 4.0,
        "passage_width": 2.5,
        "retaining_wall_risk": "stone_masonry",
        "ground_elevation_diff_m": 1.2,
        "demolition_difficulty": "high",
        "utility_pole_risk": "guy_wire",
        "foundation_crack_risk": true,
        "water_leak_risk": false,
        "stair_steepness": "steep",
        "indoor_washing_machine_space": "outdoor",
        "exposed_pipes_risk": true,
        "renovation_budget_tier": "tier_heavy"
    }
    ```
    """
    res = _parse_gemini_analysis_response(resp_text, default_result)
    assert res['shape_score_100'] == 75.0
    assert res['nta_irregular_discount'] is not None
    assert res['retaining_wall_risk'] == 'stone_masonry'
    assert res['ground_elevation_diff_m'] == 1.2
    assert res['foundation_crack_risk'] is True
    assert res['water_leak_risk'] is False
    assert res['stair_steepness'] == 'steep'
    assert res['indoor_washing_machine_space'] == 'outdoor'
    assert res['renovation_budget_tier'] == 'tier_heavy'

    # 2. かげ地なし (None)
    resp_text_none = '{"shadow_area_ratio": null, "retaining_wall_risk": "none"}'
    res_none = _parse_gemini_analysis_response(resp_text_none, default_result)
    assert res_none['shape_score_100'] is None
    assert res_none['nta_irregular_discount'] is None
    assert res_none['foundation_crack_risk'] is None

    # 3. 不正テキスト (フォールバック)
    invalid_res = _parse_gemini_analysis_response("Invalid text without json", default_result)
    assert invalid_res == default_result


def test_analyze_property_images_with_gemini(monkeypatch):
    """画像ソート優先度、URL重複排除、Gemini呼び出しの検証"""
    from unittest.mock import MagicMock
    from package.utils.image_handler import analyze_property_images_with_gemini

    # Mock clean_images input with duplicate URLs and different categories
    cleaned_images = [
        {"url": "http://example.com/interior1.jpg", "category": "interior"},
        {"url": "http://example.com/plot.jpg", "category": "plot_plan"},
        {"url": "http://example.com/plot.jpg", "category": "plot_plan"},  # 重複
        {"url": "http://example.com/layout1.jpg", "category": "layout"},
        {"url": "http://example.com/exterior1.jpg", "category": "exterior"},
    ]

    # Mock requests.get
    fake_img = Image.new("RGB", (400, 300), color="blue")
    draw = ImageDraw.Draw(fake_img)
    draw.line((0, 0, 400, 300), fill="red", width=10)
    draw.rectangle((50, 50, 150, 150), fill="yellow")
    buf = io.BytesIO()
    fake_img.save(buf, format="JPEG")
    fake_bytes = buf.getvalue()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = fake_bytes

    monkeypatch.setattr("requests.get", lambda url, timeout: mock_resp)

    # Mock genai
    mock_model = MagicMock()
    mock_gen_resp = MagicMock()
    mock_gen_resp.text = '{"shadow_area_ratio": 0.1, "retaining_wall_risk": "none"}'
    mock_model.generate_content.return_value = mock_gen_resp

    monkeypatch.setenv("GEMINI_API_KEY", "fake_api_key")
    monkeypatch.setattr("google.generativeai.GenerativeModel", lambda m: mock_model)

    result = analyze_property_images_with_gemini(cleaned_images)
    assert result['shape_score_100'] == 90.0
    assert result['retaining_wall_risk'] == 'none'

    # Exception during generate_content -> returns default_result
    mock_model.generate_content.side_effect = RuntimeError("API error")
    err_res = analyze_property_images_with_gemini(cleaned_images)
    assert err_res['shape_score_100'] is None


def test_update_from_gemini_model_persistence():
    """PropertyEvaluation.update_from_gemini のフィールド反映と None 保持の検証"""
    eval_rec = PropertyEvaluation(
        company="mitsui",
        property_type="kodate",
        property_id=101,
        property_url="http://example.com/test101",
    )
    gemini_data = {
        'shape_score_100': 85.0,
        'nta_irregular_discount': 0.95,
        'retaining_wall_risk': 'rc_legal',
        'ground_elevation_diff_m': 0.8,
        'demolition_difficulty': 'low',
        'utility_pole_risk': 'pole',
        'foundation_crack_risk': True,
        'water_leak_risk': None,  # Noneは更新されないこと
        'stair_steepness': 'gentle',
        'indoor_washing_machine_space': 'indoor',
        'exposed_pipes_risk': False,
        'renovation_budget_tier': 'tier_light',
    }
    eval_rec.update_from_gemini(gemini_data)

    assert eval_rec.shape_score_100 == 85.0
    assert eval_rec.nta_irregular_discount == 0.95
    assert eval_rec.retaining_wall_risk == 'rc_legal'
    assert eval_rec.ground_elevation_diff_m == 0.8
    assert eval_rec.foundation_crack_risk is True
    assert eval_rec.water_leak_risk is None
    assert eval_rec.renovation_budget_tier == 'tier_light'


def test_run_bulk_ml_evaluation_helpers():
    """run_bulk_ml_evaluation 内の _extract_land_rent_and_liability と _populate_text_risks の検証"""
    from decimal import Decimal
    from scripts.ops.run_bulk_ml_evaluation import _extract_land_rent_and_liability, _populate_text_risks

    class DummyItem:
        chidai = 20000
        chidaiStr = None
        propertyName = "テスト物件"
        address = "東京都新宿区"
        traffic = "新宿駅徒歩5分"
        biko = "告知事項あり。契約不適合免責。再建築不可。"
        tochikenri = "所有権"
        genkyo = "空家"
        torihiki = "媒介"
        setsubi = "都市ガス、本下水、ユニットバス"
        kaisu = "4階"
        kai = 4
        floorMax = 10
        chikunengetsu = None
        chikunengetsuStr = "1978年3月"

    item = DummyItem()
    rent, liability = _extract_land_rent_and_liability(item)
    assert rent == 20000
    assert liability == Decimal(480)

    item.chidai = None
    item.chidaiStr = "月額10,000円"
    rent, liability = _extract_land_rent_and_liability(item)
    assert rent == 10000

    # 2. テキストリスク反映
    eval_rec = PropertyEvaluation(company="sumifu", property_type="mansion", property_id=5)
    _populate_text_risks(eval_rec, item)
    assert eval_rec.is_psychological_defect is True
    assert eval_rec.is_as_is_condition is True
    assert eval_rec.is_unbuildable is True
    assert eval_rec.gas_type == "city_gas"
    assert eval_rec.bath_type == "unit_bath"
    assert eval_rec.is_old_earthquake_standard is True


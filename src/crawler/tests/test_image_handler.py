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

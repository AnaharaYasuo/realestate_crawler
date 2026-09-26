import io
import json
import logging
import os
import re
from urllib.parse import urljoin

from google import genai
from google.genai import types
import requests
from django.utils import timezone
from package.models.evaluation import PropertyEvaluation
from package.utils.plot_shape_analyzer import calculate_nta_irregular_discount
from PIL import Image

logger = logging.getLogger(__name__)

# 1日のGemini API上限数
MAX_DAILY_IMAGE_ANALYSIS = 200

# 除外対象の不要キーワード（周辺環境、ダミー、広告、ロゴなど）
REJECT_KEYWORDS = [
    '周辺', '環境', '駅', '学校', '店舗', 'スーパー', '地図', '街なみ',
    '街並み', 'コンビニ', 'ドラッグストア', '小学校', '中学校', '病院',
    '公園', '役所', '郵便局', '銀行', 'バス停', '道路', '現地案内図',
    '案内図', 'logo', 'map', 'banner', 'dummy', 'noimage', '担当者',
    'ロゴ', '案内', '案内板', '看板', 'ライフインフォメーション'
]

# 各カテゴリのホワイトリストキーワード
PLOT_PLAN_KEYWORDS = ['区画', '敷地配置', '土地図', '公図', '測量図', '実測図', '区画図']
LAYOUT_KEYWORDS = ['間取', '平面']
EXTERIOR_KEYWORDS = ['外観', '建物', 'エントランス', '共有', 'ロビー', 'アプローチ', '庭']


def extract_images_from_soup(soup, base_url):
    """BeautifulSoupオブジェクトから画像URLとラベル（alt属性や周囲のテキスト）のリストを抽出する。"""
    images = []
    if not soup:
        return images

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy")
        if not src:
            continue

        full_url = urljoin(base_url, src.strip())
        alt = img.get("alt", "").strip()
        parent_text = img.parent.get_text(strip=True) if img.parent else ""
        label = f"{alt} {parent_text}".strip()

        images.append({
            "url": full_url,
            "label": label
        })

    return images


def _is_rejected_image(label_lower: str, url_lower: str) -> bool:
    """除外キーワードに合致するか判定する。"""
    return any(kw.lower() in label_lower or kw.lower() in url_lower for kw in REJECT_KEYWORDS)


def _detect_image_category(label_lower: str, url_lower: str) -> str | None:
    """ラベルとURLから画像カテゴリ（plot_plan, layout, exterior, interior）を判定する。"""
    if any(kw.lower() in label_lower or kw.lower() in url_lower for kw in PLOT_PLAN_KEYWORDS):
        return 'plot_plan'
    if any(kw.lower() in label_lower or kw.lower() in url_lower for kw in LAYOUT_KEYWORDS):
        return 'layout'
    if any(kw.lower() in label_lower or kw.lower() in url_lower for kw in EXTERIOR_KEYWORDS):
        return 'exterior'
    return 'interior'


def clean_images(images_list):
    """画像のリストを入力とし、不要な画像を除外してホワイトリストカテゴリに分類して返す。"""
    cleaned = []
    for img in images_list:
        url = img.get("url", "") or ""
        label = img.get("label", "") or ""
        url_lower = url.lower()
        label_lower = label.lower()

        if _is_rejected_image(label_lower, url_lower):
            continue

        category = _detect_image_category(label_lower, url_lower)
        cleaned.append({
            "url": url,
            "label": label,
            "category": category
        })
    return cleaned


def verify_image_bytes(image_bytes):
    """バイト列が有効な画像であるか検証し、単色画像や極端に小さい画像でないかチェックする。"""
    if not image_bytes or len(image_bytes) < 1000:
        return False
        
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.verify()
            
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.size
            if width < 50 or height < 50:
                return False
                
            img_small = img.resize((10, 10)).convert("RGB")
            pixels = list(img_small.getdata())
            first_pixel = pixels[0]
            is_monochrome = all(p == first_pixel for p in pixels)
            if is_monochrome:
                return False
                
        return True
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Image verification failed: {e}")
        return False


def check_daily_analysis_limit():
    """本日の画像解析実行数が上限（200件）に達しているか確認する。"""
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = PropertyEvaluation.objects.filter(
        analysis_status__in=['processing', 'completed'],
        analyzed_at__gte=today_start
    ).count()
    return count < MAX_DAILY_IMAGE_ANALYSIS


# Alias for test backwards-compatibility
check_api_budget_cap = check_daily_analysis_limit


def _parse_gemini_analysis_response(text: str, default_result: dict) -> dict:
    """Gemini APIのテキストレスポンスからJSONをパースし、評価結果辞書を構築する。"""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        logger.warning(f"Failed to parse Gemini response: {text}")
        return default_result

    data = json.loads(match.group(0))
    result = default_result.copy()

    shadow_ratio = float(data.get('shadow_area_ratio')) if data.get('shadow_area_ratio') is not None else None
    nta_discount = None
    shape_score_100 = None
    if shadow_ratio is not None:
        nta_discount = calculate_nta_irregular_discount(shadow_ratio)
        shape_score_100 = round(max(0.0, min(100.0, 100.0 - (shadow_ratio * 100.0))), 1)

    result.update({
        'interior_score': float(data.get('interior_score', 3.5)),
        'layout_score': float(data.get('layout_score', 3.5)),
        'plot_shape_type': str(data.get('plot_shape_type', 'unknown')),
        'plot_shape_description': str(data.get('plot_shape_description', '')),
        'maintenance_score': float(data.get('maintenance_score', 3.5)),
        'maintenance_comment': str(data.get('maintenance_comment', '')),
        'shadow_area_ratio': shadow_ratio,
        'frontage_length_est': float(data.get('frontage_length_est')) if data.get('frontage_length_est') is not None else None,
        'road_width_est': float(data.get('road_width_est')) if data.get('road_width_est') is not None else None,
        'passage_width': float(data.get('passage_width')) if data.get('passage_width') is not None else None,
        'shape_score_100': shape_score_100,
        'nta_irregular_discount': nta_discount,
        'retaining_wall_risk': str(data.get('retaining_wall_risk', 'none')),
        'ground_elevation_diff_m': float(data.get('ground_elevation_diff_m')) if data.get('ground_elevation_diff_m') is not None else None,
        'demolition_difficulty': str(data.get('demolition_difficulty', 'medium')),
        'utility_pole_risk': str(data.get('utility_pole_risk', 'none')),
        'foundation_crack_risk': bool(data['foundation_crack_risk']) if data.get('foundation_crack_risk') is not None else None,
        'water_leak_risk': bool(data['water_leak_risk']) if data.get('water_leak_risk') is not None else None,
        'stair_steepness': str(data.get('stair_steepness', 'unknown')),
        'indoor_washing_machine_space': str(data.get('indoor_washing_machine_space', 'unknown')),
        'exposed_pipes_risk': bool(data['exposed_pipes_risk']) if data.get('exposed_pipes_risk') is not None else None,
        'renovation_budget_tier': str(data.get('renovation_budget_tier', 'tier_medium')),
    })
    return result


def analyze_property_images_with_gemini(cleaned_images):
    """選別された画像群をGeminiに渡し、画像特化の画地幾何およびプロ目線リスク予測を実行する。"""
    default_result = {
        'interior_score': 3.5,
        'layout_score': 3.5,
        'plot_shape_type': 'unknown',
        'plot_shape_description': '',
        'maintenance_score': 3.5,
        'maintenance_comment': '',
        'shadow_area_ratio': None,
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

    if not cleaned_images:
        return default_result

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not configured. Skipping Gemini image analysis.")
        return default_result

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=30000)
    )

    # Deduplicate by URL and prioritize 'plot_plan' first
    seen_urls = set()
    unique_images = []
    for img in cleaned_images:
        url = img.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_images.append(img)

    category_priority = {"plot_plan": 0, "layout": 1, "exterior": 2, "interior": 3}
    sorted_images = sorted(
        unique_images,
        key=lambda x: category_priority.get(x.get("category", ""), 99)
    )

    images_to_send = []
    for item in sorted_images[:5]:
        url = item.get("url")
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200 and verify_image_bytes(resp.content):
                img = Image.open(io.BytesIO(resp.content))
                images_to_send.append(img)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Failed to load image for Gemini: {e}")

    if not images_to_send:
        logger.warning("No valid images downloaded. Using default analysis result.")
        return default_result

    prompt = """
あなたはお不動産買い付けのプロ査定士です。提供された画像群（区画図・配置図、間取り図、外観、内装など）から、
画像からしか視認できない画地幾何指標およびコストリスクを厳密に査定し、以下のJSON形式で回答してください。

```json
{
  "interior_score": 1.0〜5.0,
  "layout_score": 1.0〜5.0,
  "plot_shape_type": "regular" | "irregular" | "flagpole" | "unknown",
  "plot_shape_description": "土地形状の具体的特徴",
  "maintenance_score": 1.0〜5.0,
  "maintenance_comment": "外観状態の評価",
  "shadow_area_ratio": 0.0〜1.0 (区画図がある場合のかげ地割合。ない場合はnull),
  "frontage_length_est": 推定間口幅(m) または null,
  "road_width_est": 推定前面道路幅(m) または null,
  "passage_width": 旗竿地の場合の通路幅(m) または null,
  "retaining_wall_risk": "none" | "rc_legal" | "stone_masonry" | "two_tier_illegal",
  "ground_elevation_diff_m": 道路との高低差(m) または null,
  "demolition_difficulty": "low" | "medium" | "high",
  "utility_pole_risk": "none" | "pole" | "guy_wire",
  "foundation_crack_risk": true | false,
  "water_leak_risk": true | false,
  "stair_steepness": "normal" | "steep" | "unknown",
  "indoor_washing_machine_space": "indoor" | "outdoor" | "unknown",
  "exposed_pipes_risk": true | false,
  "renovation_budget_tier": "tier_none" | "tier_light" | "tier_medium" | "tier_heavy" | "tier_full"
}
```
"""

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt] + images_to_send,
        )
        return _parse_gemini_analysis_response(response.text, default_result)
    except Exception:
        logger.exception("Error during Gemini image analysis")
        return default_result

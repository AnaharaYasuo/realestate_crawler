import io
import json
import logging
import os
import re
from urllib.parse import urljoin

import requests
from django.utils import timezone
from google import genai
from google.genai import types
from package.models.evaluation import PropertyEvaluation
from package.utils.gemini_rate_limiter import get_gemini_flash_limiter
from package.utils.http_client import fetch_image_bytes
from package.utils.opencv_image_analyzer import analyze_pil_images_with_opencv
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
            raw_bytes = fetch_image_bytes(url, timeout=10)
            if raw_bytes and verify_image_bytes(raw_bytes):
                img = Image.open(io.BytesIO(raw_bytes))
                images_to_send.append(img)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Failed to load image for Gemini: {e}")

    if not images_to_send:
        logger.warning("No valid images downloaded. Using default analysis result.")
        return default_result

    try:
        with genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=30000)
        ) as client:
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

            response = get_gemini_flash_limiter().execute(
                client.models.generate_content,
                model='gemini-2.5-flash',
                contents=[prompt] + images_to_send,
            )
            return _parse_gemini_analysis_response(response.text, default_result)
    except Exception:
        logger.exception("Error during Gemini image analysis")
        return default_result


def _default_image_analysis_result() -> dict:
    return {
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


def _open_valid_pil_image(image_bytes: bytes, category: str) -> Image.Image | None:
    if not image_bytes:
        return None
    if verify_image_bytes(image_bytes):
        return Image.open(io.BytesIO(image_bytes))
    if category in ('plot_plan', 'layout'):
        try:
            with Image.open(io.BytesIO(image_bytes)) as probe:
                w, h = probe.size
                if w < 150 or h < 150:
                    return None
                small = list(probe.resize((12, 12)).convert('RGB').getdata())
                if all(px == small[0] for px in small):
                    return None
            return Image.open(io.BytesIO(image_bytes))
        except Exception:  # noqa: BLE001
            return None
    return None


def _fetch_single_pil_image(url: str, cat: str) -> Image.Image | None:
    try:
        raw_bytes = fetch_image_bytes(url, timeout=10)
        if raw_bytes:
            return _open_valid_pil_image(raw_bytes, cat)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to download image for hybrid analysis: %s", exc)
    return None


def _download_categorized_images(cleaned_images: list[dict], max_images: int = 5) -> list[tuple[str, Image.Image]]:
    seen_urls: set[str] = set()
    unique_items: list[dict] = []
    for item in cleaned_images:
        url = item.get('url')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_items.append(item)

    category_priority = {'plot_plan': 0, 'layout': 1, 'exterior': 2, 'interior': 3}
    sorted_items = sorted(unique_items, key=lambda x: category_priority.get(x.get('category', ''), 99))

    loaded: list[tuple[str, Image.Image]] = []
    for item in sorted_items[:max_images]:
        url = str(item.get('url') or '')
        cat = str(item.get('category') or 'interior')
        pil_img = _fetch_single_pil_image(url, cat) if url else None
        if pil_img is not None:
            loaded.append((cat, pil_img))
    return loaded


_GEMINI_SEMANTIC_KEYS: tuple[str, ...] = (
    'retaining_wall_risk',
    'ground_elevation_diff_m',
    'demolition_difficulty',
    'utility_pole_risk',
    'foundation_crack_risk',
    'water_leak_risk',
    'stair_steepness',
    'indoor_washing_machine_space',
    'exposed_pipes_risk',
    'renovation_budget_tier',
    'frontage_length_est',
    'road_width_est',
    'maintenance_comment',
    'layout_score',
)


def _apply_gemini_semantic_and_blended_scores(fused: dict, cv_res: dict, gemini_res: dict) -> None:
    for k in _GEMINI_SEMANTIC_KEYS:
        val = gemini_res.get(k)
        if val is not None and val != '':
            fused[k] = val

    for score_key in ('interior_score', 'maintenance_score'):
        g_val = gemini_res.get(score_key)
        c_val = cv_res.get(score_key)
        if isinstance(g_val, (int, float)) and isinstance(c_val, (int, float)):
            fused[score_key] = round(0.4 * float(c_val) + 0.6 * float(g_val), 2)


def _apply_geometry_fallback_fields(fused: dict, cv_res: dict, gemini_res: dict) -> None:
    g_shape = gemini_res.get('plot_shape_type')
    if cv_res.get('shadow_area_ratio') is not None:
        if fused.get('plot_shape_type') == 'unknown' and g_shape:
            fused['plot_shape_type'] = g_shape
        return
    for geom_key in ('shadow_area_ratio', 'shape_score_100', 'nta_irregular_discount', 'passage_width'):
        if gemini_res.get(geom_key) is not None:
            fused[geom_key] = gemini_res[geom_key]
    if g_shape and g_shape != 'unknown':
        fused['plot_shape_type'] = g_shape


def _fuse_opencv_and_gemini_results(base_res: dict, cv_res: dict, gemini_res: dict | None) -> dict:
    fused = base_res.copy()
    for k, v in cv_res.items():
        if v is not None and v != '':
            fused[k] = v
    if not gemini_res:
        return fused
    _apply_gemini_semantic_and_blended_scores(fused, cv_res, gemini_res)
    _apply_geometry_fallback_fields(fused, cv_res, gemini_res)
    return fused


def analyze_property_images_hybrid(cleaned_images: list[dict]) -> dict:
    """OpenCV の精密幾何・測光解析と、2秒間隔レート制限付き `gemini-2.5-flash` の意味査定を融合する。"""
    base_res = _default_image_analysis_result()
    if not cleaned_images:
        return base_res

    categorized_pil = _download_categorized_images(cleaned_images, max_images=5)
    if not categorized_pil:
        return base_res

    cv_res = analyze_pil_images_with_opencv(categorized_pil)
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return _fuse_opencv_and_gemini_results(base_res, cv_res, None)

    gemini_res = None
    prompt = (
        "あなたは不動産買い付けのプロ査定士です。提供画像から擁壁リスク・電柱支線・基礎クラック・"
        "漏水サイン・階段勾配・洗濯機置場・間取り動線・想定リフォーム規模を厳密査定しJSONのみで回答してください。\n"
        '{"interior_score": 3.5, "layout_score": 3.5, "maintenance_score": 3.5, '
        '"maintenance_comment": "", "plot_shape_type": "unknown", "shadow_area_ratio": null, '
        '"frontage_length_est": null, "road_width_est": null, "passage_width": null, '
        '"retaining_wall_risk": "none", "ground_elevation_diff_m": null, '
        '"demolition_difficulty": "medium", "utility_pole_risk": "none", '
        '"foundation_crack_risk": false, "water_leak_risk": false, '
        '"stair_steepness": "unknown", "indoor_washing_machine_space": "unknown", '
        '"exposed_pipes_risk": false, "renovation_budget_tier": "tier_medium"}'
    )
    try:
        pil_only = [img for _, img in categorized_pil]
        model_name = os.getenv('GEMINI_VISION_MODEL', 'gemini-2.5-flash')
        with genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30000)) as client:
            resp = get_gemini_flash_limiter().execute(
                client.models.generate_content,
                model=model_name,
                contents=[prompt, *pil_only],
            )
            gemini_res = _parse_gemini_analysis_response(resp.text or "", base_res)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini 2.5 Flash skipped/failed in hybrid vision; using OpenCV result: %s", exc)

    return _fuse_opencv_and_gemini_results(base_res, cv_res, gemini_res)

# -*- coding: utf-8 -*-
import io
import re
import os
import json
import logging
import requests
from django.utils import timezone
from PIL import Image
import google.generativeai as genai
from package.models.evaluation import PropertyEvaluation

# 1日のGemini API上限数
MAX_DAILY_IMAGE_ANALYSIS = 200

# 除外対象の不要キーワード（周辺環境、ダミー、広告、ロゴなど）
REJECT_KEYWORDS = [
    u'周辺', u'環境', u'駅', u'学校', u'店舗', u'スーパー', u'地図', u'街なみ',
    u'街並み', u'コンビニ', u'ドラッグストア', u'小学校', u'中学校', u'病院',
    u'公園', u'役所', u'郵便局', u'銀行', u'バス停', u'道路', u'現地案内図',
    u'案内図', u'logo', u'map', u'banner', u'dummy', u'noimage', u'担当者',
    u'ロゴ', u'案内', u'案内板', u'看板', u'ライフインフォメーション'
]

# 各カテゴリのホワイトリストキーワード
LAYOUT_KEYWORDS = [u'間取', u'平面', u'区画']
EXTERIOR_KEYWORDS = [u'外観', u'建物', u'エントランス', u'共有', u'ロビー', u'アプローチ', u'庭']


def extract_images_from_soup(soup, base_url):
    """
    BeautifulSoupオブジェクトから画像URLとラベル（alt属性や周囲のテキスト）のリストを抽出する。
    """
    images = []
    if not soup:
        return images
        
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy")
        if not src:
            continue
            
        # 相対パスを絶対パスに変換
        from urllib.parse import urljoin
        abs_url = urljoin(base_url, src)
        
        # 拡張子チェック (jpg, jpeg, png, webp のみ)
        # クエリパラメータ付きURL対策として、?以降をカットして拡張子判定
        clean_url = abs_url.split('?')[0]
        if not any(clean_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            continue
            
        alt = img.get("alt") or img.get("title") or ""
        label = alt.strip()
        
        # 重複排除
        if abs_url not in [i["url"] for i in images]:
            images.append({
                "url": abs_url,
                "label": label
            })
            
    return images


def clean_images(images_list):
    """
    画像のリストを入力とし、不要な画像（周辺環境やロゴなど）を除外して
    ホワイトリストに該当する画像のみをカテゴリに分類して返す。
    
    images_list: list of dict. 例: [{"url": "http...", "label": "外観"}]
    """
    cleaned = []
    
    for img in images_list:
        url = img.get("url", "") or ""
        label = img.get("label", "") or ""
        
        # Noneや空文字対策
        url_lower = url.lower()
        label_lower = label.lower()
        
        # 1. 除外キーワードチェック
        has_reject = False
        for kw in REJECT_KEYWORDS:
            if kw.lower() in label_lower or kw.lower() in url_lower:
                has_reject = True
                break
        
        if has_reject:
            continue
            
        # 2. カテゴリ判定
        category = None
        
        # 間取り判定
        for kw in LAYOUT_KEYWORDS:
            if kw.lower() in label_lower or kw.lower() in url_lower:
                category = 'layout'
                break
                
        if not category:
            # 外観判定
            for kw in EXTERIOR_KEYWORDS:
                if kw.lower() in label_lower or kw.lower() in url_lower:
                    category = 'exterior'
                    break
                    
        if not category:
            # 内装判定（それ以外を内装とみなす）
            category = 'interior'
            
        cleaned.append({
            "url": url,
            "category": category
        })
        
    return cleaned


def verify_image_bytes(image_bytes: bytes) -> bool:
    """
    画像のバイナリデータをチェックし、サイズ、アスペクト比、色の分散から
    明らかにノイズ（プレースホルダーや小さすぎるアイコン）であるものを除外する。
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        
        # 1. サイズフィルター
        if width < 200 or height < 200:
            return False
            
        # 2. アスペクト比フィルター
        aspect_ratio = float(width) / float(height)
        if aspect_ratio > 3.0 or aspect_ratio < 0.33:
            return False
            
        # 3. 単色プレースホルダー画像（ダミー）の判定
        img_rgb = img.convert('RGB')
        img_small = img_rgb.resize((10, 10))
        pixels = list(img_small.getdata())
        
        r_vals = [p[0] for p in pixels]
        g_vals = [p[1] for p in pixels]
        b_vals = [p[2] for p in pixels]
        
        def std_dev(lst):
            mean = sum(lst) / len(lst)
            variance = sum((x - mean) ** 2 for x in lst) / len(lst)
            return variance ** 0.5
            
        r_std = std_dev(r_vals)
        g_std = std_dev(g_vals)
        b_std = std_dev(b_vals)
        
        if r_std < 5.0 and g_std < 5.0 and b_std < 5.0:
            return False
            
        return True
    except Exception:
        return False


def check_api_budget_cap() -> bool:
    """
    当日の画像解析APIの実行数が上限（200件）を超えていないかチェックする。
    """
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    current_count = PropertyEvaluation.objects.filter(
        analysis_status__in=['completed', 'processing'],
        analyzed_at__gte=today_start
    ).count()
    
    return current_count < MAX_DAILY_IMAGE_ANALYSIS


def analyze_property_images_with_gemini(cleaned_images) -> dict:
    """
    クレンジング済み画像リストから画像をダウンロードし、
    Gemini API に入力して各種画像解析メタデータ（内装、間取り、土地形状、外観状態）を取得する。
    
    返り値: dict
    """
    default_result = {
        'interior_score': 3.5,
        'layout_score': 3.5,
        'plot_shape_type': 'unknown',
        'plot_shape_description': '画像なしのため判定不能',
        'maintenance_score': 3.5,
        'maintenance_comment': '画像なしのため判定不能'
    }
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logging.error("❌ [CRITICAL ERROR] GEMINI_API_KEY env variable is NOT configured. Gemini image analysis will be skipped and default dummy scores will be returned! Please set the API key in your .env or system environment.")
        return default_result
        
    try:
        genai.configure(api_key=api_key)
        # gemini-1.5-flashを使用
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        images_to_send = []
        categories_to_send = ['layout', 'exterior', 'interior']
        
        for cat in categories_to_send:
            target = [img for img in cleaned_images if img['category'] == cat]
            # 各カテゴリ最大2枚まで取得して解析精度を高める
            for img_info in target[:2]:
                try:
                    resp = requests.get(img_info['url'], timeout=10)
                    if resp.status_code == 200:
                        img_bytes = resp.content
                        if verify_image_bytes(img_bytes):
                            pil_img = Image.open(io.BytesIO(img_bytes))
                            images_to_send.append(pil_img)
                except Exception as e:
                    logging.warning(f"Failed to download or verify image {img_info['url']}: {e}")
                    
        if not images_to_send:
            logging.warning("No valid images downloaded. Using default analysis result.")
            return default_result
            
        prompt = (
            "Analyze these real estate images (interior, layout/plot plan, exterior) and evaluate the property.\n"
            "Return a JSON object containing the following fields:\n"
            "1. 'interior_score': float between 1.0 and 5.0 (cleanliness and design of interior)\n"
            "2. 'layout_score': float between 1.0 and 5.0 (utility and efficiency of floor plan)\n"
            "3. 'plot_shape_type': string, one of ['regular', 'irregular', 'flagpole', 'unknown']\n"
            "   - 'regular': Standard rectangular/square shape, easy to build on.\n"
            "   - 'irregular': Deformed, triangular, or complex shape which is hard to build on efficiently.\n"
            "   - 'flagpole': Flagpole land / long narrow entrance pathway leading to the main plot (敷地延長/引込線路地).\n"
            "   - 'unknown': Cannot determine from the given images.\n"
            "4. 'plot_shape_description': string in Japanese explaining the land shape evaluation.\n"
            "5. 'maintenance_score': float between 1.0 and 5.0 (structural maintenance quality, paint fade, rust, cleanliness of exterior)\n"
            "6. 'maintenance_comment': string in Japanese summarizing the maintenance status of the exterior.\n"
            "Return ONLY raw JSON, e.g. {\"interior_score\": 4.0, \"layout_score\": 3.5, \"plot_shape_type\": \"regular\", \"plot_shape_description\": \"きれいな長方形の角地で非常に建てやすい形状です。\", \"maintenance_score\": 4.2, \"maintenance_comment\": \"外壁の劣化やクラックは見られず、非常によくメンテナンスされています。\"}"
        )
        
        response = model.generate_content(images_to_send + [prompt])
        text = response.text.strip()
        
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            result = default_result.copy()
            result.update({
                'interior_score': float(data.get('interior_score', 3.5)),
                'layout_score': float(data.get('layout_score', 3.5)),
                'plot_shape_type': str(data.get('plot_shape_type', 'unknown')),
                'plot_shape_description': str(data.get('plot_shape_description', '')),
                'maintenance_score': float(data.get('maintenance_score', 3.5)),
                'maintenance_comment': str(data.get('maintenance_comment', ''))
            })
            return result
            
        logging.warning(f"Failed to parse Gemini response: {text}")
        return default_result
    except Exception as e:
        logging.error(f"Error during Gemini image analysis: {e}")
        return default_result

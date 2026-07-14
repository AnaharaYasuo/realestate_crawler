# -*- coding: utf-8 -*-
import re
import logging
import datetime
from typing import Optional
from difflib import SequenceMatcher
from django.utils import timezone
from package.models.evaluation import PropertyEvaluation

logger = logging.getLogger(__name__)

def normalize_address(address: str) -> str:
    """
    住所の表記揺れを最小限にするための正規化関数。
    - 全角英数字・記号を半角に変換
    - 漢数字をアラビア数字に変換
    - 「丁目」「番」「号」「番地」等をハイフンに統一
    - スペースの排除
    """
    if not address:
        return ""
    
    # 全角英数字を半角に変換
    address = address.translate(str.maketrans(
        '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    ))
    
    # スペースの排除
    address = re.sub(r'[\s　]+', '', address)
    
    # 各種全角ハイフン・ダッシュ・マイナス記号の半角ハイフン置換
    address = re.sub(r'[－ー‐—―〜~−]+', '-', address)
    
    # 漢数字の置換
    kanji_digits = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'}
    for k, v in kanji_digits.items():
        address = address.replace(k, v)
        
    # 「◯丁目◯番◯号」「◯番地◯」をハイフンに変換
    address = re.sub(r'(\d+)丁目', r'\1-', address)
    address = re.sub(r'(\d+)番(?:地|の)?', r'\1-', address)
    address = re.sub(r'(\d+)号', r'\1', address)
    
    # 重複するハイフンをまとめる、末尾のハイフンを削除
    address = re.sub(r'-+', '-', address)
    address = address.strip('-')
    
    return address

def calculate_property_similarity(eval_a: PropertyEvaluation, eval_b: PropertyEvaluation) -> float:
    """
    2つの PropertyEvaluation レコード（および紐づく実データ）の類似度を計算する。
    戻り値: 0.0 (全く異なる) 〜 1.0 (完全に同一) の類似度スコア
    """
    # 同一URLの場合は1.0
    if eval_a.property_url == eval_b.property_url:
        return 1.0
        
    # 物件種別の互換性チェック（マンション・アパート系同士、または戸建て系同士）
    group_a = "building" if eval_a.property_type in ["mansion", "investmentapartment", "tochi"] else "house"
    group_b = "building" if eval_b.property_type in ["mansion", "investmentapartment", "tochi"] else "house"
    if group_a != group_b:
        return 0.0
        
    score = 0.0
    
    # 実データモデルオブジェクトの取得
    # それぞれの評価レコードに紐づく物件実データをモデルから引く
    def get_real_property(eval_rec):
        try:
            from django.apps import apps
            company = eval_rec.company
            ptype = eval_rec.property_type
            
            # company が unknown の場合は、property_type から会社名を逆引きして解決を試みる
            if company == "unknown":
                for c in ["mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1", "mizuho", "odakyu", "afr", "sekisui", "daiwa", "totate", "athome", "homes", "seibu", "keikyu", "sotetsu", "keisei", "daikyo", "rearie", "heim", "sumirin", "keio"]:
                    if ptype.lower().startswith(c):
                        company = c
                        ptype = ptype.lower().replace(c, "")
                        break
            
            company_camel = company.capitalize()
            ptype_camel = ptype.replace("apartment", "Apartment").replace("kodate", "Kodate").replace("mansion", "Mansion").replace("tochi", "Tochi").replace("investment", "Investment")
            # 先頭大文字化の担保
            if len(ptype_camel) > 0:
                ptype_camel = ptype_camel[0].upper() + ptype_camel[1:]
                
            model_name = f"{company_camel}{ptype_camel}"
            
            model_class = apps.get_model('package', model_name)
            return model_class.objects.filter(id=eval_rec.property_id).first()
        except Exception as e:
            logger.debug(f"Failed to load real property data for evaluation {eval_rec.id}: {e}")
            return None

    prop_a = get_real_property(eval_a)
    prop_b = get_real_property(eval_b)
    
    if not prop_a or not prop_b:
        return 0.0

    # 1. 住所類似度 (最大 0.5)
    addr_a = normalize_address(prop_a.address)
    addr_b = normalize_address(prop_b.address)
    if addr_a and addr_b:
        if addr_a == addr_b:
            score += 0.50
        else:
            # difflib を用いた部分類似度算出 (市区町村以降の番地類似を考慮)
            match_ratio = SequenceMatcher(None, addr_a, addr_b).ratio()
            if match_ratio >= 0.85:
                score += 0.35
            elif match_ratio >= 0.70:
                score += 0.20

    # 2. 面積類似度 (最大 0.3)
    # 建物面積(tatemonoMenseki) または 専有面積(senyuMenseki) を取得
    area_a = float(getattr(prop_a, "tatemonoMenseki", 0) or getattr(prop_a, "senyuMenseki", 0) or 0)
    area_b = float(getattr(prop_b, "tatemonoMenseki", 0) or getattr(prop_b, "senyuMenseki", 0) or 0)
    
    if area_a > 0 and area_b > 0:
        diff_ratio = abs(area_a - area_b) / max(area_a, area_b)
        if diff_ratio <= 0.01:
            score += 0.30
        elif diff_ratio <= 0.03:
            score += 0.20
        elif diff_ratio <= 0.07:
            score += 0.10

    # 3. 価格類似度 (最大 0.2)
    price_a = float(prop_a.price if prop_a.price else 0)
    price_b = float(prop_b.price if prop_b.price else 0)
    if price_a > 0 and price_b > 0:
        diff_ratio = abs(price_a - price_b) / max(price_a, price_b)
        if diff_ratio <= 0.01:
            score += 0.20
        elif diff_ratio <= 0.03:
            score += 0.15
        elif diff_ratio <= 0.07:
            score += 0.10
        elif diff_ratio <= 0.15:
            score += 0.05

    # 4. 築年月類似度 (最大 0.1)
    date_a = getattr(prop_a, "chikunengetsu", None)
    date_b = getattr(prop_b, "chikunengetsu", None)
    if date_a and date_b and date_a == date_b:
        score += 0.10
    else:
        str_a = getattr(prop_a, "chikunengetsuStr", "")
        str_b = getattr(prop_b, "chikunengetsuStr", "")
        if str_a and str_b and str_a == str_b:
            score += 0.10

    return score

def find_duplicate_property(new_eval: PropertyEvaluation) -> Optional[PropertyEvaluation]:
    """
    新しく登録された PropertyEvaluation に対して、DB内に同一とみなせる類似物件レコードが存在するか検索する。
    - 直近に作成された最大1000件のレコードを対象
    - 類似度スコアが 0.85 以上のものを重複と判定
    """
    candidates = PropertyEvaluation.objects.exclude(id=new_eval.id).order_by('-id')[:1000]
    
    for cand in candidates:
        similarity = calculate_property_similarity(new_eval, cand)
        if similarity >= 0.85:
            logger.info(f"Duplicate property detected: {new_eval.property_url} is duplicate of {cand.property_url} (Similarity: {similarity:.2f})")
            return cand
            
    return None

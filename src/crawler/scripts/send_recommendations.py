# -*- coding: utf-8 -*-
import os
import sys
import logging

# Django設定のロード
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from django.db import transaction
from package.models.evaluation import PropertyEvaluation
from package.utils.slack import send_slack_message
from asgiref.sync import async_to_sync
import time

# 各社モデルのインポート (物件名や価格の取得用)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def get_property_record(eval_record):
    """URLに対応する各社テーブルの物件レコードを動的かつ堅牢に取得する"""
    from django.apps import apps
    company = eval_record.company.lower()
    ptype = eval_record.property_type.lower().replace("_", "")
    
    for model in apps.get_models():
        m_name = model.__name__.lower()
        if m_name.startswith(company):
            rest = m_name[len(company):]
            if rest == ptype or rest == ptype.replace("invest", "investment"):
                return model.objects.filter(pageUrl=eval_record.property_url).first()
    return None

def clean_val(val):
    if val is None:
        return "-"
    s = str(val).strip()
    if s.lower() in ["none", ""]:
        return "-"
    return s

def get_prop_dates(prop):
    # クロール日時
    crawl_dt = getattr(prop, "inputDateTime", None) or getattr(prop, "inputDate", None)
    crawl_str = crawl_dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(crawl_dt, "strftime") else str(crawl_dt) if crawl_dt else "-"
    
    # 公開/更新日時
    pub_dt = None
    for attr in ["updateDateTime", "updateDate", "publishedDateTime", "publishedDate", "published_at", "updated_at"]:
        if hasattr(prop, attr):
            val = getattr(prop, attr)
            if val:
                pub_dt = val
                break
    if not pub_dt:
        pub_dt = getattr(prop, "inputDate", None)
    
    pub_str = pub_dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(pub_dt, "strftime") else str(pub_dt) if pub_dt else "-"
    return pub_str, crawl_str

def send_recommendations():
    logging.info("Scanning for new hot recommendation properties to send via Slack...")
    
    # Slack通知未送信の評価レコードを抽出
    candidates = PropertyEvaluation.objects.filter(is_slack_notified=False)
    
    sent_count = 0
    
    for eval_rec in candidates:
        prop = get_property_record(eval_rec)
        if not prop:
            continue
            
        asking_price = getattr(prop, "price", 0)
        if not asking_price or asking_price <= 0:
            continue
            
        asking_price_man = asking_price // 10000
        
        pred_price = float(eval_rec.second_stage_predicted_price or eval_rec.first_stage_predicted_price or 0.0)
        
        is_recommend = False
        reason = ""
        
        # 判定条件1: アパート（投資用）
        ptype_lower = eval_rec.property_type.lower().replace("_", "")
        if ptype_lower in ["investapartment", "investmentapartment", "apartment", "investment"]:
            score = eval_rec.investment_score or eval_rec.total_investment_score or 0.0
            if score >= 60.0:
                is_recommend = True
                reason = f"【高利回り・優良融資スコア: {score:.1f}点】"
                
        # 判定条件2: 居住用 (割安度 15% 以上、ただし40%以上の極端な乖離は2σ乖離の予測エラーとして除外)
        elif pred_price > 0:
            discount_pct = (pred_price - asking_price_man) / pred_price * 100.0
            if discount_pct >= 40.0 or discount_pct <= -40.0:
                logging.warning(f"Skipping alert (2-sigma error suspect): Property {prop.pageUrl} has extreme prediction gap of {discount_pct:.1f}% (Predicted: {pred_price}万円, Asking: {asking_price_man}万円)")
            elif discount_pct >= 15.0:
                is_recommend = True
                reason = f"【市場予測価格より {discount_pct:.1f}% 割安（お宝物件！）】"
                
        if not is_recommend:
            # 基準を満たさないものはスキップ（通知済フラグは立てない）
            continue
            
        # Slack送信メッセージ構築
        ptype_jp = {
            "mansion": "中古マンション",
            "kodate": "中古戸建",
            "tochi": "土地",
            "invest_kodate": "戸建（投資用）",
            "invest_apartment": "一棟アパート",
            "apartment": "一棟アパート",
            "investmentkodate": "戸建（投資用）",
            "investmentapartment": "一棟アパート",
            "investment": "投資用物件"
        }.get(eval_rec.property_type, eval_rec.property_type)
        
        p_name = clean_val(getattr(prop, "propertyName", "不明な物件名"))
        address = clean_val(getattr(prop, "address", getattr(prop, "address1", "")))
        
        # アクセス情報の不要な二重空白の除去と None フィルタリング
        access_parts = [p for p in [clean_val(getattr(prop, "railway1", "")), clean_val(getattr(prop, "station1", "")), clean_val(getattr(prop, "railwayWalkMinute1Str", ""))] if p and p != "-"]
        access = " ".join(access_parts)
        if not access:
            access = clean_val(getattr(prop, "traffic", ""))
            
        # 面積情報構築
        area_parts = []
        senyu = clean_val(getattr(prop, "senyuMensekiStr", ""))
        tochi = clean_val(getattr(prop, "tochiMensekiStr", ""))
        tate = clean_val(getattr(prop, "tatemonoMensekiStr", ""))
        if senyu != "-": area_parts.append(f"専有面積: {senyu}")
        if tochi != "-": area_parts.append(f"土地面積: {tochi}")
        if tate != "-": area_parts.append(f"建物面積: {tate}")
        area_info = " / ".join(area_parts) if area_parts else "-"
            
        chikunen = clean_val(getattr(prop, "chikunengetsuStr", getattr(prop, "chikunenki", "")))
        madori = clean_val(getattr(prop, "madori", ""))
        
        # 建ぺい率・容積率の取得
        kenpei = clean_val(getattr(prop, "kenpeiStr", getattr(prop, "kenpei", "")))
        youseki = clean_val(getattr(prop, "yousekiStr", getattr(prop, "youseki", "")))
        
        # 公開日・クロール日時の取得
        pub_date, crawled_date = get_prop_dates(prop)
        
        msg = (
            f"🏆 [お宝物件検出] {reason}\n"
            f"物件名: {p_name} ({ptype_jp})\n"
            f"売出価格: {asking_price_man}万円\n"
            f"理論予測価格: {int(pred_price)}万円\n"
            f"【物件詳細】\n"
            f"住所: {address}\n"
            f"アクセス: {access}\n"
            f"面積: {area_info}\n"
            f"間取り: {madori}\n"
            f"築年月: {chikunen}\n"
            f"建ぺい率 / 容積率: {kenpei} / {youseki}\n"
        )
        
        if eval_rec.property_type in ["invest_apartment", "apartment", "invest_kodate", "investmentapartment", "investmentkodate", "investment"]:
            msg += (
                f"想定積算価格: {clean_val(eval_rec.estimated_sekisan_price)}万円\n"
                f"年間キャッシュフロー: {clean_val(eval_rec.cash_flow)}万円/年 (DSCR: {clean_val(eval_rec.dscr)})\n"
            )
            
        msg += (
            f"情報公開日: {pub_date} | クロール日時: {crawled_date}\n"
            f"詳細URL: {eval_rec.property_url}\n"
        )
        
        # 物件種別ごとの投稿先チャンネル定義 (お宝物件用: デフォルトは goodproperty-* チャネル)
        channel_id = os.getenv("SLACK_RECOMMEND_CHANNEL_ID") or os.getenv("SLACK_CHANNEL_ID")
        ptype_clean = eval_rec.property_type.lower().replace("_", "")
        
        if ptype_clean == "mansion":
            channel_id = os.getenv("SLACK_RECOMMEND_MANSION", "goodproperty-mansion")
        elif ptype_clean == "kodate":
            channel_id = os.getenv("SLACK_RECOMMEND_KODATE", "goodproperty-kodate")
        elif ptype_clean == "tochi":
            channel_id = os.getenv("SLACK_RECOMMEND_TOCHI", "goodproperty-tochi")
        elif ptype_clean in ["investapartment", "investmentapartment", "apartment"]:
            channel_id = os.getenv("SLACK_RECOMMEND_INVEST_APARTMENT", "goodproperty-invest-apartment")
        elif ptype_clean in ["investkodate", "investmentkodate"]:
            channel_id = os.getenv("SLACK_RECOMMEND_INVEST_KODATE", "goodproperty-invest-kodate")
        elif ptype_clean == "investment":
            # generic な investment の場合はクラス名や物件名で分類
            model_class_name = prop.__class__.__name__.lower()
            prop_name_lower = p_name.lower()
            is_apartment = False
            if "apartment" in model_class_name or "アパート" in prop_name_lower or "マンション" in prop_name_lower or "一棟" in prop_name_lower:
                is_apartment = True
                
            if is_apartment:
                channel_id = os.getenv("SLACK_RECOMMEND_INVEST_APARTMENT", "goodproperty-invest-apartment")
            else:
                channel_id = os.getenv("SLACK_RECOMMEND_INVEST_KODATE", "goodproperty-invest-kodate")
 
        logging.info(f"Sending recommendation for {p_name} ({eval_rec.property_url}) to {channel_id}")
        
        # 実際のSlack送信実行
        success = async_to_sync(send_slack_message)(msg, channel=channel_id)
        if success:
            with transaction.atomic():
                eval_rec.is_slack_notified = True
                eval_rec.save()
            sent_count += 1
            # Slack APIレートリミット対策のための短いスリープ
            time.sleep(1.0)
            
    logging.info(f"Recommendation sending completed. Sent: {sent_count} properties.")
 
def main():
    send_recommendations()
 
if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
import os
import sys
import logging
import datetime
import time
from asgiref.sync import async_to_sync

_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env
        break
    _cur = _parent

from django.db import models, transaction
from django.utils import timezone
from django.apps import apps
from package.models.evaluation import PropertyEvaluation
from package.utils.slack import send_slack_message

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

LABEL_INVEST_APARTMENT = "一棟アパート"
LABEL_INVEST_KODATE = "戸建（投資用）"

def get_property_record(eval_record):
    """URLに対応する各社テーブルの物件レコードを動的かつ堅牢に取得する"""
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

def normalize_asking_price_man(asking_price):
    """
    売り出し価格を「万円単位」に正規化する。
    - 円単位（例: 45,900,000円）の場合: // 10000 して 4590 とする
    - 既に万円単位（例: 4590万円）の場合: そのまま 4590 とする（Issue #235）
    """
    if not asking_price or asking_price <= 0:
        return 0
    try:
        val = int(asking_price)
        return val // 10000 if val > 500000 else val
    except (ValueError, TypeError):
        return 0


def get_prop_dates(prop):
    crawl_dt = getattr(prop, "inputDateTime", None) or getattr(prop, "inputDate", None)
    if hasattr(crawl_dt, "strftime"):
        crawl_str = crawl_dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        crawl_str = str(crawl_dt) if crawl_dt else "-"
    
    pub_dt = None
    for attr in ["updateDateTime", "updateDate", "publishedDateTime", "publishedDate", "published_at", "updated_at"]:
        if hasattr(prop, attr):
            val = getattr(prop, attr)
            if val:
                pub_dt = val
                break
    if not pub_dt:
        pub_dt = getattr(prop, "inputDate", None)
    
    if hasattr(pub_dt, "strftime"):
        pub_str = pub_dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        pub_str = str(pub_dt) if pub_dt else "-"
    return pub_str, crawl_str

def _evaluate_investment_candidate(eval_rec) -> tuple:
    score = eval_rec.investment_score or eval_rec.total_investment_score or 0.0
    if score >= 80.0:
        return True, f"【高利回り・優良融資スコア: {score:.1f}点】", score
    return False, "", 0.0

def _evaluate_residential_candidate(prop, asking_price_man: int, pred_price: float) -> tuple:
    if pred_price <= 0 or asking_price_man <= 0:
        return False, "", 0.0
    discount_pct = (pred_price - asking_price_man) / pred_price * 100.0
    if discount_pct >= 35.0 or discount_pct <= -35.0:
        logging.warning(
            f"Skipping alert (2-sigma error suspect): Property {prop.pageUrl} has extreme prediction gap of {discount_pct:.1f}% (Predicted: {pred_price:.0f}万円, Asking: {asking_price_man:.0f}万円)"
        )
        return False, "", 0.0
    if discount_pct >= 20.0:
        return True, f"【市場予測価格より {discount_pct:.1f}% 割安（超お宝物件！）】", discount_pct
    return False, "", 0.0

def _evaluate_candidate(eval_rec, prop) -> tuple:
    asking_price = getattr(prop, "price", 0)
    if not asking_price or asking_price <= 0:
        return False, "", 0.0

    ptype_lower = eval_rec.property_type.lower().replace("_", "")
    if ptype_lower in ["investapartment", "investmentapartment", "apartment", "investment"]:
        return _evaluate_investment_candidate(eval_rec)

    asking_price_man = normalize_asking_price_man(asking_price)
    pred_price = float(eval_rec.second_stage_predicted_price or eval_rec.first_stage_predicted_price or 0.0)
    return _evaluate_residential_candidate(prop, asking_price_man, pred_price)

def _get_target_slack_channel(eval_rec, prop, p_name: str) -> str:
    ptype_clean = eval_rec.property_type.lower().replace("_", "")
    channel_map = {
        "mansion": ("SLACK_RECOMMEND_MANSION", "goodproperty-mansion"),
        "kodate": ("SLACK_RECOMMEND_KODATE", "goodproperty-kodate"),
        "tochi": ("SLACK_RECOMMEND_TOCHI", "goodproperty-tochi"),
        "investapartment": ("SLACK_RECOMMEND_INVEST_APARTMENT", "goodproperty-invest-apartment"),
        "investmentapartment": ("SLACK_RECOMMEND_INVEST_APARTMENT", "goodproperty-invest-apartment"),
        "apartment": ("SLACK_RECOMMEND_INVEST_APARTMENT", "goodproperty-invest-apartment"),
        "investkodate": ("SLACK_RECOMMEND_INVEST_KODATE", "goodproperty-invest-kodate"),
        "investmentkodate": ("SLACK_RECOMMEND_INVEST_KODATE", "goodproperty-invest-kodate"),
    }
    if ptype_clean in channel_map:
        env_var, default_ch = channel_map[ptype_clean]
        return os.getenv(env_var, default_ch)

    if ptype_clean == "investment":
        model_class_name = prop.__class__.__name__.lower()
        prop_name_lower = p_name.lower()
        if any(k in model_class_name or k in prop_name_lower for k in ["apartment", "アパート", "マンション", "一棟"]):
            return os.getenv("SLACK_RECOMMEND_INVEST_APARTMENT", "goodproperty-invest-apartment")
        return os.getenv("SLACK_RECOMMEND_INVEST_KODATE", "goodproperty-invest-kodate")

    return os.getenv("SLACK_RECOMMEND_CHANNEL_ID") or os.getenv("SLACK_CHANNEL_ID") or "property_alert"

def _format_access_and_area(prop) -> tuple:
    access_parts = [
        p for p in [
            clean_val(getattr(prop, "railway1", "")),
            clean_val(getattr(prop, "station1", "")),
            clean_val(getattr(prop, "railwayWalkMinute1Str", ""))
        ] if p and p != "-"
    ]
    access = " ".join(access_parts) if access_parts else clean_val(getattr(prop, "traffic", ""))

    area_parts = []
    senyu = clean_val(getattr(prop, "senyuMensekiStr", ""))
    tochi = clean_val(getattr(prop, "tochiMensekiStr", ""))
    tate = clean_val(getattr(prop, "tatemonoMensekiStr", ""))
    if senyu != "-":
        area_parts.append(f"専有面積: {senyu}")
    if tochi != "-":
        area_parts.append(f"土地面積: {tochi}")
    if tate != "-":
        area_parts.append(f"建物面積: {tate}")
    area_info = " / ".join(area_parts) if area_parts else "-"
    return access, area_info

def _build_recommendation_msg(eval_rec, prop, reason: str, p_name: str) -> str:
    asking_price = getattr(prop, "price", 0)
    asking_price_man = normalize_asking_price_man(asking_price)
    pred_price = float(eval_rec.second_stage_predicted_price or eval_rec.first_stage_predicted_price or 0.0)

    ptype_jp = {
        "mansion": "中古マンション",
        "kodate": "中古戸建",
        "tochi": "土地",
        "invest_kodate": LABEL_INVEST_KODATE,
        "invest_apartment": LABEL_INVEST_APARTMENT,
        "apartment": LABEL_INVEST_APARTMENT,
        "investmentkodate": LABEL_INVEST_KODATE,
        "investmentapartment": LABEL_INVEST_APARTMENT,
        "investment": "投資用物件"
    }.get(eval_rec.property_type, eval_rec.property_type)

    address = clean_val(getattr(prop, "address", getattr(prop, "address1", "")))
    access, area_info = _format_access_and_area(prop)
    chikunen = clean_val(getattr(prop, "chikunengetsuStr", getattr(prop, "chikunenki", "")))
    madori = clean_val(getattr(prop, "madori", ""))
    kenpei = clean_val(getattr(prop, "kenpeiStr", getattr(prop, "kenpei", "")))
    youseki = clean_val(getattr(prop, "yousekiStr", getattr(prop, "youseki", "")))
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
    return msg

def _dispatch_single_recommendation(eval_rec, prop, reason: str) -> bool:
    p_name = clean_val(getattr(prop, "propertyName", "不明な物件名"))
    msg = _build_recommendation_msg(eval_rec, prop, reason, p_name)
    channel_id = _get_target_slack_channel(eval_rec, prop, p_name)

    logging.info(f"Sending recommendation for {p_name} ({eval_rec.property_url}) to {channel_id}")
    success = async_to_sync(send_slack_message)(msg, channel=channel_id)
    if success:
        with transaction.atomic():
            eval_rec.is_slack_notified = True
            eval_rec.save()
        time.sleep(1.0)
        return True
    return False

def _fetch_recommendation_candidates():
    threshold_48h = timezone.now() - datetime.timedelta(hours=48)
    candidates = PropertyEvaluation.objects.filter(
        is_slack_notified=False
    ).filter(
        models.Q(analyzed_at__gte=threshold_48h) | models.Q(analyzed_at__isnull=True)
    )
    if not candidates.exists():
        return PropertyEvaluation.objects.filter(is_slack_notified=False).order_by('-id')[:200]
    return candidates

def send_recommendations():
    logging.info("Scanning for new hot recommendation properties to send via Slack...")
    candidates = _fetch_recommendation_candidates()
    matched_candidates = []

    for eval_rec in candidates:
        prop = get_property_record(eval_rec)
        if not prop:
            continue
        is_rec, reason, priority = _evaluate_candidate(eval_rec, prop)
        if is_rec:
            matched_candidates.append((priority, eval_rec, prop, reason))

    matched_candidates.sort(key=lambda x: x[0], reverse=True)
    top_candidates = matched_candidates[:15]
    logging.info(f"Filtered {len(matched_candidates)} recommendation candidates down to top {len(top_candidates)} items.")

    sent_count = 0
    for _, eval_rec, prop, reason in top_candidates:
        if _dispatch_single_recommendation(eval_rec, prop, reason):
            sent_count += 1

    logging.info(f"Recommendation sending completed. Sent: {sent_count} properties.")
 
def main():
    send_recommendations()
 
if __name__ == "__main__":
    main()

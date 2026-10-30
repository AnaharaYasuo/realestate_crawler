# ruff: noqa: E402, F401
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

from django.db import models, transaction, close_old_connections, connections
from django.utils import timezone
from django.apps import apps
from package.models.evaluation import PropertyEvaluation
from package.utils.slack import send_slack_message, send_dev_report
from package.utils.batch_metrics import BatchMetrics, format_timestamp_jst
from package.utils.db_timeouts import bound_mysql_timeouts

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def _notify_status(msg: str) -> None:
    try:
        async_to_sync(send_dev_report)(msg)
    except Exception as e:
        logger.warning("Failed to send recommendation status report: %s", e)

LABEL_INVEST_APARTMENT = "一棟アパート"
LABEL_INVEST_KODATE = "戸建（投資用）"


def batch_resolve_properties(eval_records: list) -> dict:
    """
    複数のPropertyEvaluationレコードに対応する実物件レコードを一括照会する。
    1件ずつの個別クエリ発行によるN+1問題および長時間クエリタイムアウトを防止する。
    戻り値: {property_url: property_record}
    """
    from collections import defaultdict
    model_groups = defaultdict(list)
    resolved = {}

    for rec in eval_records:
        if not rec.property_url:
            continue
        company = (rec.company or "").lower()
        ptype = (rec.property_type or "").lower().replace("_", "")
        model_groups[(company, ptype)].append(rec.property_url)

    all_models = apps.get_models()
    for (company, ptype), urls in model_groups.items():
        matched_model = None
        for model in all_models:
            m_name = model.__name__.lower()
            if m_name.startswith(company):
                rest = m_name[len(company):]
                if rest == ptype or rest == ptype.replace("invest", "investment"):
                    matched_model = model
                    break
        if matched_model:
            chunk_size = 500
            for i in range(0, len(urls), chunk_size):
                sub_urls = urls[i:i + chunk_size]
                try:
                    for obj in matched_model.objects.filter(pageUrl__in=sub_urls):
                        resolved[obj.pageUrl] = obj
                except Exception as e:
                    logger.warning("Error batch resolving properties for %s: %s", matched_model.__name__, e)
    return resolved

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


def _format_dt(dt) -> str:
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt) if dt else "-"


def _find_pub_dt(prop):
    for attr in ("updateDateTime", "updateDate", "publishedDateTime", "publishedDate", "published_at", "updated_at"):
        val = getattr(prop, attr, None)
        if val:
            return val
    return getattr(prop, "inputDate", None)


def get_prop_dates(prop):
    crawl_dt = getattr(prop, "inputDateTime", None) or getattr(prop, "inputDate", None)
    crawl_str = _format_dt(crawl_dt)
    pub_dt = _find_pub_dt(prop)
    pub_str = _format_dt(pub_dt)
    return pub_str, crawl_str

INVESTMENT_PROPERTY_TYPES = {
    "investapartment",
    "investmentapartment",
    "apartment",
    "invest_apartment",
    "investkodate",
    "investmentkodate",
    "invest_kodate",
    "investment",
    "investmentbuilding",
}

def is_investment_type(property_type: str | None) -> bool:
    if not property_type:
        return False
    ptype_clean = property_type.lower().replace("_", "")
    return ptype_clean in INVESTMENT_PROPERTY_TYPES or "invest" in ptype_clean

def _evaluate_investment_candidate(eval_rec, prop=None) -> tuple:
    asking_price = getattr(prop, "price", 0) if prop else 0
    asking_price_man = normalize_asking_price_man(asking_price)
    pred_price = float(eval_rec.second_stage_predicted_price or eval_rec.first_stage_predicted_price or 0.0)

    # 2-sigma / 安全弁ガード: 予測価格と売出価格の極端な乖離（3倍超または0.33倍未満）は異常値として除外 (Issue #1116)
    if pred_price > 0 and asking_price_man > 0:
        price_ratio = pred_price / asking_price_man
        if price_ratio > 3.0 or price_ratio < 0.33:
            logger.warning(
                f"Skipping investment alert (extreme prediction gap): Property {getattr(prop, 'pageUrl', '')} "
                f"ratio {price_ratio:.1f}x (Predicted: {pred_price:.0f}万円, Asking: {asking_price_man:.0f}万円)"
            )
            return False, "", 0.0

    score = eval_rec.total_investment_score or eval_rec.investment_score or 0.0
    if score >= 70.0:
        return True, f"【高利回り・優良融資スコア: {score:.1f}点】", float(score)

    if pred_price > 0 and asking_price_man > 0:
        discount_pct = (pred_price - asking_price_man) / pred_price * 100.0
        if -35.0 <= discount_pct <= 35.0 and discount_pct >= 20.0:
            calc_priority = 70.0 + discount_pct
            return True, f"【市場予測価格より {discount_pct:.1f}% 割安（投資お宝物件！）】", calc_priority

    return False, "", 0.0

def _evaluate_residential_candidate(prop, asking_price_man: int, pred_price: float) -> tuple:
    if pred_price <= 0 or asking_price_man <= 0:
        return False, "", 0.0
    discount_pct = (pred_price - asking_price_man) / pred_price * 100.0
    if discount_pct >= 35.0 or discount_pct <= -35.0:
        logger.warning(
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

    if is_investment_type(eval_rec.property_type):
        return _evaluate_investment_candidate(eval_rec, prop)

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

    return os.getenv("SLACK_RECOMMEND_CHANNEL_ID") or os.getenv("SLACK_DEV_CHANNEL") or "dev-agent"

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
        f"理論予測価格: {int(pred_price) if pred_price > 0 else '-'}万円\n" if pred_price > 0 else f"理論予測価格: -\n"
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

    logger.info(f"Sending recommendation for {p_name} ({eval_rec.property_url}) to {channel_id}")
    success = async_to_sync(send_slack_message)(msg, channel=channel_id)
    if success:
        for attempt in range(3):
            try:
                with transaction.atomic():
                    eval_rec.is_slack_notified = True
                    eval_rec.save()
                break
            except Exception as dbe:
                logger.warning(f"DB update failed on recommendation notify (attempt {attempt+1}/3): {dbe}")
                close_old_connections()
                connections.close_all()
                if attempt == 2:
                    raise
                time.sleep(1.0)
        time.sleep(1.0)
        return True
    return False

def _fetch_recommendation_candidates(limit: int = 3000):
    """
    全種別の候補をバランスよく取得する (Issue #1087)
    住居系（マンション、戸建て、土地）と投資系（区分、一棟、戸建て）のそれぞれについて
    最新の未通知・公開物件を並行してロードし、特定種別による枠の独占を防ぐ。
    """
    base_qs = PropertyEvaluation.objects.filter(
        is_slack_notified=False,
        is_published=True,
        needs_recrawl=False,
    )
    all_types = [
        'mansion', 'kodate', 'tochi',
        'investmentapartment', 'investment', 'apartment',
        'investmentkodate', 'invest_kodate', 'invest_apartment', 'investmentbuilding'
    ]
    per_type_limit = max(100, limit // len(all_types))
    combined_candidates = []
    seen_ids = set()

    for ptype in all_types:
        qs_type = base_qs.filter(property_type=ptype).order_by('-id')[:per_type_limit]
        for rec in qs_type:
            if rec.id not in seen_ids:
                seen_ids.add(rec.id)
                combined_candidates.append(rec)

    if len(combined_candidates) < limit:
        remaining_limit = limit - len(combined_candidates)
        fallback_qs = base_qs.exclude(id__in=seen_ids).order_by('-id')[:remaining_limit]
        combined_candidates.extend(fallback_qs)

    return combined_candidates

def _select_balanced_recommendations(
    matched_candidates: list,
    quota: int = 15,
    min_investment_quota: int = 3,
    max_per_type: int = 5,
) -> list:
    """
    優先度順に並べ替えつつ、住居系・投資系のバランスおよび特定種別の独占を防止する (Issue #1087)
    - 投資物件を最低 min_investment_quota 件確保
    - 住居系（マンション、戸建て、土地）もバランスよく選定
    - 単一種別（例: investmentkodate のみ）の上限を max_per_type 件に制限
    """
    matched_candidates.sort(key=lambda x: x[0], reverse=True)
    if len(matched_candidates) <= quota:
        return matched_candidates

    inv_candidates = [c for c in matched_candidates if is_investment_type(c[1].property_type)]
    res_candidates = [c for c in matched_candidates if not is_investment_type(c[1].property_type)]

    selected = []
    type_counts = {}

    def can_add(c):
        ptype = c[1].property_type.lower().replace("_", "")
        return type_counts.get(ptype, 0) < max_per_type

    def add_candidate(c):
        selected.append(c)
        ptype = c[1].property_type.lower().replace("_", "")
        type_counts[ptype] = type_counts.get(ptype, 0) + 1

    # 1. 投資物件枠を確保
    for c in inv_candidates:
        if len([x for x in selected if is_investment_type(x[1].property_type)]) >= min_investment_quota:
            break
        if can_add(c):
            add_candidate(c)

    # 2. 住居系枠を確保（最低3件）
    min_res_quota = min(3, len(res_candidates))
    for c in res_candidates:
        if len([x for x in selected if not is_investment_type(x[1].property_type)]) >= min_res_quota:
            break
        if can_add(c):
            add_candidate(c)

    # 3. 残り枠を全体優先度順に上限（max_per_type）に配慮して補充
    used_ids = {c[1].id for c in selected}
    for c in matched_candidates:
        if len(selected) >= quota:
            break
        if c[1].id not in used_ids and can_add(c):
            add_candidate(c)
            used_ids.add(c[1].id)

    # 上限に達しなかった場合のフェールセーフ（上限緩和して残り枠を埋める）
    if len(selected) < quota:
        for c in matched_candidates:
            if len(selected) >= quota:
                break
            if c[1].id not in used_ids:
                selected.append(c)
                used_ids.add(c[1].id)

    selected.sort(key=lambda x: x[0], reverse=True)
    return selected

def send_recommendations():
    close_old_connections()
    connections.close_all()
    bound_mysql_timeouts()
    metrics = BatchMetrics(job_name="Slack Recommendation")
    logger.info("Scanning for new hot recommendation properties to send via Slack...")
    _notify_status("🔍 【お宝物件スクリーニング開始】 未通知の割安物件・高利回り優良物件の抽出を開始します...")

    candidates = _fetch_recommendation_candidates()
    metrics.total_count = len(candidates)
    matched_candidates = []

    prop_lookup = batch_resolve_properties(candidates)

    for eval_rec in candidates:
        prop = prop_lookup.get(eval_rec.property_url) or get_property_record(eval_rec)
        if not prop:
            continue
        is_rec, reason, priority = _evaluate_candidate(eval_rec, prop)
        if is_rec:
            matched_candidates.append((priority, eval_rec, prop, reason))

    if not matched_candidates:
        metrics.finish()
        st_str = format_timestamp_jst(metrics.start_time)
        et_str = format_timestamp_jst(metrics.end_time)
        logger.info("No hot recommendation candidates found. (Scanned: %d, Elapsed: %s)", len(candidates), metrics.duration_str)
        _notify_status(
            f"ℹ️ 【お宝物件通知】 現在配信基準を満たす新規お宝物件はありませんでした (0件)。\n"
            f"• *実行時間*: {st_str} 〜 {et_str} (所要: {metrics.duration_str})\n"
            f"• *スクリーニング*: 対象候補 {len(candidates):,} 件を走査 | 基準合致 0 件"
        )
        banner = metrics.build_log_banner(
            title="Slack Recommendation Batch",
            custom_sections=[
                f"• スクリーニング: 対象候補 {len(candidates):,} 件 | 基準合致 0 件",
            ]
        )
        logger.info("\n" + banner)
        return

    matched_candidates.sort(key=lambda x: x[0], reverse=True)
    top_candidates = _select_balanced_recommendations(matched_candidates, quota=15, min_investment_quota=3)
    logger.info(f"Filtered {len(matched_candidates)} recommendation candidates down to top {len(top_candidates)} items.")
    _notify_status(
        f"🎯 【お宝物件検出】 {len(matched_candidates)} 件の候補物件を検出しました。優先度上位 {len(top_candidates)} 件を各Slackチャンネルへ配信します。"
    )

    sent_count = 0
    channel_counts: dict[str, int] = {}
    for _, eval_rec, prop, reason in top_candidates:
        if _dispatch_single_recommendation(eval_rec, prop, reason):
            sent_count += 1
            metrics.record_processed(1)
            ptype_key = eval_rec.property_type.lower().replace("_", "")
            channel_counts[ptype_key] = channel_counts.get(ptype_key, 0) + 1
        else:
            metrics.record_failed(1)

    metrics.finish()
    logger.info("Recommendation sending completed. Sent: %d properties.", sent_count)
    finish_msg = metrics.build_recommendation_slack_summary(
        channel_counts=channel_counts,
        matched_count=len(matched_candidates),
        quota=len(top_candidates),
    )
    _notify_status(finish_msg)

    channel_breakdown = ", ".join(f"{k}: {v}件" for k, v in sorted(channel_counts.items())) if channel_counts else "なし"
    banner = metrics.build_log_banner(
        title="Slack Recommendation Batch",
        custom_sections=[
            f"• スクリーニング: 対象候補 {len(candidates):,} 件 | 基準合致 {len(matched_candidates):,} 件 | 配信枠 {len(top_candidates)} 件",
            f"• 配信内訳    : {channel_breakdown}",
        ]
    )
    logger.info("\n" + banner)
 
def main():
    send_recommendations()
 
if __name__ == "__main__":
    main()

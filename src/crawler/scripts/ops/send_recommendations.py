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
from package.ml.report_generator import generate_professional_and_danchou_report

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


def _get_property_category(ptype: str | None) -> str:
    """
    物件種別を二段階スクリーニング用の主要4大カテゴリに分類する (Issue #1311)
    - mansion: 区分マンション
    - kodate: 戸建て（実需）
    - tochi: 土地
    - investment: 投資用全般（一棟アパート・マンション、収益戸建て等）
    """
    if not ptype:
        return "other"
    t = ptype.lower().replace("_", "")
    if is_investment_type(t):
        return "investment"
    if "mansion" in t:
        return "mansion"
    if "kodate" in t or "house" in t:
        return "kodate"
    if "tochi" in t or "land" in t:
        return "tochi"
    return "other"


def _rank_by_qualitative_score(eval_rec, ml_priority: float = 0.0) -> float:
    """
    定性レーティング(AAA/AA/A/B)およびML割安度優先度による複合スコアを算出する (Issue #1311)
    AI定性コメント・レーティングを主軸としつつ、ML定量優先度を加味する。
    - AAA: 1000点ベース
    - AA:  800点ベース
    - A:   600点ベース
    - B:   400点ベース
    - その他/未設定: 200点ベース
    """
    rating = getattr(eval_rec, "investment_rating", "") or ""
    rating_scores = {
        "AAA": 1000.0,
        "AA": 800.0,
        "A": 600.0,
        "B": 400.0,
    }
    base_rating_score = rating_scores.get(rating, 200.0)
    # ML優先度（通常 20.0〜50.0 程度）を加算して同レーティング内での順位を決定
    return base_rating_score + float(ml_priority or 0.0)


def _select_two_stage_recommendations(
    candidates_by_category: dict[str, list],
    quota_per_category: int = 5,
) -> list:
    """
    二次スクリーニング（定性評価スコアリング）に基づき、各カテゴリごとに上位 quota_per_category 件を選抜する (Issue #1311)
    戻り値: [(ml_priority, eval_rec, prop, reason), ...] (全体配信リスト)
    """
    final_selected = []
    category_order = ["mansion", "kodate", "tochi", "investment"]

    for cat in category_order:
        cands = candidates_by_category.get(cat, [])
        if not cands:
            continue
        # 定性評価スコア順に降順ソート
        cands.sort(
            key=lambda x: _rank_by_qualitative_score(x[1], ml_priority=x[0]),
            reverse=True,
        )
        selected_for_cat = cands[:quota_per_category]
        final_selected.extend(selected_for_cat)

    return final_selected

def _evaluate_investment_candidate(eval_rec, prop=None) -> tuple:
    asking_price = getattr(prop, "price", 0) if prop else 0
    asking_price_man = normalize_asking_price_man(asking_price)
    pred_price = float(eval_rec.second_stage_predicted_price or eval_rec.first_stage_predicted_price or 0.0)

    # 理論予測価格が未算出（0以下）または売出価格が無効な場合は推奨しない（割安判定必須）
    if pred_price <= 0 or asking_price_man <= 0:
        return False, "", 0.0

    # 2-sigma / 安全弁ガード: 予測価格と売出価格の極端な乖離（3倍超または0.33倍未満）は異常値として除外 (Issue #1116)
    price_ratio = pred_price / asking_price_man
    if price_ratio > 3.0 or price_ratio < 0.33:
        logger.warning(
            f"Skipping investment alert (extreme prediction gap): Property {getattr(prop, 'pageUrl', '')} "
            f"ratio {price_ratio:.1f}x (Predicted: {pred_price:.0f}万円, Asking: {asking_price_man:.0f}万円)"
        )
        return False, "", 0.0

    # 理論価格が売出価格を上回っていること（pred_price > asking_price_man）が絶対前提 (Issue #1175, #1239)
    if pred_price <= asking_price_man:
        logger.info(
            f"Skipping investment alert: Pred price ({pred_price:.0f}万) does not exceed asking price ({asking_price_man:.0f}万)"
        )
        return False, "", 0.0

    # 利回りベース単独での推奨は撤廃し、割安判定（ディスカウント率 20%〜35%）を満たすもののみ推奨 (Issue #1239)
    discount_pct = (pred_price - asking_price_man) / pred_price * 100.0
    if 20.0 <= discount_pct <= 35.0:
        score = eval_rec.total_investment_score or eval_rec.investment_score or 0.0
        calc_priority = 70.0 + discount_pct + (float(score) * 0.1)
        reason = f"【市場予測価格より {discount_pct:.1f}% 割安（投資お宝物件！）】"
        return True, reason, calc_priority

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

def _is_bus_route(prop, index: int) -> bool:
    bus_use = getattr(prop, f"busUse{index}", None)
    if isinstance(bus_use, (int, float)) and bus_use > 0:
        return True
    bus_min = getattr(prop, f"busWalkMinute{index}", None)
    return isinstance(bus_min, (int, float)) and bus_min > 0

def is_bus_access_property(prop) -> bool:
    """全ての有効アクセス経路がバス利用の物件を「バス利用物件」と判定する (Issue #1244)。"""
    routes = [
        i for i in range(1, 6)
        if isinstance(getattr(prop, f"station{i}", None), str) and getattr(prop, f"station{i}").strip()
    ]
    return bool(routes) and all(_is_bus_route(prop, i) for i in routes)

def _evaluate_candidate(eval_rec, prop) -> tuple:
    asking_price = getattr(prop, "price", 0)
    if not asking_price or asking_price <= 0:
        return False, "", 0.0

    # バス利用物件はピックアップ対象外 (Issue #1244)
    if is_bus_access_property(prop):
        logger.info(f"Skipping alert (bus access property): {getattr(prop, 'pageUrl', '')}")
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

def _format_single_access(prop, index: int) -> str:
    r = clean_val(getattr(prop, f"railway{index}", ""))
    s = clean_val(getattr(prop, f"station{index}", ""))
    w = clean_val(getattr(prop, f"railwayWalkMinute{index}Str", ""))
    if w == "-":
        w_num = getattr(prop, f"railwayWalkMinute{index}", None)
        w = str(w_num) if w_num else "-"
    if s == "-":
        return ""

    transit_parts = []
    if r != "-":
        transit_parts.append(r)
    transit_parts.append(s)

    bus_use = getattr(prop, f"busUse{index}", 0)
    bus_min = clean_val(getattr(prop, f"busWalkMinute{index}Str", ""))
    if bus_min == "-":
        bus_min = clean_val(getattr(prop, f"busWalkMinute{index}", ""))
    bus_stop = clean_val(getattr(prop, f"busStation{index}", ""))

    if bus_use and bus_min != "-":
        bus_desc = f"バス{bus_min}分"
        if bus_stop != "-":
            bus_desc += f"(停 {bus_stop})"
        transit_parts.append(bus_desc)

    if w != "-":
        transit_parts.append(_format_walk_text(w))

    return " ".join(transit_parts).strip()


def _format_walk_text(w) -> str:
    """徒歩分数を「徒歩N分」形式に正規化する (数値のみの場合は「分」を付与)"""
    text = str(w).strip()
    if not text.startswith("徒歩"):
        text = f"徒歩{text}"
    if text[-1].isdigit():
        text += "分"
    return text


def _format_access_and_area(prop) -> tuple:
    # 複数路線・最寄り駅の包括的フォールバック抽出
    access_parts = []
    for i in range(1, 4):
        part = _format_single_access(prop, i)
        if part:
            access_parts.append(part)

    if access_parts:
        access = " / ".join(access_parts)
    else:
        traffic_val = clean_val(getattr(prop, "traffic", ""))
        access = traffic_val if traffic_val != "-" else "最寄り駅情報なし"

    area_parts = []
    senyu = clean_val(getattr(prop, "senyuMensekiStr", ""))
    tochi = clean_val(getattr(prop, "tochiMensekiStr", ""))
    tate = clean_val(getattr(prop, "tatemonoMensekiStr", ""))
    if senyu != "-":
        area_parts.append(f"専有: {senyu}")
    if tochi != "-":
        area_parts.append(f"土地: {tochi}")
    if tate != "-":
        area_parts.append(f"建物: {tate}")
    area_info = " / ".join(area_parts) if area_parts else "-"
    return access, area_info

def _extract_property_display_info(prop, eval_rec) -> tuple[str, int, float, str, str]:
    """物件表示用の共通情報（ptype_jp, asking_price_man, pred_price, address, access）を抽出する"""
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

    addr_parts = [clean_val(getattr(prop, f"address{i}", "")) for i in ["", "1", "2", "3", "Kyoto"]]
    addr_valid = [p for p in addr_parts if p and p != "-"]
    address = " ".join(addr_valid) if addr_valid else "住所情報なし"

    access, _ = _format_access_and_area(prop)
    return ptype_jp, asking_price_man, pred_price, address, access


def _build_recommendation_msg(eval_rec, prop, reason: str, p_name: str, report_data: dict | None = None) -> str:
    ptype_jp, asking_price_man, pred_price, address, access = _extract_property_display_info(prop, eval_rec)
    _, area_info = _format_access_and_area(prop)
    chikunen = clean_val(getattr(prop, "chikunengetsuStr", getattr(prop, "chikunenki", "")))
    madori = clean_val(getattr(prop, "madori", ""))
    kenpei = clean_val(getattr(prop, "kenpeiStr", getattr(prop, "kenpei", "")))
    youseki = clean_val(getattr(prop, "yousekiStr", getattr(prop, "youseki", "")))
    pub_date, crawled_date = get_prop_dates(prop)

    # 割安金額と割安率の算出
    diff_man = int(pred_price - asking_price_man) if pred_price > 0 else 0
    discount_pct = (pred_price - asking_price_man) / pred_price * 100.0 if pred_price > 0 else 0.0

    # レポートが渡されていない場合は生成、渡されている場合は再利用 (Issue #1314)
    if report_data is None:
        report_data = generate_professional_and_danchou_report(
            eval_rec=eval_rec,
            prop=prop,
            ptype_jp=ptype_jp,
            asking_price_man=asking_price_man,
            pred_price=pred_price,
            address=address,
            access=access
        )

    rating_str = f" [{report_data.get('investment_rating')}]" if report_data and report_data.get("investment_rating") else ""

    msg = (
        f"🏆 [お宝物件検出]{rating_str} {reason}\n"
        f"物件名: {p_name} ({ptype_jp})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 価格・割安度（3面アプローチ）\n"
        f"・売出価格: {asking_price_man}万円\n"
        f"・理論予測価格: {int(pred_price) if pred_price > 0 else '-'}万円\n"
    )
    if pred_price > 0:
        msg += f"・割安度: -{diff_man}万円 ({discount_pct:.1f}% 割安)\n"

    if eval_rec.estimated_sekisan_price:
        msg += f"・想定積算価格: {clean_val(eval_rec.estimated_sekisan_price)}万円\n"
    if eval_rec.cash_flow:
        msg += f"・年間CF: {clean_val(eval_rec.cash_flow)}万円/年 (DSCR: {clean_val(eval_rec.dscr)})\n"

    msg += (
        f"\n📍 所在地・アクセス\n"
        f"・所在地: {address}\n"
        f"・最寄り駅: {access}\n"
        f"\n🏠 物件スペック\n"
        f"・面積: {area_info}\n"
        f"・間取り: {madori} / 築年月: {chikunen}\n"
        f"・建ぺい/容積率: {kenpei} / {youseki}\n"
    )

    # プロ鑑定 ＆ 団長目利きセクション（AIレポートが存在する場合のみ追加）
    if report_data:
        area_eval = report_data.get("area_evaluation", "")
        station_eval = report_data.get("station_evaluation", "")
        hazard_eval = report_data.get("hazard_evaluation", "")
        prop_eval = report_data.get("property_evaluation", "")
        mr_eval = report_data.get("mansion_market_evaluation", "")
        hbu = report_data.get("highest_and_best_use", "")
        dancho = report_data.get("danchou_comment", "")
        pos = report_data.get("ai_positive_points", "")
        neg = report_data.get("ai_negative_points", "")
        summary = report_data.get("ai_evaluation_summary", "")

        msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n📑 プロフェッショナル多面鑑定評価レポート\n"
        if area_eval:
            msg += f"\n🌍 [1. 地域・立地需給評価]\n{area_eval}\n"
        if station_eval:
            msg += f"\n🚉 [2. 駅力・交通アクセス評価]\n{station_eval}\n"
        if mr_eval and mr_eval.strip():
            msg += f"\n🏢 [3. マンションレビュー過去取引・相場分析]\n{mr_eval}\n"
        if hazard_eval:
            msg += f"\n🌊 [4. 防災・地盤・ハザード分析]\n{hazard_eval}\n"
        if prop_eval:
            msg += f"\n🏗 [5. 物件スペック・価格歪み分析]\n{prop_eval}\n"
        elif summary and not area_eval:
            msg += f"\n【AI総括サマリー】\n{summary}\n"
            
        if hbu:
            msg += f"\n🏛 [最有効使用・出口戦略]\n{hbu}\n"
        if dancho:
            msg += f"\n🐺 [元祖・狼旅団 団長の辛口実戦目利き]\n{dancho}\n"
        if pos:
            msg += f"\n⭕️ [高評価ポイント]\n{pos}\n"
        if neg:
            msg += f"\n⚠️ [物理・法的DDチェック（留意点）]\n{neg}\n"

    msg += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"情報公開日: {pub_date} | クロール日時: {crawled_date}\n"
        f"詳細URL: {eval_rec.property_url}\n"
    )
    return msg

def _dispatch_single_recommendation(eval_rec, prop, reason: str, report_data: dict | None = None) -> bool:
    p_name = clean_val(getattr(prop, "propertyName", "不明な物件名"))
    msg = _build_recommendation_msg(eval_rec, prop, reason, p_name, report_data=report_data)
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

    # Stage 1: 物件種別ごとに割安度上位を抽出 (Issue #1311, #1327)
    # Gemini レート制限および Cloud Run Job タイムアウト（2時間）防止のため、
    # 一次選抜枠を 15件/種別（計最大60件）とし、最終選抜上位（5件/種別、計最大20件）に対してのみ
    # AI多面鑑定レポート生成を行う2段階フローへ最適化する。
    STAGE1_PER_CATEGORY_LIMIT = 50
    STAGE2_PER_CATEGORY_QUOTA = 5

    candidates_by_category: dict[str, list] = {
        "mansion": [],
        "kodate": [],
        "tochi": [],
        "investment": [],
    }

    # 各カテゴリごとに優先度順ソート
    matched_candidates.sort(key=lambda x: x[0], reverse=True)
    for c in matched_candidates:
        cat = _get_property_category(c[1].property_type)
        if cat in candidates_by_category and len(candidates_by_category[cat]) < STAGE1_PER_CATEGORY_LIMIT:
            candidates_by_category[cat].append(c)

    stage1_total = sum(len(v) for v in candidates_by_category.values())
    stage1_summary = ", ".join(f"{k}: {len(v)}件" for k, v in candidates_by_category.items())
    logger.info(f"Stage 1 screening: Picked {stage1_total} properties ({stage1_summary})")
    _notify_status(
        f"🎯 【お宝物件検出】 {len(matched_candidates)} 件の候補物件を検出しました。優先度上位 {stage1_total} 件を一次選抜しました。"
    )

    # 二次スクリーニング：定性評価スコア（過去評価含む）およびML優先度を加味したカテゴリ別上位5件の選抜 (Issue #1327)
    top_candidates = _select_two_stage_recommendations(
        candidates_by_category,
        quota_per_category=STAGE2_PER_CATEGORY_QUOTA,
    )
    logger.info(f"Stage 2 screening: Selected final {len(top_candidates)} recommendation properties.")
    _notify_status(
        f"✨ 【選抜完了】 一次選抜 {stage1_total} 件から最終配信対象 {len(top_candidates)} 件を選抜しました。\n"
        f"未生成の対象物件に対してAI定性評価（多面プロ鑑定・団長講評・レーティング）を生成して各Slackチャンネルへ配信します..."
    )

    # Stage 2: 最終選抜された上位物件（最大20件）に対してのみAI定性評価・レポート生成と永続化（遅延生成）
    # レートリミット対策インターバルおよび全体タイムアウトガードを適用
    report_cache: dict[str, dict] = {}
    stage2_start_time = time.time()
    MAX_STAGE2_DURATION_SEC = 900  # 最大15分で打ち切り、Slack配信を最優先

    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    for idx, (priority, eval_rec, prop, reason) in enumerate(top_candidates, 1):
        elapsed = time.time() - stage2_start_time
        remaining_budget = MAX_STAGE2_DURATION_SEC - elapsed
        if remaining_budget <= 0:
            logger.warning(
                "Stage 2 report generation exceeded safety limit (%.0fs). Proceeding to dispatch remaining without new reports.",
                MAX_STAGE2_DURATION_SEC
            )
            break

        # レポート未生成（または未保存）の場合のみAI定性評価を実行
        if not getattr(eval_rec, "investment_rating", None) or not getattr(eval_rec, "ai_evaluation_summary", None):
            try:
                ptype_jp, asking_price_man, pred_price, address, access = _extract_property_display_info(prop, eval_rec)
                
                # 残り時間予算（remaining_budget）を超えないようスレッド実行でタイムアウト制御 (CodeRabbit指摘)
                single_timeout = min(remaining_budget, 120.0)
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        generate_professional_and_danchou_report,
                        eval_rec=eval_rec,
                        prop=prop,
                        ptype_jp=ptype_jp,
                        asking_price_man=asking_price_man,
                        pred_price=pred_price,
                        address=address,
                        access=access,
                    )
                    rep = future.result(timeout=single_timeout)
                    if rep:
                        report_cache[eval_rec.property_url] = rep
            except FuturesTimeoutError:
                logger.warning(
                    "Timed out generating report for %s within remaining budget (%.1fs). Skipping and continuing.",
                    eval_rec.property_url, remaining_budget
                )
            except Exception as e:
                logger.warning("Error generating report for %s: %s", eval_rec.property_url, e)
            # レートリミット（RPMクォータ枯渇）を防止するための安全インターバル
            time.sleep(2.0)

    sent_count = 0
    channel_counts: dict[str, int] = {}
    for _, eval_rec, prop, reason in top_candidates:
        cached_rep = report_cache.get(eval_rec.property_url)
        if _dispatch_single_recommendation(eval_rec, prop, reason, report_data=cached_rep):
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

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

# Django初期化設定
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
import realestateSettings

realestateSettings.configure()


import asyncio

from django.utils import timezone
from package.models.athome import (
    AthomeInvestmentApartment,
    AthomeKodate,
    AthomeMansion,
    AthomeTochi,
)
from package.models.evaluation import PropertyEvaluation
from package.models.homes import (
    HomesInvestmentApartment,
    HomesKodate,
    HomesMansion,
    HomesTochi,
)
from package.models.misawa import (
    MisawaInvestmentApartment,
    MisawaInvestmentKodate,
    MisawaKodate,
    MisawaMansion,
    MisawaTochi,
)
from package.models.mitsui import (
    MitsuiInvestmentApartment,
    MitsuiInvestmentKodate,
    MitsuiKodate,
    MitsuiMansion,
    MitsuiTochi,
)
from package.models.nomura import (
    NomuraInvestmentApartment,
    NomuraInvestmentKodate,
    NomuraKodate,
    NomuraMansion,
    NomuraTochi,
)
from package.models.sumifu import (
    SumifuInvestmentApartment,
    SumifuInvestmentKodate,
    SumifuKodate,
    SumifuMansion,
    SumifuTochi,
)
from package.models.tokyu import (
    TokyuInvestmentApartment,
    TokyuInvestmentKodate,
    TokyuKodate,
    TokyuMansion,
    TokyuTochi,
)
from package.utils.slack import send_dev_report

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    import httpx
except ImportError:
    httpx = None

MODEL_MAP = {
    ("mitsui", "mansion"): MitsuiMansion,
    ("mitsui", "kodate"): MitsuiKodate,
    ("mitsui", "tochi"): MitsuiTochi,
    ("mitsui", "investment_kodate"): MitsuiInvestmentKodate,
    ("mitsui", "apartment"): MitsuiInvestmentApartment,
    ("sumifu", "mansion"): SumifuMansion,
    ("sumifu", "kodate"): SumifuKodate,
    ("sumifu", "tochi"): SumifuTochi,
    ("sumifu", "investment_kodate"): SumifuInvestmentKodate,
    ("sumifu", "apartment"): SumifuInvestmentApartment,
    ("tokyu", "mansion"): TokyuMansion,
    ("tokyu", "kodate"): TokyuKodate,
    ("tokyu", "tochi"): TokyuTochi,
    ("tokyu", "investment_kodate"): TokyuInvestmentKodate,
    ("tokyu", "apartment"): TokyuInvestmentApartment,
    ("nomura", "mansion"): NomuraMansion,
    ("nomura", "kodate"): NomuraKodate,
    ("nomura", "tochi"): NomuraTochi,
    ("nomura", "investment_kodate"): NomuraInvestmentKodate,
    ("nomura", "apartment"): NomuraInvestmentApartment,
    ("misawa", "mansion"): MisawaMansion,
    ("misawa", "kodate"): MisawaKodate,
    ("misawa", "tochi"): MisawaTochi,
    ("misawa", "investment_kodate"): MisawaInvestmentKodate,
    ("misawa", "apartment"): MisawaInvestmentApartment,
    ("athome", "mansion"): AthomeMansion,
    ("athome", "kodate"): AthomeKodate,
    ("athome", "tochi"): AthomeTochi,
    ("athome", "apartment"): AthomeInvestmentApartment,
    ("homes", "mansion"): HomesMansion,
    ("homes", "kodate"): HomesKodate,
    ("homes", "tochi"): HomesTochi,
    ("homes", "apartment"): HomesInvestmentApartment,
}

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def aggregate_and_sort_targets(raw_targets: list[dict], max_targets: int = 50) -> list[dict]:
    """
    検知された異常物件リストを (company, property_type, reason_prefix) 単位で集計し、
    発生件数（頻度）が多い順にソートして上位グループから代表レコード1件ずつ最大 max_targets 件（デフォルト50件）を返却する。
    各要素には frequency フィールドが付与される。
    """
    if not raw_targets:
        return []

    from collections import Counter

    # グループキーの生成: reason のコロン前などをグループ化キーにする
    def get_group_key(target: dict) -> tuple:
        reason = target.get("reason", "")
        reason_group = reason.split(":")[0] if ":" in reason else reason
        return (target.get("company"), target.get("property_type"), reason_group)

    # 頻度集計
    counts = Counter(get_group_key(t) for t in raw_targets)

    # グループごとに代表レコード（最初の1件）を保持
    groups: dict[tuple, dict] = {}
    for t in raw_targets:
        key = get_group_key(t)
        if key not in groups:
            t_copy = dict(t)
            t_copy["frequency"] = counts[key]
            groups[key] = t_copy

    # 頻度降順（第一キー: -frequency, 第二キー: company, 第三キー: property_type）でソート
    sorted_groups = sorted(
        groups.values(),
        key=lambda x: (-x.get("frequency", 1), x.get("company", ""), x.get("property_type", ""))
    )

    # 上位 max_targets 件を取得
    return sorted_groups[:max_targets]


_CB_STATE_FILE = "gemini_circuit_breaker.json"


def _get_cb_state_path() -> str:
    curr = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(os.path.dirname(curr)))
    return os.path.join(root, "Temp", _CB_STATE_FILE)


def _load_cb_state() -> tuple[int, datetime | None]:
    path = _get_cb_state_path()
    if not os.path.exists(path):
        return 0, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            count = data.get("consecutive_timeouts", 0)
            cd_str = data.get("cooldown_until")
            cd = datetime.fromisoformat(cd_str) if cd_str else None
            return count, cd
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed to load circuit-breaker state from {path}: {e}")
        return 0, None


def _save_cb_state(count: int, cooldown_until: datetime | None) -> None:
    path = _get_cb_state_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "consecutive_timeouts": count,
                "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
            }, f)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed to save circuit-breaker state to {path}: {e}")


def summarize_errors_with_gemini(top_targets: list[dict]) -> str:
    """
    Google Cloud Gemini 2.5 Flash を用いて上位エラーを簡潔に要約（Caveman形式）する。
    連続タイムアウト時はサーキットブレイカー（クールダウン）を作動させ、ルールベースのデフォルトサマリーを即時返却。
    プロセス間永続化ファイル（Temp/gemini_circuit_breaker.json）により状態を維持。
    """
    if not top_targets:
        return ""

    default_summary = "\n".join(
        [
            f"- {t.get('company')} ({t.get('property_type')}) [{t.get('frequency', 1)}件]: {t.get('reason')} (URL: {t.get('url')})"
            for t in top_targets[:5]
        ]
    )
    if len(top_targets) > 5:
        default_summary += f"\n... 他 {len(top_targets) - 5} 件 (最大50件を優先修復対象に選定)"

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or genai is None:
        return default_summary

    consecutive_timeouts, cooldown_until = _load_cb_state()
    now = datetime.now(dt_timezone.utc)
    if cooldown_until and now < cooldown_until:
        logger.warning(
            "Gemini API circuit-breaker active until %s due to consecutive timeouts. Returning default summary.",
            cooldown_until,
        )
        return default_summary

    model_name = "gemini-2.5-flash"
    try:
        http_options = types.HttpOptions(timeout=10000) if types else None
        with genai.Client(api_key=api_key, http_options=http_options) as client:
            items_text = json.dumps(top_targets[:50], ensure_ascii=False, indent=2)
            prompt = (
                "以下の不動産クローラーのエラー上位リスト（Top 50）を読み、AI開発エージェント向けに"
                "修復優先度・影響サイト・原因セレクターやパース不備をCaveman形式（簡潔・余計な修飾語なし・箇条書き）で要約してください。\n\n"
                f"{items_text}"
            )
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            summary_text = (getattr(resp, "text", "") or "").strip()
            if summary_text:
                _save_cb_state(0, None)
                return summary_text
    except Exception as e:  # noqa: BLE001
        is_timeout_exception = isinstance(e, (TimeoutError, asyncio.TimeoutError))
        if httpx and isinstance(e, httpx.TimeoutException):
            is_timeout_exception = True
        err_msg = str(e).lower()
        if is_timeout_exception or any(k in err_msg for k in ("timeout", "timed out", "deadline")):
            consecutive_timeouts += 1
            logger.warning(
                "Gemini API timeout occurred (consecutive: %d): %s",
                consecutive_timeouts,
                e,
            )
            new_cooldown = None
            if consecutive_timeouts >= 2:
                new_cooldown = now + timedelta(minutes=5)
                logger.warning(
                    "Gemini API consecutive timeouts reached threshold. Entering cooldown for 5 minutes until %s.",
                    new_cooldown,
                )
            _save_cb_state(0 if new_cooldown else consecutive_timeouts, new_cooldown)
        else:
            logger.warning(f"Failed to summarize errors with Gemini: {e}")

    return default_summary


def notify_auto_heal_request(
    heal_targets: list[dict],
    ai_summary: str = "",
    total_detected: int | None = None,
):
    """
    異常検知時にSlack (#dev-agent) へ [AUTO_HEAL_REQ] を発報し、
    常駐デーモン経由で Antigravity 自己修復を自動キックします。
    """
    if not heal_targets:
        return

    target_summary = ai_summary if ai_summary else "\n".join(
        [
            f"- {t.get('company')} ({t.get('property_type')}) [{t.get('frequency', 1)}件]: {t.get('reason')} (URL: {t.get('url')})"
            for t in heal_targets[:5]
        ]
    )
    if not ai_summary and len(heal_targets) > 5:
        target_summary += f"\n... 他 {len(heal_targets) - 5} 件"

    total_count = total_detected if total_detected is not None else len(heal_targets)
    msg = (
        f"🚨 **[AUTO_HEAL_REQ] クローラー自己修復リクエスト**\n"
        f"クローリング・データ検証においてパース異常・データ不整合が検知されました。\n\n"
        f"**検知件数**: {total_count} 件 (優先グループ {len(heal_targets)} 件)\n"
        f"**対象概要**:\n{target_summary}\n\n"
        f"/auto-heal"
    )
    try:
        asyncio.run(send_dev_report(msg))
        logger.info("Successfully sent [AUTO_HEAL_REQ] to Slack dev channel.")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to send auto-heal Slack notification: {e}")


def scan_anomalies_and_generate_instructions():
    """
    データ不整合（価格極小、面積極小、一棟面積不足、間口0m警告など）がある物件や、
    直近でエラーが検出された物件のURLをDBからスキャンし、
    発生頻度の高い上位エラー（Top 50）に絞り込んで自己修復指示書 (auto_heal_instruction.json) を出力します。
    """
    logger.info(
        "Scanning for scraping anomalies and errors to build AI self-healing instructions..."
    )

    heal_targets = []

    three_days_ago = timezone.now() - timedelta(days=3)
    # needs_parser_fix=True かつ 公開中 (is_published=True) の物件をスキャン (Issue #665)
    eval_anomalies = PropertyEvaluation.objects.filter(
        needs_parser_fix=True,
        is_published=True,
    )
    if not eval_anomalies.exists():
        eval_anomalies = PropertyEvaluation.objects.filter(analyzed_at__gte=three_days_ago, is_published=True)

    for ev in eval_anomalies:
        model = MODEL_MAP.get((ev.company, ev.property_type))
        if not model:
            continue
        try:
            prop = model.objects.get(id=ev.property_id)
        except model.DoesNotExist:
            continue

        reason = ev.data_quality_issue or ""
        if not reason:
            if prop.price and prop.price < 1000000:
                reason = f"価格異常極小: {prop.priceStr} ({prop.price}円)"
            elif getattr(prop, "tatemonoMenseki", 0) and prop.tatemonoMenseki < 5.0:
                reason = f"建物面積異常極小: {prop.tatemonoMenseki}㎡"
            elif getattr(prop, "tochiMenseki", 0) and prop.tochiMenseki < 5.0:
                reason = f"土地面積異常極小: {prop.tochiMenseki}㎡"
        elif (
            hasattr(prop, "maguchi")
            and prop.maguchi == 0
            and prop.setsudou
            and any(k in str(prop.setsudou) for k in ["間口", "接面"])
        ):
            reason = f"間口パース漏れ警告 (接道: '{prop.setsudou}')"

        if reason:
            target = {
                "url": prop.pageUrl,
                "company": ev.company,
                "property_type": ev.property_type,
                "propertyName": prop.propertyName,
                "price": float(prop.price) if prop.price else 0,
                "reason": reason,
                "detected_at": ev.analyzed_at.strftime("%Y-%m-%d %H:%M:%S")
                if ev.analyzed_at
                else None,
            }
            if target not in heal_targets:
                heal_targets.append(target)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    temp_dir = os.path.join(project_root, "Temp")

    if not heal_targets:
        logger.info("No scraping anomalies found for AI healing.")
        inst_path = os.path.join(temp_dir, "auto_heal_instruction.json")
        if os.path.exists(inst_path):
            os.remove(inst_path)
            logger.info("Removed stale auto_heal_instruction.json")
        return

    # 発生頻度順（Top 50）に優先順位付け
    top_targets = aggregate_and_sort_targets(heal_targets, max_targets=50)

    # Google Cloud Gemini (Flash) を直接呼び出し、インメモリでエラー要約（ローカル一時ファイル経由なし）
    ai_summary = summarize_errors_with_gemini(top_targets)

    parser_rel_dir = os.path.relpath(
        os.path.join(os.path.dirname(os.path.dirname(current_dir)), "package", "parser"),
        project_root,
    ).replace("\\", "/")

    instruction = {
        "generated_at": datetime.now(dt_timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "total_anomalies_detected": len(heal_targets),
        "ai_summary": ai_summary,
        "targets": top_targets,
        "action_required": f"Please inspect the target URLs in prioritized order (Top-50 frequency first), analyze why their data parsed incorrectly, fix the corresponding parser inside {parser_rel_dir}/, run verification tests, and commit/push/merge changes to master.",
    }

    os.makedirs(temp_dir, exist_ok=True)
    inst_path = os.path.join(temp_dir, "auto_heal_instruction.json")
    with open(inst_path, "w", encoding="utf-8") as f:
        json.dump(instruction, f, ensure_ascii=False, indent=2)

    logger.info(
        f"Successfully generated AI self-healing instruction at {inst_path} with {len(top_targets)} prioritized targets (total {len(heal_targets)} detected)."
    )
    notify_auto_heal_request(
        top_targets,
        ai_summary=ai_summary,
        total_detected=len(heal_targets),
    )


if __name__ == "__main__":
    scan_anomalies_and_generate_instructions()

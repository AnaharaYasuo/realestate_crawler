import json
import logging
import os
import sys
from datetime import UTC, datetime, timedelta

# Django初期化設定
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
import realestateSettings

realestateSettings.configure()


import asyncio

from django.utils import timezone
from package.models.evaluation import PropertyEvaluation
from package.site_registry import SiteRegistry
from package.utils.data_validator import PropertyDataValidator
from package.utils.open_data_cache_sync import should_sync_storage_cache
from package.utils.slack import send_dev_report
from package.utils.storage import get_storage_manager
from package.utils.url_matcher import UrlMatcher

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


def _build_dynamic_model_map() -> dict[tuple[str, str], object]:
    mapping: dict[tuple[str, str], object] = {}
    for model_cls, comp, ptype in SiteRegistry.get_all_property_model_entries():
        mapping[(comp, ptype)] = model_cls
        if ptype == "invest_kodate":
            mapping[(comp, "investment_kodate")] = model_cls
            mapping[(comp, "investmentkodate")] = model_cls
        elif ptype == "apartment":
            mapping[(comp, "invest_apartment")] = model_cls
            mapping[(comp, "investmentapartment")] = model_cls
            mapping[(comp, "investment")] = model_cls
    for comp, ptype in SiteRegistry.get_all_jobs():
        resolved = SiteRegistry.resolve_model_class(comp, ptype)
        if resolved is not None:
            mapping[(comp, ptype)] = resolved
    return mapping


MODEL_MAP = _build_dynamic_model_map()

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


def get_project_root() -> str:
    """リポジトリルート（/app またはホストのプロジェクトルート）を動的に探索・解決する"""
    cur = os.path.abspath(__file__)
    while True:
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        if (os.path.exists(os.path.join(parent, "src")) and os.path.exists(os.path.join(parent, "docs"))) or os.path.exists(os.path.join(parent, ".git")):
            return parent
        cur = parent
    curr = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(curr))))


_CB_STATE_FILE = "gemini_circuit_breaker.json"


def _get_cb_state_path() -> str:
    root = get_project_root()
    return os.path.join(root, "Temp", _CB_STATE_FILE)


def _load_cb_state() -> tuple[int, datetime | None]:
    path = _get_cb_state_path()
    if not os.path.exists(path):
        return 0, None
    try:
        with open(path, encoding="utf-8") as f:
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


def summarize_errors_with_gemini(
    top_targets: list[dict], failed_pipeline_steps: list[str] | None = None
) -> str:
    """
    Google Cloud Gemini を用いてエラーを分析し、根本原因と具体的修正アクション（対象ファイル・メソッド）を提示する。
    環境変数 GEMINI_RECOMMEND_MODEL (デフォルト: gemini-3.8-flash, フォールバック: gemini-3.1-flash-lite) に準拠 (Issue #1391)。
    連続タイムアウト時はサーキットブレイカー（クールダウン）を作動させ、ルールベースのデフォルトサマリーを即時返却。
    """
    if not top_targets and not failed_pipeline_steps:
        return ""

    summary_lines = []
    if failed_pipeline_steps:
        summary_lines.append("【パイプライン重大失敗ステップ】:")
        for fs in failed_pipeline_steps:
            summary_lines.append(f"- ❌ {fs}")
    if top_targets:
        summary_lines.append("【上位データ・パース異常】:")
        for t in top_targets[:5]:
            summary_lines.append(
                f"- {t.get('company')} ({t.get('property_type')}) [{t.get('frequency', 1)}件]: {t.get('reason')} (URL: {t.get('url')})"
            )
        if len(top_targets) > 5:
            summary_lines.append(f"... 他 {len(top_targets) - 5} 件 (最大50件を優先修復対象に選定)")

    default_summary = "\n".join(summary_lines)

    # ユニットテスト環境等でGEMINI_API_KEYがあってもモック無しでLLM生成テキストが不定になるのを防ぐため、
    # default_summary にプレースホルダーヘッダーを保持しつつ、Gemini APIコールを実行可能。
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or genai is None or os.getenv("TESTING") == "1":
        return default_summary

    consecutive_timeouts, cooldown_until = _load_cb_state()
    now = datetime.now(UTC)
    if cooldown_until and now < cooldown_until:
        logger.warning(
            "Gemini API circuit-breaker active until %s due to consecutive timeouts. Returning default summary.",
            cooldown_until,
        )
        return default_summary

    # 環境変数からモデルを取得。gemini-2.5-flash等の非推奨・廃止モデルが指定されていた場合は最新3.8-flashへフォールバック
    candidate_model = os.getenv("GEMINI_RECOMMEND_MODEL", "gemini-3.8-flash")
    if candidate_model in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
        candidate_model = "gemini-3.8-flash"

    try:
        http_options = types.HttpOptions(timeout=15000) if types else None
        with genai.Client(api_key=api_key, http_options=http_options) as client:
            items_text = json.dumps(top_targets[:50], ensure_ascii=False, indent=2)
            steps_text = json.dumps(failed_pipeline_steps or [], ensure_ascii=False, indent=2)
            prompt = (
                "あなたは不動産クローラーおよびML価格推定システムの主任AIデバッグエージェントです。\n"
                "今回パイプライン実行で発生したエラー（失敗ステップおよびデータ・パース異常）を分析し、"
                "開発AIエージェントが直ちに修復に着手できるよう、実効性のある診断レポートを作成してください。\n\n"
                f"### パイプライン失敗ステップ:\n{steps_text}\n\n"
                f"### 上位異常リスト (Top 50):\n{items_text}\n\n"
                "### 出力要件:\n"
                "1. **【全体診断 & 根本原因】**: パイプライン停止やデータ異常の主要因（DOM変更、MySQL切断/Server has gone away、型破綻、モデル推論異常など）を箇条書きで特定する。\n"
                "2. **【最優先修正対象】**: 影響度の大きい順に、修正すべき具体的なファイルパス（例: `src/crawler/package/parser/xxxParser.py`, `src/crawler/package/ml/xxx.py`）、クラス・メソッド名、修正すべきロジックの概要を提示する。\n"
                "3. **【推奨実行コマンド】**: テストやオートヒール実行のためのコマンド（例: `/auto-heal`, `pytest ...`）を明示する。\n"
                "※ 冗長な挨拶は省き、実務的・具体的・Markdown形式で記述してください。"
            )
            resp = client.models.generate_content(
                model=candidate_model,
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
            logger.warning(f"Failed to summarize errors with Gemini ({candidate_model}): {e}")

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


def parse_slack_message_to_targets(text: str, channel_name: str = "", ts: str = "") -> list[dict]:
    """
    Slackメッセージ本文から、0件取得警告、パース例外、低件数異常を抽出し、自己修復ターゲット辞書のリストを生成する。
    """
    if not text:
        return []

    targets = []
    import re

    # 1. 0件取得警告
    if "0件取得検知" in text or ("取得件数: 0" in text and "クローリング" in text):
        site_match = re.search(r"対象サイト:\s*([a-zA-Z0-9_]+)", text)
        type_match = re.search(r"種別:\s*([a-zA-Z0-9_]+)", text)
        site = site_match.group(1).lower() if site_match else "unknown"
        ptype = type_match.group(1).lower() if type_match else "unknown"
        if site != "unknown":
            targets.append({
                "company": site,
                "property_type": ptype,
                "reason": f"0件取得検知 (#{channel_name})",
                "url": f"https://www.{site}.co.jp/" if "." not in site else f"https://{site}/",
                "detected_at": ts,
                "source": "slack"
            })

    # 2. パース例外 / データ異常検知
    if "パース例外" in text or "データ異常検知" in text:
        site_match = re.search(r"サイト:\s*([a-zA-Z0-9_]+)", text)
        type_match = re.search(r"種別:\s*([a-zA-Z0-9_]+)", text)
        err_match = re.search(r"エラー:\s*(.+)", text)
        url_match = re.search(r"URL:\s*(https?://[^\s]+)", text)
        site = site_match.group(1).lower() if site_match else "unknown"
        ptype = type_match.group(1).lower() if type_match else "unknown"
        err = err_match.group(1).strip() if err_match else "パース例外"
        url = url_match.group(1).strip() if url_match else ""
        if site != "unknown":
            targets.append({
                "company": site,
                "property_type": ptype,
                "reason": f"パース例外: {err}",
                "url": url or f"https://www.{site}.co.jp/",
                "detected_at": ts,
                "source": "slack"
            })

    # 3. データ監視アラート個別行 (- :x: [Critical] [company/ptype] ... | URL: <url>)
    # 例: - :x: [Critical] [mitsui/mansion] 価格異常 (0.0万円), 面積異常 (0.0㎡) | パークシティ中野 ザ タワー エアーズ | URL: <https://www.rehouse.co.jp/buy/mansion/bkdetail/FKJBFA06/>
    monitor_alert_pattern = re.compile(
        r"-\s*:(?:x|bulb):\s*\[(?:Critical|Warning)\]\s*\[([a-zA-Z0-9_]+)/([a-zA-Z0-9_]+)\]\s*([^|]+)\|\s*([^|]+)\|\s*URL:\s*<?(https?://[^\s>]+)>?",
        re.IGNORECASE,
    )
    for match in monitor_alert_pattern.finditer(text):
        site = match.group(1).lower().strip()
        ptype = match.group(2).lower().strip()
        reason = match.group(3).strip()
        pname = match.group(4).strip()
        url = match.group(5).strip()

        # ビジネス上の注意喚起・ペナルティ情報（再建築不可、間口0m等）はパーサーバグではないため除外
        if any(w in reason for w in ("再建築不可", "間口0m", "無道路地")):
            continue

        u_low = url.lower()
        if (
            (ptype == "tochi" and any(seg in u_low for seg in ("/mansion/", "/kodate/")))
            or (ptype == "kodate" and any(seg in u_low for seg in ("/mansion/", "/tochi/")))
            or (ptype == "mansion" and any(seg in u_low for seg in ("/tochi/", "/kodate/")))
            or (ptype in ("apartment", "investmentapartment") and "/tochi/" in u_low)
        ):
            continue

        targets.append({
            "company": site,
            "property_type": ptype,
            "propertyName": pname,
            "reason": f"{reason} (#{channel_name})",
            "url": url,
            "detected_at": ts,
            "source": "slack",
        })

    # 4. 低件数サマリー
    major_sites = ["athome", "homes", "mitsui", "sumifu", "tokyu", "nomura"]
    for s in major_sites:
        pat = rf"(?:•|\*|-)?\s*{s}\s*[:：]\s*(\d+)\s*件"
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            cnt = int(m.group(1))
            if cnt < 5:
                targets.append({
                    "company": s,
                    "property_type": "mansion",
                    "reason": f"大規模サイト極小件数異常: {cnt}件取得 (#{channel_name})",
                    "url": f"https://www.{s}.co.jp/",
                    "detected_at": ts,
                    "source": "slack"
                })

    return targets


async def fetch_all_slack_channel_messages(limit: int = 100) -> list[tuple[str, dict]]:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token or os.getenv("PYTEST_CURRENT_TEST"):
        return []

    import aiohttp
    headers = {"Authorization": f"Bearer {token}"}
    all_msgs = []
    try:
        timeout = aiohttp.ClientTimeout(total=10.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            list_url = "https://slack.com/api/conversations.list"
            cursor = None
            channels = []
            while True:
                params = {"types": "public_channel,private_channel", "limit": 100}
                if cursor:
                    params["cursor"] = cursor
                async with session.get(list_url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    if not data.get("ok"):
                        logger.warning(f"Slack API conversations.list returned error: {data.get('error')}")
                        return []
                    channels.extend(data.get("channels", []))
                    cursor = data.get("response_metadata", {}).get("next_cursor")
                    if not cursor:
                        break

            for ch in channels:
                ch_name = ch.get("name", "")
                if not (ch_name.startswith("alerts-") or ch_name in ["dev-agent", "property_alert", "alerts-crawling"]):
                    continue
                hist_url = "https://slack.com/api/conversations.history"
                try:
                    async with session.get(hist_url, headers=headers, params={"channel": ch["id"], "limit": limit}) as hresp:
                        if hresp.status != 200:
                            logger.warning(f"conversations.history HTTP {hresp.status} for {ch_name}")
                            continue
                        hdata = await hresp.json()
                        if not hdata.get("ok"):
                            logger.warning(f"conversations.history error for {ch_name}: {hdata.get('error')}")
                            continue
                        for m in hdata.get("messages", []):
                            all_msgs.append((ch_name, m))
                except Exception as ch_err:  # noqa: BLE001
                    logger.warning(f"History fetch error for channel {ch_name}: {ch_err}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to fetch Slack messages for auto-healing: {e}")
    return all_msgs


async def fetch_slack_error_targets(limit: int = 100) -> list[dict]:
    """
    Slackチャンネルからエラーメッセージおよび低件数異常を抽出し、ターゲットリストを返却する。
    """
    msgs = await fetch_all_slack_channel_messages(limit=limit)
    targets = []
    for ch_name, m in msgs:
        text = m.get("text", "")
        ts = m.get("ts", "")
        parsed = parse_slack_message_to_targets(text, channel_name=ch_name, ts=ts)
        targets.extend(parsed)
    return targets


AUTO_HEAL_GCS_LATEST_KEY = "auto_heal/latest_instruction.json"


def upload_instruction_to_gcs(instruction: dict) -> bool:
    """Cloud Run / GCS 環境において自己修復指示書を GCS へ永続化し、ホスト /auto-heal から参照可能にする (Issue #1410)"""
    if not should_sync_storage_cache():
        return False
    try:
        payload = json.dumps(instruction, ensure_ascii=False, indent=2).encode("utf-8")
        today_str = datetime.now(UTC).strftime("%Y-%m-%d")
        sm = get_storage_manager()
        sm.upload_bytes(payload, AUTO_HEAL_GCS_LATEST_KEY, content_type="application/json")
        sm.upload_bytes(
            payload,
            f"auto_heal/history/{today_str}/auto_heal_instruction.json",
            content_type="application/json",
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to upload auto_heal_instruction.json to GCS: %s", exc)
        return False


def pull_latest_instruction_from_gcs(dest_path: str | None = None) -> bool:
    """GCS 上の最新 auto_heal/latest_instruction.json をローカル Temp/auto_heal_instruction.json へ取得する (Issue #1410)"""
    target_path = dest_path or os.path.join(get_project_root(), "Temp", "auto_heal_instruction.json")
    try:
        raw_text = get_storage_manager().read_text(AUTO_HEAL_GCS_LATEST_KEY)
        if not raw_text:
            return False
        parsed = json.loads(raw_text)
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        logger.info("Pulled latest auto-heal instruction from GCS to %s", target_path)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not pull auto-heal instruction from GCS: %s", exc)
        return False


def _resolve_property_for_eval(ev, model):
    prop_id = getattr(ev, "property_id", 0) or 0
    if prop_id > 0:
        try:
            return model.objects.get(id=prop_id)
        except model.DoesNotExist:
            pass
    prop_url = getattr(ev, "property_url", "") or ""
    if prop_url:
        try:
            return UrlMatcher.find_match_in_queryset(model.objects, "pageUrl", prop_url)
        except Exception:  # noqa: BLE001
            return None
    return None


def _mark_eval_heal_requested(ev) -> None:
    cur_status = getattr(ev, "heal_status", "detected")
    if cur_status in ("healthy", "detected", ""):
        try:
            ev.heal_status = "heal_requested"
            ev.save(update_fields=["heal_status"])
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not persist heal_requested status: %s", exc)


def _extract_fallback_reason_from_prop(prop) -> str:
    if getattr(prop, "price", None) and prop.price < 1000000:
        return f"価格異常極小: {getattr(prop, 'priceStr', '')} ({prop.price}円)"
    if getattr(prop, "tatemonoMenseki", 0) and prop.tatemonoMenseki < 5.0:
        return f"建物面積異常極小: {prop.tatemonoMenseki}㎡"
    if getattr(prop, "tochiMenseki", 0) and prop.tochiMenseki < 5.0:
        return f"土地面積異常極小: {prop.tochiMenseki}㎡"
    return ""


def _is_source_data_invalid(ev) -> bool:
    if getattr(ev, "heal_status", "") == "source_data_invalid":
        return True
    issue_text = str(getattr(ev, "data_quality_issue", "") or "")
    return "[source_data_invalid]" in issue_text


def _clear_stale_instruction_and_sync_zero(temp_dir: str) -> None:
    logger.info("No scraping anomalies or pipeline failures found for AI healing.")
    inst_path = os.path.join(temp_dir, "auto_heal_instruction.json")
    if os.path.exists(inst_path):
        os.remove(inst_path)
        logger.info("Removed stale auto_heal_instruction.json")
    upload_instruction_to_gcs(
        {
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "total_anomalies_detected": 0,
            "failed_pipeline_steps": [],
            "ai_summary": "",
            "targets": [],
            "action_required": "",
        }
    )


def _build_target_from_eval_anomaly(ev) -> dict | None:
    if _is_source_data_invalid(ev):
        return None

    model = MODEL_MAP.get((ev.company, ev.property_type)) or SiteRegistry.resolve_model_class(
        ev.company, ev.property_type
    )
    prop = _resolve_property_for_eval(ev, model) if model is not None else None

    if prop is None:
        # 初回詳細ページ取得で ParserFailureException となり property_id=0 のみのケースを救済 (Issue #1410)
        prop_url = getattr(ev, "property_url", "") or ""
        reason = getattr(ev, "data_quality_issue", "") or ""
        if not prop_url or not reason:
            return None
        _mark_eval_heal_requested(ev)
        return {
            "url": prop_url,
            "company": ev.company,
            "property_type": ev.property_type,
            "propertyName": "(初回パース失敗・未保存物件)",
            "price": 0,
            "reason": reason,
            "detected_at": ev.analyzed_at.strftime("%Y-%m-%d %H:%M:%S") if getattr(ev, "analyzed_at", None) else None,
        }

    # 現行バリデータで再検証: すでに合格するレコードは自動的に不整合フラグを解消 (Issue #922)
    is_valid, current_reasons = PropertyDataValidator.validate_property(prop, ev.property_type)
    if is_valid:
        if ev.needs_parser_fix or ev.data_quality_issue:
            ev.needs_parser_fix = False
            ev.data_quality_issue = ""
            if hasattr(ev, "heal_status"):
                ev.heal_status = "recrawled_pending_ml"
            ev.save(update_fields=["needs_parser_fix", "data_quality_issue"])
        return None

    reason = "; ".join(current_reasons) if current_reasons else (ev.data_quality_issue or "")
    if not reason:
        reason = _extract_fallback_reason_from_prop(prop)

    if (
        hasattr(prop, "maguchi")
        and prop.maguchi == 0
        and prop.setsudou
        and any(k in str(prop.setsudou) for k in ["間口", "接面"])
    ):
        maguchi_warn = f"間口パース漏れ警告 (接道: '{prop.setsudou}')"
        reason = f"{reason}; {maguchi_warn}" if reason else maguchi_warn

    if not reason:
        return None

    _mark_eval_heal_requested(ev)
    return {
        "url": prop.pageUrl,
        "company": ev.company,
        "property_type": ev.property_type,
        "propertyName": prop.propertyName,
        "price": float(prop.price) if prop.price else 0,
        "reason": reason,
        "detected_at": ev.analyzed_at.strftime("%Y-%m-%d %H:%M:%S") if ev.analyzed_at else None,
    }


def scan_anomalies_and_generate_instructions(failed_steps: list[str] | None = None):
    """
    データ不整合（価格極小、面積極小、一棟面積不足、間口0m警告など）がある物件や、
    直近でエラーが検出された物件のURLをDBからスキャンし、
    パイプライン各ステップの失敗情報（failed_steps）も含めて総合自己修復指示書 (auto_heal_instruction.json) を出力します。
    """
    logger.info(
        "Scanning for scraping anomalies and errors to build AI self-healing instructions..."
    )

    heal_targets = []

    # Slackエラー・0件警告・極小件数異常の自動取得 (Issue #958)
    try:
        slack_targets = asyncio.run(fetch_slack_error_targets(limit=100))
        for st in slack_targets:
            if st not in heal_targets:
                heal_targets.append(st)
        logger.info(f"Loaded {len(slack_targets)} error targets from Slack telemetry.")
    except Exception as se:  # noqa: BLE001
        logger.warning(f"Could not load Slack error targets: {se}")

    three_days_ago = timezone.now() - timedelta(days=3)
    # needs_parser_fix=True かつ 公開中 (is_published=True) の物件をスキャン (Issue #665)
    eval_anomalies = PropertyEvaluation.objects.filter(
        needs_parser_fix=True,
        is_published=True,
    )
    if not eval_anomalies.exists():
        eval_anomalies = PropertyEvaluation.objects.filter(analyzed_at__gte=three_days_ago, is_published=True)

    for ev in eval_anomalies:
        target = _build_target_from_eval_anomaly(ev)
        if target and target not in heal_targets:
            heal_targets.append(target)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = get_project_root()
    temp_dir = os.path.join(project_root, "Temp")

    if not heal_targets and not failed_steps:
        _clear_stale_instruction_and_sync_zero(temp_dir)
        return

    # 発生頻度順（Top 50）に優先順位付け
    top_targets = aggregate_and_sort_targets(heal_targets, max_targets=50)

    # Google Cloud Gemini を直接呼び出し、インメモリで根本原因・具体的アクションを分析 (Issue #1391)
    ai_summary = summarize_errors_with_gemini(top_targets, failed_pipeline_steps=failed_steps)

    parser_rel_dir = os.path.relpath(
        os.path.join(os.path.dirname(os.path.dirname(current_dir)), "package", "parser"),
        project_root,
    ).replace("\\", "/")

    instruction = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "total_anomalies_detected": len(heal_targets),
        "failed_pipeline_steps": failed_steps or [],
        "ai_summary": ai_summary,
        "targets": top_targets,
        "action_required": (
            f"Please inspect the target URLs in prioritized order (Top-50 frequency first), analyze why their data parsed incorrectly, "
            f"fix the corresponding parser inside {parser_rel_dir}/ in an isolated git worktree with SDD doc + TDD test updates, "
            f"run verification tests, merge the PR to master, promote and merge the Release PR into production, "
            f"and verify that the Deploy Production workflow succeeds on Cloud Run (stopping at PR creation or master merge is strictly prohibited)."
        ),
    }

    os.makedirs(temp_dir, exist_ok=True)
    inst_path = os.path.join(temp_dir, "auto_heal_instruction.json")
    with open(inst_path, "w", encoding="utf-8") as f:
        json.dump(instruction, f, ensure_ascii=False, indent=2)

    upload_instruction_to_gcs(instruction)

    logger.info(
        f"Successfully generated AI self-healing instruction at {inst_path} with {len(top_targets)} prioritized targets (total {len(heal_targets)} detected, failed_steps: {len(failed_steps or [])})."
    )
    notify_auto_heal_request(
        top_targets,
        ai_summary=ai_summary,
        total_detected=len(heal_targets),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Auto-Heal Instruction Generator")
    parser.add_argument(
        "--failed-steps",
        dest="failed_steps",
        type=str,
        default=None,
        help="JSON-encoded list of failed pipeline step descriptions",
    )
    parser.add_argument(
        "--pull-from-gcs",
        dest="pull_from_gcs",
        action="store_true",
        help="Pull latest auto_heal_instruction.json from GCS to Temp/ and exit",
    )
    args = parser.parse_args()
    if args.pull_from_gcs:
        pull_latest_instruction_from_gcs()
        sys.exit(0)
    failed_steps_list = None
    if args.failed_steps:
        try:
            failed_steps_list = json.loads(args.failed_steps)
        except json.JSONDecodeError:
            failed_steps_list = [args.failed_steps]
    scan_anomalies_and_generate_instructions(failed_steps=failed_steps_list)

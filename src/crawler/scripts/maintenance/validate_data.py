import argparse
import asyncio
import copy
import datetime
import json
import logging
import os
import subprocess
import sys
import time
from typing import Any

_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env  # noqa: F401
        break
    _cur = _parent

from asgiref.sync import async_to_sync
from django.db import OperationalError, close_old_connections, transaction
from django.utils import timezone
from package.models.evaluation import PropertyEvaluation
from package.site_registry import SiteRegistry
from package.utils.data_validator import PropertyDataValidator, apply_integrity_transition
from package.utils.db_timeouts import bound_mysql_timeouts
from package.utils.slack import send_dev_report, verify_url_active

logger = logging.getLogger(__name__)


def get_all_models_flat(skip_portals: bool = False, skip_uncrawled: bool = False):
    """SiteRegistry (SSOT) から全物件種別のモデルクラスとその判定タグのリストを動的に返す (Issue #1410)"""
    return SiteRegistry.get_all_property_model_entries(
        skip_portals=skip_portals,
        skip_uncrawled=skip_uncrawled,
    )


async def process_property_validation(
    item: Any,
    property_type: str,
    company: str,
    eval_rec: PropertyEvaluation | None = None,
    skip_url_check: bool = False,
) -> dict[str, Any]:
    """
    単一物件レコードの生存確認およびデータ妥当性を検証する。
    1. 掲載終了（404等）判定時: is_published=False, delisted_at=now, needs_recrawl=False (skip_url_check=True の場合はスキップ)
    2. スペック異常判定時: needs_parser_fix=True, needs_recrawl=True, heal_status='detected', 予測価格無効化 (is_slack_notifiedは非汚染)
    3. 正常時: is_published=True, needs_recrawl=False
    """
    url = getattr(item, "pageUrl", "") or getattr(item, "url", "")
    p_name = getattr(item, "propertyName", "不明な物件名")

    # 1. URL生存確認 (公開中かどうか - skip_url_check=True 時は省略)
    if url and not skip_url_check:
        is_active = await verify_url_active(url)
        if not is_active:
            if eval_rec:
                eval_rec.is_published = False
                eval_rec.delisted_at = timezone.now()
                eval_rec.needs_recrawl = False
                eval_rec.first_stage_predicted_price = None
                eval_rec.second_stage_predicted_price = None
                eval_rec.dcf_theoretical_price = None
                eval_rec.is_first_stage_passed = False
                if not eval_rec.needs_parser_fix:
                    eval_rec.heal_status = "healthy"
            return {
                "status": "delisted",
                "company": company,
                "property_type": property_type,
                "url": url,
                "name": p_name,
                "reasons": ["掲載終了検知 (404/掲載終了文言)"],
                "is_critical": False,
            }

    # 2. データ妥当性検証 (PropertyDataValidator)
    is_valid, reasons = PropertyDataValidator.validate_property(item, property_type)

    if not is_valid:
        if eval_rec:
            apply_integrity_transition(eval_rec, is_valid=False, reasons=reasons)
        return {
            "status": "invalid",
            "company": company,
            "property_type": property_type,
            "url": url,
            "name": p_name,
            "reasons": reasons,
            "is_critical": True,
        }

    # 3. 正常
    if eval_rec:
        apply_integrity_transition(eval_rec, is_valid=True, reasons=[])

    return {
        "status": "valid",
        "company": company,
        "property_type": property_type,
        "url": url,
        "name": p_name,
        "reasons": [],
        "is_critical": False,
    }


def _instantiate_missing_eval_record(
    item: Any,
    ptype: str,
    company: str,
    res: dict[str, Any],
) -> PropertyEvaluation | None:
    url = res.get("url") or getattr(item, "pageUrl", "") or ""
    if not url or res.get("status") not in ("invalid", "delisted"):
        return None
    raw_id = getattr(item, "id", 0)
    prop_id = raw_id if isinstance(raw_id, int) else 0
    rec = PropertyEvaluation(
        property_url=url,
        company=company,
        property_type=ptype,
        property_id=prop_id,
        analysis_status="skipped_by_budget",
    )
    if res["status"] == "delisted":
        rec.is_published = False
        rec.delisted_at = timezone.now()
        rec.needs_recrawl = False
        rec.heal_status = "healthy"
    else:
        apply_integrity_transition(rec, is_valid=False, reasons=list(res.get("reasons") or []))
    return rec


async def _validate_single_property(
    sem: asyncio.Semaphore,
    item: Any,
    ptype: str,
    company: str,
    eval_rec: PropertyEvaluation | None,
    skip_url_check: bool = False,
) -> tuple[dict[str, Any], PropertyEvaluation | None]:
    async with sem:
        res = await process_property_validation(item, ptype, company, eval_rec, skip_url_check=skip_url_check)
        if eval_rec is None:
            eval_rec = _instantiate_missing_eval_record(item, ptype, company, res)
        return res, eval_rec


async def _run_parallel_validation(
    tasks_input: list[tuple[Any, str, str, PropertyEvaluation | None]],
    concurrency: int = 15,
    skip_url_check: bool = False,
) -> list[tuple[dict[str, Any], PropertyEvaluation | None]]:
    sem = asyncio.Semaphore(concurrency)
    coros = [
        _validate_single_property(sem, item, ptype, company, eval_rec, skip_url_check=skip_url_check)
        for item, ptype, company, eval_rec in tasks_input
    ]
    return await asyncio.gather(*coros)


def _safe_close_old_connections() -> None:
    """Close stale DB connections when DB access is active; ignore pytest-django blocked non-DB unit tests."""
    try:
        close_old_connections()
    except RuntimeError:
        return


def _fetch_eval_chunk_with_retry(chunk: list[str], max_retries: int = 3) -> list[PropertyEvaluation]:
    for attempt in range(max_retries):
        try:
            _safe_close_old_connections()
            return list(PropertyEvaluation.objects.filter(property_url__in=chunk))
        except OperationalError as oe:
            _safe_close_old_connections()
            if attempt >= max_retries - 1:
                raise
            logger.warning("OperationalError in batch_resolve_evaluations (attempt %d/%d): %s", attempt + 1, max_retries, oe)
            time.sleep(0.2 * (attempt + 1))
    return []


def batch_resolve_evaluations(urls: list[str], chunk_size: int = 1000) -> dict[str, PropertyEvaluation]:
    """
    URLリストに対応するPropertyEvaluationレコードをチャンク分割して一括取得する。
    1件ごとの個別SELECTクエリ発行によるN+1問題およびMySQL/ProxySQLの接続切断を防止する。
    戻り値: {property_url: PropertyEvaluation}
    """
    if not urls:
        return {}

    unique_urls = list(dict.fromkeys(urls))
    eval_map: dict[str, PropertyEvaluation] = {}
    for i in range(0, len(unique_urls), chunk_size):
        chunk = unique_urls[i:i + chunk_size]
        for rec in _fetch_eval_chunk_with_retry(chunk):
            eval_map[rec.property_url] = rec
    return eval_map


def _fetch_model_candidates_with_retry(model_cls: Any, since_date: Any, max_retries: int = 3) -> list[Any]:
    for attempt in range(max_retries):
        try:
            _safe_close_old_connections()
            qs = model_cls.objects.all()
            if since_date and hasattr(model_cls, "inputDate"):
                qs = qs.filter(inputDate__gte=since_date)
            return list(qs)
        except OperationalError as oe:
            _safe_close_old_connections()
            if attempt >= max_retries - 1:
                raise
            logger.warning("OperationalError scanning %s (attempt %d/%d): %s", getattr(model_cls, "__name__", str(model_cls)), attempt + 1, max_retries, oe)
            time.sleep(0.2 * (attempt + 1))
    return []


def _save_eval_with_retry(eval_rec: PropertyEvaluation, max_retries: int = 3) -> None:
    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                eval_rec.save()
            return
        except OperationalError as oe:
            _safe_close_old_connections()
            if attempt >= max_retries - 1:
                raise
            logger.warning("OperationalError saving PropertyEvaluation (attempt %d/%d): %s", attempt + 1, max_retries, oe)
            time.sleep(0.2 * (attempt + 1))


def validate_data(
    days: int | None = None,
    scan_all: bool = False,
    concurrency: int | None = None,
    skip_url_check: bool = False,
):
    bound_mysql_timeouts()
    if concurrency is None:
        try:
            concurrency = int(os.getenv("VALIDATE_DATA_CONCURRENCY", "15").strip())
        except ValueError:
            concurrency = 15
    if concurrency < 1:
        concurrency = 15

    if not skip_url_check:
        env_skip = os.getenv("VALIDATE_DATA_SKIP_URL_CHECK", "").strip().lower()
        if env_skip in ("true", "1", "yes"):
            skip_url_check = True

    logger.info(
        "Starting automated scraping validation and data integrity checks (concurrency=%d, skip_url_check=%s)...",
        concurrency,
        skip_url_check,
    )
    
    if scan_all:
        days_limit = None
        logger.info("Full scan mode enabled: scanning all records in database.")
    else:
        if days is not None:
            if days < 0:
                raise ValueError(f"days must be non-negative: {days}")
            days_limit = days if days > 0 else None
        else:
            env_val = os.getenv("VALIDATE_DATA_DAYS", "7").strip()
            try:
                val = int(env_val)
                days_limit = val if val > 0 else None
            except ValueError:
                days_limit = 7
        if days_limit:
            logger.info("Recent scan mode enabled: scanning records from the last %d days.", days_limit)
        else:
            logger.info("Full scan mode enabled via days/VALIDATE_DATA_DAYS=0.")
            
    since_date = (datetime.datetime.now(tz=datetime.timezone.utc).date() - datetime.timedelta(days=days_limit)) if days_limit else None
    
    anomalies = []
    delisted_count = 0
    recrawl_queued_count = 0
    
    models = get_all_models_flat()
    
    raw_candidates: list[tuple[Any, str, str, str]] = []
    for model_cls, company, ptype in models:
        for item in _fetch_model_candidates_with_retry(model_cls, since_date):
            url = getattr(item, "pageUrl", "")
            if not url:
                continue
            raw_candidates.append((item, ptype, company, url))

    # N+1問題を解消: 全URLからPropertyEvaluationを一括バッチ照会
    all_urls = [c[3] for c in raw_candidates]
    eval_lookup = batch_resolve_evaluations(all_urls)

    tasks_input: list[tuple[Any, str, str, PropertyEvaluation | None]] = [
        (item, ptype, company, copy.copy(eval_lookup.get(url)) if eval_lookup.get(url) is not None else None)
        for item, ptype, company, url in raw_candidates
    ]

    logger.info("Total properties to validate: %d. Running parallel verification...", len(tasks_input))

    if tasks_input:
        results = async_to_sync(_run_parallel_validation)(
            tasks_input,
            concurrency=concurrency,
            skip_url_check=skip_url_check,
        )
        _safe_close_old_connections()
        for res, eval_rec in results:
            if eval_rec:
                _save_eval_with_retry(eval_rec)

            if res["status"] == "delisted":
                delisted_count += 1
            elif res["status"] == "invalid":
                recrawl_queued_count += 1
                anomalies.append(res)
                        
    logger.info(
        "Scan finished. Anomalies: %d, Delisted: %d, Auto-Heal queued: %d",
        len(anomalies), delisted_count, recrawl_queued_count
    )
    
    # HTMLパースエラー（monitor_error_pages.py）のレポート読み込み
    html_errors_list = []
    try:
        logger.info("Running monitor_error_pages.py as a subprocess...")
        crawler_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(crawler_dir, "scripts", "ops", "monitor_error_pages.py")
        if not os.path.exists(script_path):
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor_error_pages.py")
        if os.path.exists(script_path):
            subprocess.run([sys.executable, script_path], check=True)
        
        today_str = datetime.datetime.now(tz=datetime.timezone.utc).date().strftime("%Y%m%d")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        report_path = os.path.join(project_root, "logs", f"error_report_{today_str}.json")
        if os.path.exists(report_path):
            with open(report_path, encoding="utf-8") as f:
                rep = json.load(f)
                html_errors_list = rep.get("recent_details", [])
    except Exception:
        logger.exception("Failed to integrate monitor_error_pages")
        
    # Slack dev-agent 向けレポート作成（アラートチャンネルは汚染せず dev-agent に集約）
    if anomalies or html_errors_list or delisted_count > 0:
        msg_lines = [
            "📋 *【データ整合性検証＆生存確認サマリー (#dev-agent)】*",
            f"• *掲載終了検知 (非公開化)*: {delisted_count:,} 件",
            f"• *データ不正検知 (Auto-Healパーサー改修対象)*: {recrawl_queued_count:,} 件",
            f"• *HTMLパースエラー*: {len(html_errors_list):,} 件",
            "",
        ]
        if anomalies:
            msg_lines.append("🔍 *検知されたデータ異常（抜粋）*:")
            for a in anomalies[:5]:
                reasons_str = ", ".join(a["reasons"])
                msg_lines.append(f"  - [{a['company']}/{a['property_type']}] {reasons_str} | URL: {a['url']}")
            if len(anomalies) > 5:
                msg_lines.append(f"  - (他 {len(anomalies) - 5} 件)")

        if html_errors_list:
            msg_lines.append("\n🚨 *HTMLエラー（抜粋）*:")
            for err in html_errors_list[:5]:
                msg_lines.append(f"  - [{err.get('company_type')}] {err.get('reason')} | URL: {err.get('url')}")
            if len(html_errors_list) > 5:
                msg_lines.append(f"  - (他 {len(html_errors_list) - 5} 件)")

        msg_lines.append("\n※ 掲載終了物件は非公開化してリトライ除外、データ不正物件は `needs_parser_fix=True` を付与しパーサー修復待ちとしました。")
        full_report = "\n".join(msg_lines)
        logger.info("Reporting validation summary to dev-agent channel:\n%s", full_report)
        async_to_sync(send_dev_report)(full_report)
    else:
        logger.info("No scraping anomalies, delisted items, or HTML errors detected. Data integrity is clean.")


if __name__ == "__main__":
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)
        
    parser = argparse.ArgumentParser(description="Validate property data integrity.")
    parser.add_argument("--all", action="store_true", help="Scan all historical records without date limit.")
    parser.add_argument("--days", type=int, default=None, help="Number of past days to scan (default: 7).")
    parser.add_argument("--concurrency", type=int, default=None, help="Parallel concurrency for URL checks (default: 15).")
    parser.add_argument("--skip-url-check", action="store_true", help="Skip HTTP URL active checks for faster validation.")
    cli_args = parser.parse_args()
    
    validate_data(
        days=cli_args.days,
        scan_all=cli_args.all,
        concurrency=cli_args.concurrency,
        skip_url_check=cli_args.skip_url_check,
    )

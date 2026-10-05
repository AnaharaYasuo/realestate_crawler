import argparse
import asyncio
import datetime
import json
import logging
import os
import subprocess
import sys
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
from django.db import transaction
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
from package.utils.data_validator import PropertyDataValidator
from package.utils.slack import send_dev_report, verify_url_active

logger = logging.getLogger(__name__)


def get_all_models_flat():
    """全物件種別のモデルクラスとその判定タグのリストを返す"""
    return [
        (MitsuiMansion, "mitsui", "mansion"), (MitsuiKodate, "mitsui", "kodate"), (MitsuiTochi, "mitsui", "tochi"),
        (MitsuiInvestmentKodate, "mitsui", "invest_kodate"), (MitsuiInvestmentApartment, "mitsui", "apartment"),
        
        (SumifuMansion, "sumifu", "mansion"), (SumifuKodate, "sumifu", "kodate"), (SumifuTochi, "sumifu", "tochi"),
        (SumifuInvestmentKodate, "sumifu", "invest_kodate"), (SumifuInvestmentApartment, "sumifu", "apartment"),
        
        (TokyuMansion, "tokyu", "mansion"), (TokyuKodate, "tokyu", "kodate"), (TokyuTochi, "tokyu", "tochi"),
        (TokyuInvestmentKodate, "tokyu", "invest_kodate"), (TokyuInvestmentApartment, "tokyu", "apartment"),
        
        (NomuraMansion, "nomura", "mansion"), (NomuraKodate, "nomura", "kodate"), (NomuraTochi, "nomura", "tochi"),
        (NomuraInvestmentKodate, "nomura", "invest_kodate"), (NomuraInvestmentApartment, "nomura", "apartment"),
        
        (MisawaMansion, "misawa", "mansion"), (MisawaKodate, "misawa", "kodate"), (MisawaTochi, "misawa", "tochi"),
        (MisawaInvestmentKodate, "misawa", "invest_kodate"), (MisawaInvestmentApartment, "misawa", "apartment"),
        
        (AthomeMansion, "athome", "mansion"), (AthomeKodate, "athome", "kodate"), (AthomeTochi, "athome", "tochi"),
        (AthomeInvestmentApartment, "athome", "apartment"),
        
        (HomesMansion, "homes", "mansion"), (HomesKodate, "homes", "kodate"), (HomesTochi, "homes", "tochi"),
        (HomesInvestmentApartment, "homes", "apartment"),
    ]


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
    2. スペック異常判定時: needs_recrawl=True, data_quality_issue 記録, 予測価格0リセット
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
                eval_rec.first_stage_predicted_price = 0
                eval_rec.second_stage_predicted_price = 0
                eval_rec.is_slack_notified = True
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
            eval_rec.is_published = True
            eval_rec.needs_parser_fix = True
            eval_rec.needs_recrawl = False
            eval_rec.data_quality_issue = "; ".join(reasons)
            eval_rec.first_stage_predicted_price = 0
            eval_rec.second_stage_predicted_price = 0
            eval_rec.is_slack_notified = True  # ML推論および推薦アラートから除外
        return {
            "status": "invalid",
            "company": company,
            "property_type": property_type,
            "url": url,
            "name": p_name,
            "reasons": reasons,
            "is_critical": True,
        }

    # 正常
    if eval_rec:
        eval_rec.is_published = True
        eval_rec.needs_parser_fix = False
        eval_rec.needs_recrawl = False
        eval_rec.data_quality_issue = ""

    return {
        "status": "valid",
        "company": company,
        "property_type": property_type,
        "url": url,
        "name": p_name,
        "reasons": [],
        "is_critical": False,
    }


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


def validate_data(
    days: int | None = None,
    scan_all: bool = False,
    concurrency: int | None = None,
    skip_url_check: bool = False,
):
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
    
    # 全モデルの対象レコードを収集
    tasks_input: list[tuple[Any, str, str, PropertyEvaluation | None]] = []
    for model_cls, company, ptype in models:
        qs = model_cls.objects.all()
        if since_date and hasattr(model_cls, "inputDate"):
            qs = qs.filter(inputDate__gte=since_date)
            
        for item in qs:
            url = getattr(item, "pageUrl", "")
            if not url:
                continue

            eval_rec = PropertyEvaluation.objects.filter(property_url=url).first()
            tasks_input.append((item, ptype, company, eval_rec))

    logger.info("Total properties to validate: %d. Running parallel verification...", len(tasks_input))

    if tasks_input:
        results = async_to_sync(_run_parallel_validation)(
            tasks_input,
            concurrency=concurrency,
            skip_url_check=skip_url_check,
        )
        for res, eval_rec in results:
            if eval_rec:
                with transaction.atomic():
                    eval_rec.save()

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
            with open(report_path, "r", encoding="utf-8") as f:
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

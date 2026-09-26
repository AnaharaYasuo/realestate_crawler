# ruff: noqa: E402
import os
import logging
import sys
import signal
import traceback
import time
import inspect
import asyncio
import datetime
import html
from typing import Any
from flask import Flask, jsonify, request
from django.apps import apps
from django.db import close_old_connections
from django.db.models import Q

import realestateSettings
realestateSettings.configure()  # package.apiがインポートされる前に実施する。
from package.utils.logging_config import configure_logging
configure_logging()
logger = logging.getLogger(__name__)

# Import keys for remaining routes (if any) or shared usage
from package.api.api import API_KEY_MANSION_ALL_START, API_KEY_KILL
from package.models.crawler_task_execution import CrawlerTaskExecution
from package.utils.selector_loader import SelectorLoader
from package.utils.api_logger import setup_api_logging
from package.utils.failure_reporter import FailureReporter

# Import Blueprints
from routes.mitsui_routes import mitsui_bp
from routes.sumifu_routes import sumifu_bp
from routes.tokyu_routes import tokyu_bp
from routes.nomura_routes import nomura_bp
from routes.tokyu_investment_routes import tokyu_investment_bp
from routes.nomura_investment_routes import nomura_investment_bp
from routes.sumifu_investment_routes import sumifu_investment_bp
from routes.mitsui_investment_routes import mitsui_investment_bp
from routes.misawa_routes import misawa_bp
from routes.misawa_investment_routes import misawa_investment_bp
from routes.athome_routes import athome_bp
from routes.homes_routes import homes_bp
from routes.evaluation_routes import evaluation_bp
from routes.swagger_routes import swagger_bp


# Import specific functions needed for dispatch and allMansionStart
from routes.mitsui_routes import mitsuiMansionStart, mitsuiKodateStart, mitsuiTochiStart
from routes.sumifu_routes import sumifuMansionStart, sumifuKodateStart, sumifuTochiStart
from routes.tokyu_routes import tokyuMansionStart, tokyuKodateStart, tokyuTochiStart
from routes.nomura_routes import nomuraMansionStart, nomuraKodateStart, nomuraTochiStart
from routes.misawa_routes import misawaMansionStart, misawaKodateStart, misawaTochiStart
from routes.mitsui_investment_routes import mitsuiInvestKodateStart, mitsuiInvestApartmentStart
from routes.sumifu_investment_routes import sumifuInvestKodateStart, sumifuInvestApartmentStart
from routes.tokyu_investment_routes import tokyuInvestKodateStart, tokyuInvestApartmentStart
from routes.nomura_investment_routes import nomuraInvestKodateStart, nomuraInvestApartmentStart
from routes.misawa_investment_routes import misawaInvestStart, misawaInvestKodateStart, misawaInvestApartmentStart
from routes.athome_routes import athomeMansionStart, athomeKodateStart, athomeInvestApartmentStart, athomeTochiStart
from routes.homes_routes import homesMansionStart, homesKodateStart, homesInvestApartmentStart, homesTochiStart
from routes.smtrc_routes import smtrcMansionStart, smtrcKodateStart, smtrcTochiStart, smtrcInvestmentStart, smtrc_bp
from routes.sumai1_routes import sumai1MansionStart, sumai1KodateStart, sumai1TochiStart, sumai1InvestmentStart, sumai1_bp
from routes.sekisui_routes import sekisuiMansionStart, sekisuiKodateStart, sekisuiTochiStart, sekisui_bp
from routes.afr_routes import afrMansionStart, afrKodateStart, afrTochiStart, afr_bp
from routes.mizuho_routes import mizuhoMansionStart, mizuhoKodateStart, mizuhoTochiStart, mizuhoInvestmentStart, mizuho_bp
from routes.odakyu_routes import odakyuMansionStart, odakyuKodateStart, odakyuTochiStart, odakyuInvestmentStart, odakyu_bp
from routes.totate_routes import totateMansionStart, totateKodateStart, totateTochiStart, totate_bp
from routes.daiwa_routes import daiwaMansionStart, daiwaKodateStart, daiwaTochiStart, daiwa_bp
from routes.sumirin_routes import sumirinMansionStart, sumirinKodateStart, sumirinTochiStart, sumirinInvestmentStart, sumirin_bp
from routes.heim_routes import heimMansionStart, heimKodateStart, heimTochiStart, heim_bp
from routes.rearie_routes import rearieMansionStart, rearieKodateStart, rearieTochiStart, rearie_bp
from routes.keio_routes import keioMansionStart, keioKodateStart, keioTochiStart, keio_bp
from routes.seibu_routes import seibuMansionStart, seibuKodateStart, seibuTochiStart, seibu_bp
from routes.keikyu_routes import keikyuMansionStart, keikyuKodateStart, keikyuTochiStart, keikyu_bp
from routes.sotetsu_routes import sotetsuMansionStart, sotetsuKodateStart, sotetsuTochiStart, sotetsu_bp
from routes.keisei_routes import keiseiMansionStart, keiseiKodateStart, keiseiTochiStart, keisei_bp
from routes.daikyo_routes import daikyoMansionStart, daikyoKodateStart, daikyoTochiStart, daikyo_bp


app = Flask(__name__)  # NOSONAR

# Register Blueprints
app.register_blueprint(mitsui_bp)
app.register_blueprint(sumifu_bp)
app.register_blueprint(tokyu_bp)
app.register_blueprint(nomura_bp)
app.register_blueprint(tokyu_investment_bp)
app.register_blueprint(nomura_investment_bp)
app.register_blueprint(sumifu_investment_bp)
app.register_blueprint(mitsui_investment_bp)
app.register_blueprint(misawa_bp)
app.register_blueprint(misawa_investment_bp)
app.register_blueprint(athome_bp)
app.register_blueprint(homes_bp)
app.register_blueprint(smtrc_bp)
app.register_blueprint(sumai1_bp)
app.register_blueprint(sekisui_bp)
app.register_blueprint(afr_bp)
app.register_blueprint(mizuho_bp)
app.register_blueprint(odakyu_bp)
app.register_blueprint(totate_bp)
app.register_blueprint(daiwa_bp)
app.register_blueprint(sumirin_bp)
app.register_blueprint(heim_bp)
app.register_blueprint(rearie_bp)
app.register_blueprint(keio_bp)
app.register_blueprint(seibu_bp)
app.register_blueprint(keikyu_bp)
app.register_blueprint(sotetsu_bp)
app.register_blueprint(keisei_bp)
app.register_blueprint(daikyo_bp)
app.register_blueprint(evaluation_bp)
app.register_blueprint(swagger_bp)

# リクエスト・レスポンスの送受信ペイロード構造化ログ出力設定
setup_api_logging(app)

@app.before_request
def enforce_api_authentication():
    # OPTIONS は CORS プリフライトのため無条件で許可
    if request.method == 'OPTIONS':
        return "", 200

    # ドキュメント（Swagger UI, OpenAPI spec）は公開アクセス許可
    if request.path in ('/docs', '/api/openapi.yaml') or request.path.startswith('/docs/'):
        return None

    # ヘルスチェックエンドポイント
    if request.path in ('/', '/health', '/api/health'):
        return None

    # すべての /api/ エンドポイントに API キー認証を適用
    if request.path.startswith('/api/'):
        api_key = os.getenv("ESTIMATION_API_KEY", "")
        request_key = request.headers.get("X-API-KEY", "")

        if os.getenv("IS_CLOUD") and not api_key:
            return {
                "success": False,
                "message": "Server configuration error: ESTIMATION_API_KEY is not configured"
            }, 500

        if api_key and request_key != api_key:
            return {
                "success": False,
                "message": "Unauthorized: Invalid or missing X-API-KEY header"
            }, 401

    return None


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-API-KEY'
    return response


# cloud functionsとComputeEngineはサーバーレスVPCで接続

# デバッグ方法
# PythonRunよりデバッグを開始するとflaskが起動。
# そのうえで、http://127.0.0.1:8000/api/sumifu/mansion/startにアクセス


# Cloud Function entry points wrapper (if needed for GCP environment looking for these specific names in main.py)
# If GCP is configured to look for "parseMitsuiStartMansionAsyncPubSub" in main.py, we need wrappers.
# The original main.py had these.
def parse_mitsui_start_mansion_async_pubsub(event, context):
    return mitsuiMansionStart()

parseMitsuiStartMansionAsyncPubSub = parse_mitsui_start_mansion_async_pubsub


def parse_sumifu_start_mansion_async_pubsub(event, context):
    return sumifuMansionStart()

parseSumifuStartMansionAsyncPubSub = parse_sumifu_start_mansion_async_pubsub


@app.route(API_KEY_MANSION_ALL_START, methods=['OPTIONS', 'POST', 'GET'])
def all_mansion_start():
    mitsuiMansionStart()
    sumifuMansionStart()
    tokyuMansionStart()
    misawaMansionStart()
    return "OK"

allMansionStart = all_mansion_start


@app.route(API_KEY_KILL, methods=['OPTIONS', 'POST', 'GET'])
def seriouslykill():
    # セキュリティ保護: リモートからの不正シャットダウン（DoS）を防止
    if os.getenv("ALLOW_REMOTE_SHUTDOWN", "false").lower() != "true":
        return ("Forbidden: Remote shutdown is disabled.", 403)
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return "Shutting down..."



def get_dispatch_map():
    SelectorLoader.clear_cache()

    return {
        ("sumifu", "mansion"): sumifuMansionStart,
        ("sumifu", "kodate"): sumifuKodateStart,
        ("sumifu", "tochi"): sumifuTochiStart,
        ("sumifu", "investment"): sumifuInvestKodateStart,
        ("sumifu", "invest_kodate"): sumifuInvestKodateStart,
        ("sumifu", "invest_apartment"): sumifuInvestApartmentStart,
        ("mitsui", "mansion"): mitsuiMansionStart,
        ("mitsui", "kodate"): mitsuiKodateStart,
        ("mitsui", "tochi"): mitsuiTochiStart,
        ("mitsui", "investment"): mitsuiInvestKodateStart,
        ("mitsui", "invest_kodate"): mitsuiInvestKodateStart,
        ("mitsui", "invest_apartment"): mitsuiInvestApartmentStart,
        ("tokyu", "mansion"): tokyuMansionStart,
        ("tokyu", "kodate"): tokyuKodateStart,
        ("tokyu", "tochi"): tokyuTochiStart,
        ("tokyu", "investment"): tokyuInvestKodateStart,
        ("tokyu", "invest_kodate"): tokyuInvestKodateStart,
        ("tokyu", "invest_apartment"): tokyuInvestApartmentStart,
        ("nomura", "mansion"): nomuraMansionStart,
        ("nomura", "kodate"): nomuraKodateStart,
        ("nomura", "tochi"): nomuraTochiStart,
        ("nomura", "investment"): nomuraInvestKodateStart,
        ("nomura", "invest_kodate"): nomuraInvestKodateStart,
        ("nomura", "invest_apartment"): nomuraInvestApartmentStart,
        ("misawa", "mansion"): misawaMansionStart,
        ("misawa", "kodate"): misawaKodateStart,
        ("misawa", "tochi"): misawaTochiStart,
        ("misawa", "investment"): misawaInvestStart,
        ("misawa", "invest_kodate"): misawaInvestKodateStart,
        ("misawa", "invest_apartment"): misawaInvestApartmentStart,
        ("athome", "mansion"): athomeMansionStart,
        ("athome", "kodate"): athomeKodateStart,
        ("athome", "tochi"): athomeTochiStart,
        ("athome", "invest_apartment"): athomeInvestApartmentStart,
        ("athome", "investment"): athomeInvestApartmentStart,
        ("homes", "mansion"): homesMansionStart,
        ("homes", "kodate"): homesKodateStart,
        ("homes", "tochi"): homesTochiStart,
        ("homes", "invest_apartment"): homesInvestApartmentStart,
        ("homes", "investment"): homesInvestApartmentStart,
        ("smtrc", "mansion"): smtrcMansionStart,
        ("smtrc", "kodate"): smtrcKodateStart,
        ("smtrc", "tochi"): smtrcTochiStart,
        ("smtrc", "investment"): smtrcInvestmentStart,
        ("smtrc", "invest_apartment"): smtrcInvestmentStart,
        ("sumai1", "mansion"): sumai1MansionStart,
        ("sumai1", "kodate"): sumai1KodateStart,
        ("sumai1", "tochi"): sumai1TochiStart,
        ("sumai1", "investment"): sumai1InvestmentStart,
        ("sumai1", "invest_apartment"): sumai1InvestmentStart,
        ("sekisui", "mansion"): sekisuiMansionStart,
        ("sekisui", "kodate"): sekisuiKodateStart,
        ("sekisui", "tochi"): sekisuiTochiStart,
        ("afr", "mansion"): afrMansionStart,
        ("afr", "kodate"): afrKodateStart,
        ("afr", "tochi"): afrTochiStart,
        ("mizuho", "mansion"): mizuhoMansionStart,
        ("mizuho", "kodate"): mizuhoKodateStart,
        ("mizuho", "tochi"): mizuhoTochiStart,
        ("mizuho", "investment"): mizuhoInvestmentStart,
        ("mizuho", "invest_apartment"): mizuhoInvestmentStart,
        ("odakyu", "mansion"): odakyuMansionStart,
        ("odakyu", "kodate"): odakyuKodateStart,
        ("odakyu", "tochi"): odakyuTochiStart,
        ("odakyu", "investment"): odakyuInvestmentStart,
        ("odakyu", "invest_apartment"): odakyuInvestmentStart,
        ("totate", "mansion"): totateMansionStart,
        ("totate", "kodate"): totateKodateStart,
        ("totate", "tochi"): totateTochiStart,
        ("daiwa", "mansion"): daiwaMansionStart,
        ("daiwa", "kodate"): daiwaKodateStart,
        ("daiwa", "tochi"): daiwaTochiStart,
        ("sumirin", "mansion"): sumirinMansionStart,
        ("sumirin", "kodate"): sumirinKodateStart,
        ("sumirin", "tochi"): sumirinTochiStart,
        ("sumirin", "investment"): sumirinInvestmentStart,
        ("heim", "mansion"): heimMansionStart,
        ("heim", "kodate"): heimKodateStart,
        ("heim", "tochi"): heimTochiStart,
        ("rearie", "mansion"): rearieMansionStart,
        ("rearie", "kodate"): rearieKodateStart,
        ("rearie", "tochi"): rearieTochiStart,
        ("keio", "mansion"): keioMansionStart,
        ("keio", "kodate"): keioKodateStart,
        ("keio", "tochi"): keioTochiStart,
        ("seibu", "mansion"): seibuMansionStart,
        ("seibu", "kodate"): seibuKodateStart,
        ("seibu", "tochi"): seibuTochiStart,
        ("keikyu", "mansion"): keikyuMansionStart,
        ("keikyu", "kodate"): keikyuKodateStart,
        ("keikyu", "tochi"): keikyuTochiStart,
        ("sotetsu", "mansion"): sotetsuMansionStart,
        ("sotetsu", "kodate"): sotetsuKodateStart,
        ("sotetsu", "tochi"): sotetsuTochiStart,
        ("keisei", "mansion"): keiseiMansionStart,
        ("keisei", "kodate"): keiseiKodateStart,
        ("keisei", "tochi"): keiseiTochiStart,
        ("daikyo", "mansion"): daikyoMansionStart,
        ("daikyo", "kodate"): daikyoKodateStart,
        ("daikyo", "tochi"): daikyoTochiStart,
    }


def _execute_crawl_func(func: Any, company: str, prop_type: str) -> bool:
    try:
        if inspect.iscoroutinefunction(func):
            asyncio.run(func())
        else:
            func()
        return True
    except Exception as e:
        logging.exception(f"Error during crawl task for {company} - {prop_type}: {e}")
        return False


def _count_scraped_items(company: str, prop_type: str, start_dt: datetime.datetime) -> int:
    if not apps:
        return 0
    try:
        target = prop_type.lower().replace("_", "")
        for model in apps.get_models():
            m_name = model.__name__.lower()
            if m_name.startswith(company.lower()):
                rest = m_name[len(company):]
                if rest in (target, target.replace("invest", "investment")):
                    q = Q(updateDateTime__gte=start_dt) | Q(inputDateTime__gte=start_dt) if hasattr(model, "updateDateTime") else Q(inputDateTime__gte=start_dt)
                    return model.objects.filter(q).count()
    except Exception as ce:
        logging.exception(f"Failed to count scraped items: {ce}")
    return 0


def _update_task_record(task_rec: Any, success: bool) -> None:
    if not task_rec:
        return
    task_rec.status = "COMPLETED" if success else "FAILED"
    task_rec.jobs_success = 1 if success else 0
    task_rec.jobs_failed = 0 if success else 1
    task_rec.save()


def execute_crawl_task(company: str, prop_type: str, execution_date: str = None):
    dispatch = get_dispatch_map()
    func = dispatch.get((company.lower(), prop_type.lower()))
    if not func:
        return False, 0, 0

    start_t = time.time()
    start_dt = datetime.datetime.now()
    exec_dt = datetime.datetime.strptime(execution_date, "%Y-%m-%d").date() if execution_date else datetime.date.today()

    task_rec, _ = CrawlerTaskExecution.objects.update_or_create(
        execution_date=exec_dt,
        task_index=abs(hash(f"{company}_{prop_type}")) % 1000,
        defaults={"task_count": 1, "status": "RUNNING", "jobs_assigned": 1}
    )

    success = _execute_crawl_func(func, company, prop_type)
    elapsed = int(time.time() - start_t)
    scraped_count = _count_scraped_items(company, prop_type, start_dt)
    _update_task_record(task_rec, success)

    return success, scraped_count, elapsed


@app.route('/api/crawl/task', methods=['POST'])
def handle_crawl_task():
    close_old_connections()
    try:
        data = request.get_json(silent=True) or {}
        company = data.get("company", "").lower()
        prop_type = (data.get("property_type") or data.get("type") or "").lower()
        execution_date = data.get("execution_date")

        safe_company = html.escape(company)
        safe_prop_type = html.escape(prop_type)

        if not company or not prop_type:
            return jsonify({"error": "Missing company or property_type"}), 400

        dispatch = get_dispatch_map()
        if (company, prop_type) not in dispatch:
            return jsonify({"error": f"Unknown job: {safe_company} - {safe_prop_type}"}), 404

        success, count, elapsed = execute_crawl_task(company, prop_type, execution_date)
        if success:
            return jsonify({"status": "success", "company": safe_company, "property_type": safe_prop_type, "scraped_count": count, "elapsed_seconds": elapsed}), 200
        else:
            # Cloud Tasks 無限リトライ防止: 0件取得・パース異常・連続タイムアウト等は HTTP 200 でタスク消化
            return jsonify({"status": "failed", "company": safe_company, "property_type": safe_prop_type, "error": "Crawl execution failed"}), 200
    finally:
        close_old_connections()


if __name__ == "__main__":
    configure_logging()

    # CLI support for direct crawl execution
    args = sys.argv[1:]
    if args:
        company = ""
        prop_type = ""
        for arg in args:
            if arg.startswith("--company="):
                company = arg.split("=")[1].lower()
            elif arg.startswith("--type="):
                prop_type = arg.split("=")[1].lower()
            elif arg.startswith("COMPANY="):
                company = arg.split("=")[1].lower()
            elif arg.startswith("TYPE="):
                prop_type = arg.split("=")[1].lower()

        dispatch = get_dispatch_map()

        func = dispatch.get((company, prop_type))

        if func:
            stop_flag_file = "stop.flag"
            # Clean up any existing stop flag
            if os.path.exists(stop_flag_file):
                try:
                    os.remove(stop_flag_file)
                except Exception:
                    pass

            # Set up signal handling globally before execution
            def handle_sigterm(signum, frame):
                try:
                    logging.info(f"Received signal {signum}, setting stop flag and forcing exit...")
                    print(f"Received signal {signum}, setting stop flag and forcing exit...", flush=True)
                    # Create stop flag for other threads/processes
                    with open(stop_flag_file, "w") as f:
                        f.write("STOP")
                finally:
                    # Force exit immediately
                    os._exit(0)

            signal.signal(signal.SIGTERM, handle_sigterm)
            signal.signal(signal.SIGINT, handle_sigterm)

            logger.info(f"Starting {company} {prop_type} crawl via CLI...")
            try:
                # If it's a co-routine function, run it with asyncio
                if inspect.iscoroutinefunction(func):
                    asyncio.run(func())
                else:
                    func()
            except Exception as e:
                tb = traceback.format_exc()
                logger.exception(f"Error during crawl execution: {e}")
                try:
                    FailureReporter.record_job_failure(
                        company=company,
                        property_type=prop_type,
                        error_type=type(e).__name__,
                        error_message=str(e),
                        exit_code=1,
                        traceback_str=tb
                    )
                except Exception as fre:
                    logger.warning(f"Failed to record failure telemetry: {fre}")
                sys.exit(1)
            logger.info(f"Execution finished for {company} {prop_type}")
            sys.exit(0)
        else:
            logger.error(f"Unknown combination: company={company}, type={prop_type}")
            logger.info("Usage: python main.py --company=[sumifu|mitsui|tokyu|nomura|misawa] --type=[mansion|invest_kodate|invest_apartment|investment]")
            sys.exit(1)

    port = int(os.getenv('PORT', '8000'))
    flask_debug = os.getenv('FLASK_DEBUG', 'false').lower() in ('true', '1')
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=flask_debug)  # NOSONAR


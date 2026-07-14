import os
import logging
import sys
import signal
from flask import Flask, request

import realestateSettings
realestateSettings.configure()  # package.apiがインポートされる前に実施する。

# Import keys for remaining routes (if any) or shared usage
from package.api.api import API_KEY_MANSION_ALL_START, API_KEY_KILL

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

# Import specific functions needed for allMansionStart if they are exposed in the modules
# Since mitsuiMansionStart etc are decorated as routes, they can still be imported if we need to call them directly
# However, the split files had them as regular functions inside too?
# Looking at my split code:
# mitsuiMansionStart is decorated with @mitsui_bp.route(...).
# It can be imported from routes.mitsui_routes
from routes.mitsui_routes import mitsuiMansionStart, mitsuiKodateStart, mitsuiTochiStart
from routes.sumifu_routes import sumifuMansionStart, sumifuKodateStart, sumifuTochiStart
from routes.tokyu_routes import tokyuMansionStart, tokyuKodateStart, tokyuTochiStart
from routes.nomura_routes import nomuraMansionStart, nomuraKodateStart, nomuraTochiStart
from routes.misawa_routes import misawaMansionStart, misawaKodateStart, misawaTochiStart
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


app = Flask(__name__)

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

# cloud functionsとComputeEngineはサーバーレスVPCで接続

# デバッグ方法
# PythonRunよりデバッグを開始するとflaskが起動。
# そのうえで、http://127.0.0.1:8000/api/sumifu/mansion/startにアクセス


# Cloud Function entry points wrapper (if needed for GCP environment looking for these specific names in main.py)
# If GCP is configured to look for "parseMitsuiStartMansionAsyncPubSub" in main.py, we need wrappers.
# The original main.py had these.
def parseMitsuiStartMansionAsyncPubSub(event, context):
    return mitsuiMansionStart()

def parseSumifuStartMansionAsyncPubSub(event, context):
    return sumifuMansionStart()


@app.route(API_KEY_MANSION_ALL_START, methods=['OPTIONS', 'POST', 'GET'])
def allMansionStart():
    mitsuiMansionStart()
    sumifuMansionStart()
    tokyuMansionStart()
    misawaMansionStart()
    return "OK"


@app.route(API_KEY_KILL, methods=['OPTIONS', 'POST', 'GET'])
def seriouslykill():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return "Shutting down..."


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout
    )

    # CLI support for direct crawl execution
    args = sys.argv[1:]
    if args:
        company = ""
        prop_type = ""
        for arg in args:
            if arg.startswith("--company="): company = arg.split("=")[1].lower()
            elif arg.startswith("--type="): prop_type = arg.split("=")[1].lower()
            elif arg.startswith("COMPANY="): company = arg.split("=")[1].lower()
            elif arg.startswith("TYPE="): prop_type = arg.split("=")[1].lower()
        
        # Import all start functions for CLI dispatch
        from package.utils.selector_loader import SelectorLoader
        SelectorLoader.clear_cache()
        
        from routes.mitsui_investment_routes import mitsuiInvestKodateStart, mitsuiInvestApartmentStart
        from routes.sumifu_investment_routes import sumifuInvestKodateStart, sumifuInvestApartmentStart
        from routes.tokyu_investment_routes import tokyuInvestKodateStart, tokyuInvestApartmentStart
        from routes.nomura_investment_routes import nomuraInvestKodateStart, nomuraInvestApartmentStart
        from routes.misawa_investment_routes import misawaInvestStart, misawaInvestKodateStart, misawaInvestApartmentStart
        from routes.athome_routes import athomeMansionStart, athomeKodateStart, athomeInvestApartmentStart, athomeTochiStart
        from routes.homes_routes import homesMansionStart, homesKodateStart, homesInvestApartmentStart, homesTochiStart

        dispatch = {
            ("sumifu", "mansion"): sumifuMansionStart,
            ("sumifu", "kodate"): sumifuKodateStart,
            ("sumifu", "tochi"): sumifuTochiStart,
            ("sumifu", "investment"): sumifuInvestKodateStart, # Default to kodate
            ("sumifu", "invest_kodate"): sumifuInvestKodateStart,
            ("sumifu", "invest_apartment"): sumifuInvestApartmentStart,
            ("mitsui", "mansion"): mitsuiMansionStart,
            ("mitsui", "kodate"): mitsuiKodateStart,
            ("mitsui", "tochi"): mitsuiTochiStart,
            ("mitsui", "investment"): mitsuiInvestKodateStart, # Default to kodate
            ("mitsui", "invest_kodate"): mitsuiInvestKodateStart,
            ("mitsui", "invest_apartment"): mitsuiInvestApartmentStart,
            
            ("tokyu", "mansion"): tokyuMansionStart,
            ("tokyu", "kodate"): tokyuKodateStart,
            ("tokyu", "tochi"): tokyuTochiStart,
            ("tokyu", "investment"): tokyuInvestKodateStart, # Default to kodate
            ("tokyu", "invest_kodate"): tokyuInvestKodateStart,
            ("tokyu", "invest_apartment"): tokyuInvestApartmentStart,
            
            ("nomura", "mansion"): nomuraMansionStart,
            ("nomura", "kodate"): nomuraKodateStart,
            ("nomura", "tochi"): nomuraTochiStart,
            ("nomura", "investment"): nomuraInvestKodateStart, # Default to kodate
            ("nomura", "invest_kodate"): nomuraInvestKodateStart,
            ("nomura", "invest_apartment"): nomuraInvestApartmentStart,
            
            ("misawa", "mansion"): misawaMansionStart,
            ("misawa", "kodate"): misawaKodateStart,
            ("misawa", "tochi"): misawaTochiStart,
            ("misawa", "investment"): misawaInvestStart, # All investment
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

        func = dispatch.get((company, prop_type))

        if func:
            # Clean up any existing stop flag
            if os.path.exists("stop.flag"):
                try:
                    os.remove("stop.flag")
                except:
                    pass

            # Set up signal handling globally before execution
            def handle_sigterm(signum, frame):
                try:
                    logging.info(f"Received signal {signum}, setting stop flag and forcing exit...")
                    print(f"Received signal {signum}, setting stop flag and forcing exit...", flush=True)
                    # Create stop flag for other threads/processes
                    with open("stop.flag", "w") as f:
                        f.write("STOP")
                finally:
                    # Force exit immediately
                    os._exit(0)

            signal.signal(signal.SIGTERM, handle_sigterm)
            signal.signal(signal.SIGINT, handle_sigterm)

            logging.info(f"Starting {company} {prop_type} crawl via CLI...")
            import asyncio
            import inspect
            try:
                # If it's a co-routine function, run it with asyncio
                if inspect.iscoroutinefunction(func):
                    asyncio.run(func())
                else:
                    func()
            except Exception as e:
                logging.error(f"Error during crawl execution: {e}")
                import traceback
                logging.error(traceback.format_exc())
            logging.info(f"Execution finished for {company} {prop_type}")
            sys.exit(0)
        else:
            logging.error(f"Unknown combination: company={company}, type={prop_type}")
            logging.info("Usage: python main.py --company=[sumifu|mitsui|tokyu|nomura|misawa] --type=[mansion|invest_kodate|invest_apartment|investment]")
            sys.exit(1)

    if not os.getenv('IS_CLOUD', ''):
        app.run(host='0.0.0.0', port=8000, debug=True)

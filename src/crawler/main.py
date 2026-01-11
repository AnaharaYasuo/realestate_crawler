import os
import logging
import sys
from flask import Flask, request

# Import keys for remaining routes (if any) or shared usage
from package.api.api import API_KEY_MANSION_ALL_START, API_KEY_KILL

import realestateSettings
realestateSettings.configure()  # package.apiがインポートされる前に実施する。

# Import Blueprints
from routes.mitsui_routes import mitsui_bp
from routes.sumifu_routes import sumifu_bp
from routes.tokyu_routes import tokyu_bp
from routes.nomura_routes import nomura_bp
from routes.tokyu_investment_routes import tokyu_investment_bp
from routes.sumifu_investment_routes import sumifu_investment_bp
from routes.misawa_routes import misawa_bp

# Import specific functions needed for allMansionStart if they are exposed in the modules
# Since mitsuiMansionStart etc are decorated as routes, they can still be imported if we need to call them directly
# However, the split files had them as regular functions inside too?
# Looking at my split code:
# mitsuiMansionStart is decorated with @mitsui_bp.route(...).
# It can be imported from routes.mitsui_routes
from routes.mitsui_routes import mitsuiMansionStart
from routes.sumifu_routes import sumifuMansionStart
from routes.tokyu_routes import tokyuMansionStart
from routes.nomura_routes import nomuraProStart
from routes.tokyu_investment_routes import tokyuInvestStart
from routes.sumifu_investment_routes import sumifuInvestStart
from routes.misawa_routes import misawaMansionStart


app = Flask(__name__)

# Register Blueprints
app.register_blueprint(mitsui_bp)
app.register_blueprint(sumifu_bp)
app.register_blueprint(tokyu_bp)
app.register_blueprint(nomura_bp)
app.register_blueprint(tokyu_investment_bp)
app.register_blueprint(sumifu_investment_bp)
app.register_blueprint(misawa_bp)

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
    if not os.getenv('IS_CLOUD', ''):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            stream=sys.stdout
        )
        app.run(host='0.0.0.0', port=8000, debug=True)

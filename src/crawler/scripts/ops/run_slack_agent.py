# -*- coding: utf-8 -*-
import os
import sys
import time
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# プロジェクトルートパスのセットアップ
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

CRAWLER_DIR = os.path.join(SRC_DIR, "crawler")
if CRAWLER_DIR not in sys.path:
    sys.path.insert(0, CRAWLER_DIR)


from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from package.utils.slack_agent import SlackAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("run_slack_agent")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass

def start_health_server(port: int = 8080):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"HTTP health check server started on port {port}.")
    return server

def main():
    port = int(os.getenv("PORT", "8080"))
    start_health_server(port)

    logger.info("Initializing Slack Agent Service...")
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    app_token = os.getenv("SLACK_APP_TOKEN")

    if not bot_token or not app_token or bot_token.startswith("xoxb-placeholder") or app_token.startswith("xapp-placeholder"):
        logger.warning("SLACK_BOT_TOKEN or SLACK_APP_TOKEN is missing or set to placeholder.")
        logger.info("Slack Agent is idle waiting for valid token configuration. Keeping HTTP server running for Cloud Run health checks.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Slack Agent stopped by user.")
            sys.exit(0)

    agent = SlackAgent()
    try:
        agent.start_bot()
    except KeyboardInterrupt:
        logger.info("Slack Agent stopped by user.")
    except Exception as e:
        logger.critical(f"Slack Agent encountered a fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()


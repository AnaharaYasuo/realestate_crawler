# -*- coding: utf-8 -*-
import os
import sys
import logging

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

def main():
    logger.info("Initializing Slack Agent Service...")
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    app_token = os.getenv("SLACK_APP_TOKEN")


    if not bot_token or not app_token:
        logger.error("Error: SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in environment variables.")
        logger.error("Please set SLACK_BOT_TOKEN (xoxb-...) and SLACK_APP_TOKEN (xapp-...) in .env file.")
        sys.exit(1)

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

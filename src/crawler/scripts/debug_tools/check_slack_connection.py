# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import realestateSettings
realestateSettings.configure()


from package.utils.slack import verify_slack_credentials

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

async def main():
    logger.info("Checking Slack connection status (silent auth.test)...")
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        logger.error("❌ SLACK_BOT_TOKEN is not set in environment!")
        sys.exit(1)
        
    # メッセージ投稿を行わずにトークン認証と権限を安全に検証
    is_ok, msg = await verify_slack_credentials(token)
    if is_ok:
        logger.info(f"✅ Slack connection is OK! {msg}")
        sys.exit(0)
    else:
        logger.error(f"❌ Slack authentication test FAILED: {msg}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())


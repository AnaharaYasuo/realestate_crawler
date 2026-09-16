# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import realestateSettings
realestateSettings.configure()


from package.utils.slack import send_crawling_summary_alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

async def main():
    logging.info("Checking Slack connection status...")
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        logging.error("❌ SLACK_BOT_TOKEN is not set in environment!")
        sys.exit(1)
        
    channel = os.getenv("SLACK_ALERT_PROPERTY_ALERT", "property_alert")
    logging.info(f"Targeting channel: {channel}")
    
    # 送信テストの実行
    success = await send_crawling_summary_alert("🔄 【接続テスト】 パイプライン事前接続チェックを実行中...")
    if success:
        logging.info("✅ Slack connection is OK! Bot is successfully posting to the channel.")
        sys.exit(0)
    else:
        logging.error("❌ Slack notification test FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

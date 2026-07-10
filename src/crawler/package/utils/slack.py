# -*- coding: utf-8 -*-
import os
import logging
import aiohttp

logger = logging.getLogger(__name__)

async def send_slack_message(message: str) -> bool:
    """
    非同期でSlackの指定チャンネルにメッセージを投稿します。
    環境変数 SLACK_BOT_TOKEN および SLACK_CHANNEL_ID を使用します。
    """
    token = os.getenv("SLACK_BOT_TOKEN")
    channel = os.getenv("SLACK_CHANNEL_ID")

    if not token or not channel:
        logger.warning("Slack notification skipped: SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not set in environment.")
        return False

    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "channel": channel,
        "text": message
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    logger.error(f"Slack API request failed with status code: {response.status}")
                    return False
                
                resp_json = await response.json()
                if not resp_json.get("ok"):
                    logger.error(f"Slack API returned error: {resp_json.get('error')}")
                    return False
                
                logger.info("Successfully posted property alert message to Slack.")
                return True
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False

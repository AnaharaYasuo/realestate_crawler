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


async def verify_url_active(url: str) -> bool:
    """
    指定されたURLに対して非同期GETリクエストを送信し、接続可能(200 OK)であり、
    かつ物件の公開が終了していない（掲載終了のエラー文言が含まれていない）ことを確認します。
    """
    if not url:
        return False
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        timeout = aiohttp.ClientTimeout(total=5.0)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"URL verification failed (Status: {response.status}): {url}")
                    return False
                
                # HTMLコンテンツを読み込む
                html_content = await response.text(errors='ignore')
                
                # 掲載終了・非公開化を示す具体的なエラーフレーズ群
                inactive_keywords = [
                    "掲載が終了したか、成約済みになった可能性があります",
                    "お探しの物件は、掲載が終了",
                    "掲載を終了いたしました",
                    "掲載終了物件",
                    "ご指定の物件は掲載を終了",
                    "お探しのページは見つかりませんでした",
                    "お探しの物件は見つかりません",
                    "お探しのページは存在しないか、掲載が終了"
                ]
                
                # HTMLのタイトル部分のチェック
                import re
                title_match = re.search(r"<title>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title_text = title_match.group(1).strip()
                    if any(t in title_text for t in ["掲載終了", "エラー", "404", "見つかりません"]):
                        logger.warning(f"URL verification failed (Inactive title '{title_text}' detected): {url}")
                        return False
                
                for kw in inactive_keywords:
                    if kw in html_content:
                        logger.warning(f"URL verification failed (Inactive phrase '{kw}' detected): {url}")
                        return False
                
                logger.info(f"URL verification success (Active & Valid): {url}")
                return True
    except Exception as e:
        logger.warning(f"URL verification failed with exception: {e} for {url}")
        return False

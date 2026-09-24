# -*- coding: utf-8 -*-
import os
import logging
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

# 既知のアラートチャンネルID（小文字で定義して大文字小文字不問で判定）
KNOWN_ALERT_CHANNEL_IDS = {
    "c0bjwuctrnu",  # alerts-mansion
    "c0bhza5asdt",  # alerts-kodate
    "c0bj2jvgcls",  # alerts-tochi
    "c0bj6b4r3e0",  # alerts-invest-apartment
    "c0bj0ksjedc",  # alerts-invest-kodate
}


def is_alert_channel(channel: str | None) -> bool:
    """
    指定されたSlackチャンネル（またはID）がアラート専用チャンネルかどうかを判定します。
    """
    if not channel or not isinstance(channel, str):
        return False

    ch = channel.strip()
    if not ch:
        return False

    ch_lower = ch.lower()

    # 1. チャンネル名パターン (alerts-*, property_alert, または alert を含む名前)
    if ch_lower.startswith("alerts-") or ch_lower == "property_alert" or "alert" in ch_lower:
        return True

    # 2. 既知のアラートチャンネルID
    if ch_lower in KNOWN_ALERT_CHANNEL_IDS:
        return True

    # 3. 環境変数で設定されたアラートチャンネル名・ID
    for env_key, env_val in os.environ.items():
        if env_key.startswith("SLACK_ALERT_") and env_val:
            if ch_lower == env_val.strip().lower():
                return True

    return False


async def send_slack_message(message: str, channel: str | None = None) -> bool:
    """
    非同期でSlackの指定チャンネルにメッセージを投稿します。
    引数 channel が指定されていない場合は、環境変数 SLACK_CHANNEL_ID を使用します。
    アラートチャンネル宛ての場合は、ログ監視（Cloud Logging）のためにログレベル ERROR で出力します。
    """
    token = os.getenv("SLACK_BOT_TOKEN")
    target_channel = channel or os.getenv("SLACK_CHANNEL_ID")

    # アラートチャンネル宛ての通知内容は必ず ERROR レベルログとして出力
    if is_alert_channel(target_channel):
        logger.error(f"[SLACK ALERT -> {target_channel}]:\n{message}")

    if not token or not target_channel:
        logger.warning("Slack notification skipped: SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not set in environment.")
        return False

    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "channel": target_channel,
        "text": message
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    logger.error(f"Slack API request failed with status code: {response.status}")
                    return False
                
                resp_json = await response.json()
                if not resp_json.get("ok"):
                    err_code = resp_json.get("error")
                    logger.error(f"Slack API returned error: {err_code}")
                    fallback_channel = os.getenv("SLACK_CHANNEL_ID")
                    if err_code == "channel_not_found" and fallback_channel and channel != fallback_channel:
                        # フォールバックチャンネルへ警告メッセージを送信して通知不達を自己報告する
                        warning_msg = (
                            f"⚠️ 【システム警告: 通知不達】\n"
                            f"送信先チャンネル 『{channel}』 が見つからないか、Bot（@property）が参加していません。\n"
                            f"Slack上で該当のチャンネルを開き、 `/invite @property` コマンドを実行してBotを招待してください。\n\n"
                            f"**未達メッセージプレビュー**:\n{message[:300]}..."
                        )
                        payload_fallback = {
                            "channel": fallback_channel,
                            "text": warning_msg
                        }
                        await session.post(url, headers=headers, json=payload_fallback)
                    record_failed_message(channel, err_code, message)
                    return False
                
                logger.info("Successfully posted property alert message to Slack.")
                await asyncio.sleep(1.0)
                return True
    except Exception as e:
        logger.exception(f"Failed to send Slack notification: {e}")
        record_failed_message(channel, str(e), message)
        return False


def record_failed_message(channel: str, error: str, message: str):
    import json
    from datetime import datetime
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
    file_path = os.path.join(project_root, "logs", "slack_failed_messages.json")
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        data = []
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
                
        data.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "channel": channel,
            "error": error,
            "message_preview": message[:200]
        })
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        logger.exception(f"Failed to write failed Slack message record: {ex}")


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


async def send_crawling_summary_alert(summary_message: str) -> bool:
    """
    クローリング実行結果のサマリーを property_alert チャンネル（SLACK_ALERT_PROPERTY_ALERT、デフォルトは property_alert）に送信します。
    """
    channel = os.getenv("SLACK_ALERT_PROPERTY_ALERT", "property_alert")
    return await send_slack_message(summary_message, channel)


async def send_dev_report(report_message: str, channel: str | None = None) -> bool:
    """
    開発報告・診断レポート・テスト結果報告を dev-agent チャンネル（SLACK_DEV_CHANNEL、デフォルトは dev-agent）に送信します。
    """
    target_channel = channel or os.getenv("SLACK_DEV_CHANNEL") or "dev-agent"
    return await send_slack_message(report_message, target_channel)



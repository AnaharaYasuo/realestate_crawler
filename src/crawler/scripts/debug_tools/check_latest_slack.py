# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import aiohttp

_current_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.dirname(_current_dir)
_crawler_dir = os.path.dirname(_scripts_dir)
sys.path.insert(0, _crawler_dir)

def _find_channel_id_in_list(channels: list[dict], clean_name: str) -> str | None:
    for ch in channels:
        if ch.get("name", "").lower() == clean_name:
            return ch.get("id")
    return None

async def resolve_channel_id(session: aiohttp.ClientSession, channel: str, token: str) -> str:
    """チャンネル名（例: dev-agent）が指定された場合、Slack APIでConversation IDに解決する。"""
    if not channel or (channel.startswith(("C", "G", "D")) and len(channel) >= 9):
        return channel
    clean_name = channel.lstrip("#").lower()
    url = "https://slack.com/api/conversations.list"
    headers = {"Authorization": f"Bearer {token}"}
    cursor = None
    try:
        while True:
            params = {"types": "public_channel,private_channel", "limit": "200"}
            if cursor:
                params["cursor"] = cursor
            async with session.get(url, headers=headers, params=params) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    break
                found_id = _find_channel_id_in_list(data.get("channels", []), clean_name)
                if found_id:
                    return found_id
                cursor = data.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
    except Exception:
        pass
    return channel

async def verify(target_channel: str | None = None):
    """指定チャンネルの直近のSlackメッセージを取得して表示する。"""
    token = os.getenv("SLACK_BOT_TOKEN")
    channel = target_channel or os.getenv("SLACK_DEV_CHANNEL") or os.getenv("SLACK_CHANNEL_ID") or "dev-agent"
    if not token:
        print("SLACK_BOT_TOKEN not set.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        resolved_channel = await resolve_channel_id(session, channel, token)
        url = f"https://slack.com/api/conversations.history?channel={resolved_channel}&limit=2"
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            print("=== Self-Verification of Latest Slack Message ===")
            if data.get("ok"):
                for m in data.get("messages", []):
                    print(f"TS: {m.get('ts')}")
                    print(f"Text:\n{m.get('text')}\n---")
            else:
                print(f"Error: {data.get('error')}")

if __name__ == "__main__":
    ch_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(verify(ch_arg))

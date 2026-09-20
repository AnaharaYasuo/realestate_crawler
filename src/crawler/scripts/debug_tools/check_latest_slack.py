# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import aiohttp

_current_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.dirname(_current_dir)
_crawler_dir = os.path.dirname(_scripts_dir)
sys.path.insert(0, _crawler_dir)

async def resolve_channel_id(session: aiohttp.ClientSession, channel: str, token: str) -> str:
    """チャンネル名（例: dev-agent）が指定された場合、Slack APIでConversation IDに解決する。"""
    if not channel:
        return channel
    if channel.startswith(("C", "G", "D")) and len(channel) >= 9:
        return channel
    clean_name = channel.lstrip("#").lower()
    url = "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=200"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            if data.get("ok"):
                for ch in data.get("channels", []):
                    if ch.get("name", "").lower() == clean_name:
                        return ch.get("id")
    except Exception:
        pass
    return channel

async def verify(target_channel: str | None = None):
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

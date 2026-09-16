# -*- coding: utf-8 -*-
import os
import sys
import asyncio

_current_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.dirname(_current_dir)
_crawler_dir = os.path.dirname(_scripts_dir)
sys.path.insert(0, _crawler_dir)

import aiohttp

async def verify():
    token = os.getenv("SLACK_BOT_TOKEN")
    channel = os.getenv("SLACK_CHANNEL_ID")
    url = f"https://slack.com/api/conversations.history?channel={channel}&limit=2"
    headers = {"Authorization": f"Bearer {token}"}
    
    async with aiohttp.ClientSession() as session:
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
    asyncio.run(verify())

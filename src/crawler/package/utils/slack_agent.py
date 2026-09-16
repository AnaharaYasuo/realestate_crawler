# -*- coding: utf-8 -*-
import os
import shutil
import logging
import asyncio
from typing import List, Optional

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))

class SlackAgent:
    """
    Slack Socket Mode 経由で開発指示を受信し、
    Antigravity CLI (agy) を直接起動してエージェントに開発タスクを行わせ、
    途中経過および最終結果を Slack スレッドにリアルタイム返信する開発支援エージェント。
    """
    def __init__(self, allowed_users: Optional[List[str]] = None, conversation_id: Optional[str] = None):
        self.bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.app_token = os.getenv("SLACK_APP_TOKEN")
        self.conversation_id = conversation_id or os.getenv("ANTIGRAVITY_CONVERSATION_ID")
        
        env_allowed = os.getenv("SLACK_ALLOWED_USERS", "")
        if allowed_users:
            self.allowed_users = set(allowed_users)
        elif env_allowed:
            self.allowed_users = set(u.strip() for u in env_allowed.split(",") if u.strip())
        else:
            self.allowed_users = set()

    def is_user_allowed(self, user_id: str) -> bool:
        """指定されたユーザーが実行許可リストに含まれているか検証"""
        if not self.allowed_users:
            logger.warning("SLACK_ALLOWED_USERS is not set. Allowing all requests.")
            return True
        return user_id in self.allowed_users

    def start_bot(self):
        """Slack Socket Mode Bot の起動関数"""
        if not self.bot_token or not self.app_token:
            raise ValueError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in environment variables.")

        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler

        app = App(token=self.bot_token)

        def handle_event_internal(event, say, client):
            user_id = event.get("user")
            if not user_id or event.get("bot_id"):
                return

            text = event.get("text", "")
            if not text:
                return

            thread_ts = event.get("thread_ts") or event.get("ts")
            
            # 初期レスポンス投稿
            resp = say(
                text="🚀 **Antigravity Agent 本体を起動中...**\n\n```\n[タスク準備中...]\n```",
                thread_ts=thread_ts
            )

            channel_id = resp["channel"]
            message_ts = resp["ts"]

            # 非同期で agy をストリーミング実行してチャットを自動更新
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.run_streaming_agent(client, channel_id, message_ts, text))
            loop.close()

        @app.event("app_mention")
        def handle_app_mentions(body, say, client):
            handle_event_internal(body.get("event", {}), say, client)

        @app.event("message")
        def handle_message_events(body, say, client):
            event = body.get("event", {})
            if not event.get("subtype"):
                handle_event_internal(event, say, client)

        logger.info("Starting Antigravity Realtime Streaming Slack Agent...")
        handler = SocketModeHandler(app, self.app_token)
        handler.start()

    async def run_streaming_agent(self, client, channel_id: str, message_ts: str, instruction: str):
        """
        agy CLI を非同期プロセスとして起動し、標準出力をキャプチャして 3秒おきに chat.update で更新
        """
        agy_bin = (
            shutil.which("agy") or 
            shutil.which("agy.exe") or 
            (r"C:\Users\weare\AppData\Local\agy\bin\agy.exe" if os.path.exists(r"C:\Users\weare\AppData\Local\agy\bin\agy.exe") else "agy")
        )

        cmd = [agy_bin, "--dangerously-skip-permissions"]
        if self.conversation_id:
            cmd.extend(["--conversation", self.conversation_id])
        else:
            cmd.append("--continue")

        cmd.extend(["-p", instruction])

        env = os.environ.copy()
        env["PAGER"] = "cat"

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=PROJECT_ROOT,
                env=env
            )

            output_chunks = []

            async def update_slack_periodically():
                while process.returncode is None:
                    await asyncio.sleep(3)
                    curr_text = "".join(output_chunks).strip()
                    if curr_text:
                        if len(curr_text) > 3500:
                            curr_text = "... [前部省略] ...\n" + curr_text[-3400:]
                        try:
                            client.chat_update(
                                channel=channel_id,
                                ts=message_ts,
                                text=f"⏳ **Antigravity Agent 実行中 (リアルタイム進捗)...**\n\n```\n{curr_text}\n```"
                            )
                        except Exception as ex:
                            logger.error(f"Failed chat.update: {ex}")

            update_task = asyncio.create_task(update_slack_periodically())

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                output_chunks.append(line.decode("utf-8", errors="ignore"))

            await process.wait()
            update_task.cancel()

            final_text = "".join(output_chunks).strip()
            status_emoji = "✅" if process.returncode == 0 else "⚠️"

            if not final_text:
                final_text = "(Antigravity Agent からの出力はありませんでした。)"

            if len(final_text) > 3500:
                final_text = "... [前部省略] ...\n" + final_text[-3400:]

            client.chat_update(
                channel=channel_id,
                message_ts=message_ts,
                text=f"{status_emoji} **Antigravity Agent タスク完了**\n\n```\n{final_text}\n```"
            )
        except Exception as e:
            logger.error(f"Error during streaming agy execution: {e}")
            try:
                client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    text=f"❌ **Antigravity Agent 実行エラー**: `{e}`"
                )
            except Exception:
                pass

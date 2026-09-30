import asyncio
import logging
import os
import shutil

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))


def _find_agy_bin() -> str:
    win_path = r"C:\Users\weare\AppData\Local\agy\bin\agy.exe"
    return (
        shutil.which("agy")
        or shutil.which("agy.exe")
        or (win_path if os.path.exists(win_path) else "agy")
    )


def _build_agy_cmd(conversation_id: str | None, instruction: str) -> list[str]:
    cmd = [_find_agy_bin(), "--dangerously-skip-permissions"]
    if conversation_id:
        cmd.extend(["--conversation", conversation_id])
    else:
        cmd.append("--continue")
    cmd.extend(["-p", instruction])
    return cmd


def _truncate_text(text: str, max_len: int = 3500) -> str:
    if len(text) > max_len:
        return "... [前部省略] ...\n" + text[-3400:]
    return text


AUTO_HEAL_TAG = "[AUTO_HEAL_REQ]"
SELF_AGENT_MARKERS = (
    "Antigravity Agent 本体を起動中",
    "Antigravity Agent 実行完了",
    "Antigravity Agent タスク完了",
    "Antigravity Agent 実行中",
)


def is_self_agent_message(text: str) -> bool:
    """メッセージが Antigravity エージェント自身の自動応答・進捗表示かどうかを判定"""
    return any(marker in text for marker in SELF_AGENT_MARKERS)


def _validate_auto_heal_sender(
    bot_id: str | None,
    user_id: str | None,
    allowed_users: set[str],
    allowed_bots: set[str] | None,
) -> tuple[bool, str, str]:
    if bot_id:
        if not allowed_bots or bot_id not in allowed_bots:
            return False, "", "unauthorized_bot"
        return True, "/auto-heal", "auto_heal_authorized"
    if user_id:
        if not allowed_users or user_id not in allowed_users:
            return False, "", "unauthorized_user"
        return True, "/auto-heal", "auto_heal_authorized"
    return False, "", "unauthorized_sender"


def should_process_slack_event(
    event: dict,
    allowed_users: set[str],
    allowed_bots: set[str] | None = None,
) -> tuple[bool, str, str]:
    """
    イベントを処理すべきか検証し、(is_valid, extracted_instruction, reason) を返却する。
    """
    text = (event.get("text") or "").strip()
    if not text:
        return False, "", "empty_text"

    if is_self_agent_message(text):
        return False, "", "self_agent"

    bot_id = event.get("bot_id")
    user_id = event.get("user")

    if AUTO_HEAL_TAG in text:
        return _validate_auto_heal_sender(
            bot_id, user_id, allowed_users, allowed_bots
        )

    if bot_id:
        return False, "", "bot_rejected"

    if not user_id or not allowed_users or user_id not in allowed_users:
        return False, "", "unauthorized_user"

    return True, text, "user_authorized"


class SlackAgent:
    """
    Slack Socket Mode 経由で開発指示を受信し、
    Antigravity CLI (agy) を直接起動してエージェントに開発タスクを行わせ、
    途中経過および最終結果を Slack スレッドにリアルタイム返信する開発支援エージェント。
    """

    def __init__(
        self,
        allowed_users: list[str] | None = None,
        allowed_bots: list[str] | None = None,
        conversation_id: str | None = None,
    ):
        self.bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.app_token = os.getenv("SLACK_APP_TOKEN")
        self.conversation_id = conversation_id or os.getenv(
            "ANTIGRAVITY_CONVERSATION_ID"
        )

        env_allowed_users = os.getenv("SLACK_ALLOWED_USERS", "")
        if allowed_users:
            self.allowed_users = set(allowed_users)
        elif env_allowed_users:
            self.allowed_users = {
                u.strip() for u in env_allowed_users.split(",") if u.strip()
            }
        else:
            self.allowed_users = set()

        env_allowed_bots = os.getenv("SLACK_ALLOWED_BOT_IDS", "")
        if allowed_bots:
            self.allowed_bots = set(allowed_bots)
        elif env_allowed_bots:
            self.allowed_bots = {
                b.strip() for b in env_allowed_bots.split(",") if b.strip()
            }
        else:
            self.allowed_bots = set()

    def is_user_allowed(self, user_id: str) -> bool:
        """指定されたユーザーが実行許可リストに含まれているか検証（未設定時は安全のため全員拒否）"""
        if not self.allowed_users:
            logger.error(
                "SLACK_ALLOWED_USERS is not configured. Rejecting request by default for security."
            )
            return False
        return user_id in self.allowed_users

    def start_bot(self):
        """Slack Socket Mode Bot の起動関数"""
        if not self.bot_token or not self.app_token:
            raise ValueError(
                "SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in environment variables."
            )

        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler

        app = App(token=self.bot_token)

        def handle_event_internal(event, say, client):
            allowed, instruction, reason = should_process_slack_event(
                event, self.allowed_users, self.allowed_bots
            )
            if not allowed:
                if reason == "unauthorized_user":
                    user_id = event.get("user")
                    thread_ts = event.get("thread_ts") or event.get("ts")
                    logger.warning(
                        f"Unauthorized access attempt blocked from Slack user: {user_id}"
                    )
                    say(
                        text=f"⛔ **アクセス拒否**: ユーザー `{user_id}` にはエージェントの実行権限がありません。\n実行を許可するには環境変数 `SLACK_ALLOWED_USERS` にユーザーIDを追加してください。",
                        thread_ts=thread_ts,
                    )
                return

            thread_ts = event.get("thread_ts") or event.get("ts")

            # 初期レスポンス投稿
            resp = say(
                text="🚀 **Antigravity Agent 本体を起動中...**\n\n```\n[タスク準備中...]\n```",
                thread_ts=thread_ts,
            )

            channel_id = resp["channel"]
            message_ts = resp["ts"]

            # 非同期で agy をストリーミング実行してチャットを自動更新
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.run_streaming_agent(client, channel_id, message_ts, instruction)
            )
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

    async def _capture_and_stream(
        self, process, client, channel_id: str, message_ts: str
    ) -> tuple[list[str], int]:
        output_chunks = []
        stop_event = asyncio.Event()

        async def update_slack_periodically():
            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=3)
                    break
                except TimeoutError:
                    pass
                curr_text = _truncate_text("".join(output_chunks).strip())
                if curr_text:
                    try:
                        client.chat_update(
                            channel=channel_id,
                            ts=message_ts,
                            text=f"⏳ **Antigravity Agent 実行中 (リアルタイム進捗)...**\n\n```\n{curr_text}\n```",
                        )
                    except Exception:
                        logger.exception("Failed chat.update")

        update_task = asyncio.create_task(update_slack_periodically())
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            output_chunks.append(line.decode("utf-8", errors="ignore"))

        await process.wait()
        stop_event.set()
        update_task.cancel()
        return output_chunks, process.returncode

    async def run_streaming_agent(
        self, client, channel_id: str, message_ts: str, instruction: str
    ):
        """
        agy CLI を非同期プロセスとして起動し、標準出力をキャプチャして 3秒おきに chat.update で更新
        """
        cmd = _build_agy_cmd(self.conversation_id, instruction)
        env = os.environ.copy()
        env["PAGER"] = "cat"

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=PROJECT_ROOT,
                env=env,
            )
            output_chunks, returncode = await self._capture_and_stream(
                process, client, channel_id, message_ts
            )
            final_text = _truncate_text(
                "".join(output_chunks).strip()
                or "(Antigravity Agent からの出力はありませんでした。)"
            )
            status_emoji = "✅" if returncode == 0 else "⚠️"

            client.chat_update(
                channel=channel_id,
                message_ts=message_ts,
                text=f"{status_emoji} **Antigravity Agent タスク完了**\n\n```\n{final_text}\n```",
            )
        except Exception as e:
            logger.exception("Error during streaming agy execution")
            try:
                client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    text=f"❌ **Antigravity Agent 実行エラー**: `{e}`",
                )
            except Exception as update_err:  # noqa: BLE001
                logger.debug("Failed sending error status chat.update: %s", update_err)

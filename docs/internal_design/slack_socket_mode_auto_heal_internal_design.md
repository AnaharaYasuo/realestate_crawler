# Slack Socket Mode 中継による Antigravity 自律修復トリガー機構 内部設計書

## 1. モジュールおよびクラス設計

### 1.1 `package.utils.slack_agent.py`
関数の追加および `handle_event_internal` のリファクタリングを行う。

```python
AUTO_HEAL_TAG = "[AUTO_HEAL_REQ]"
SELF_AGENT_MARKERS = [
    "Antigravity Agent 本体を起動中",
    "Antigravity Agent 実行完了",
    "Antigravity Agent タスク完了",
    "Antigravity Agent 実行中",
]

def is_self_agent_message(text: str) -> bool:
    """メッセージが Antigravity エージェント自身の自動応答・進捗表示かどうかを判定"""
    return any(marker in text for marker in SELF_AGENT_MARKERS)

def should_process_slack_event(event: dict, allowed_users: set[str]) -> tuple[bool, str]:
    """
    イベントを処理すべきか検証し、(is_valid, extracted_instruction) を返却する。
    
    1. text が空の場合は (False, "")
    2. is_self_agent_message(text) が真の場合は (False, "")  # 自己ループ防止
    3. AUTO_HEAL_TAG in text の場合:
       - Bot発信であっても自動修復トリガーとして受諾 -> (True, "/auto-heal")
    4. event.get("bot_id") が存在する場合:
       - タグなしBotメッセージは破棄 -> (False, "")
    5. 人間ユーザーの場合:
       - user_id in allowed_users の場合のみ -> (True, text)
       - それ以外は認可エラー通知 -> (False, "")
    """
```

### 1.2 `src/crawler/scripts/node/slack_agent_host.js`
Node.js 側も同様の判定関数を実装：

```javascript
const AUTO_HEAL_TAG = '[AUTO_HEAL_REQ]';
const SELF_AGENT_MARKERS = [
  'Antigravity Agent 本体を起動中',
  'Antigravity Agent 実行完了',
  'Antigravity Agent タスク完了',
  'Antigravity Agent 実行中'
];

function isSelfAgentMessage(text) {
  return SELF_AGENT_MARKERS.some(marker => text.includes(marker));
}

function shouldProcessEvent(event, allowedUsers) {
  const text = (event.text || '').trim();
  if (!text) return { valid: false, instruction: '' };
  if (isSelfAgentMessage(text)) return { valid: false, instruction: '' };

  if (text.includes(AUTO_HEAL_TAG)) {
    return { valid: true, instruction: '/auto-heal', isAutoHeal: true };
  }

  if (event.bot_id) {
    return { valid: false, instruction: '' };
  }

  const userId = event.user;
  if (!userId || (allowedUsers.size > 0 && !allowedUsers.has(userId))) {
    return { valid: false, instruction: '', unauthorized: true };
  }

  return { valid: true, instruction: text, isAutoHeal: false };
}
```

### 1.3 `src/crawler/scripts/debug_tools/auto_heal_parsers.py`
`scan_anomalies_and_generate_instructions()` において、検知したエラーをグループ化・発生回数で集計し、Top-50 を優先抽出するロジックを実装：

```python
def aggregate_and_sort_targets(raw_targets: list[dict], max_targets: int = 50) -> list[dict]:
    """
    検知された異常物件リストを (company, property_type, reason_prefix) 単位で集計し、
    発生件数（頻度）が多い順にソートして上位最大 max_targets 件（デフォルト50件）を返却する。
    """
    ...
```

`notify_auto_heal_request()` も Top-50 に基づくサマリーを発報：

```python
def notify_auto_heal_request(heal_targets: list[dict]):
    """異常物件検知時に Slack dev チャンネルへ [AUTO_HEAL_REQ] メッセージを送信"""
    if not heal_targets:
        return
        
    from package.utils.slack import send_dev_report
    import asyncio
    
    target_summary = "\n".join([
        f"- {t['company']} ({t['property_type']}) [{t.get('frequency', 1)}件]: {t['reason']} (URL: {t['url']})"
        for t in heal_targets[:5]
    ])
    if len(heal_targets) > 5:
        target_summary += f"\n... 他 {len(heal_targets) - 5} 件 (最大10件を優先修復対象に選定)"
        
    msg = (
        f"🚨 **[AUTO_HEAL_REQ] クローラー自己修復リクエスト**\n"
        f"クローリング・データ検証においてパース異常・データ不整合が検知されました。\n\n"
        f"**検知件数**: {len(heal_targets)} 件 (頻度順 Top 10)\n"
        f"**対象概要**:\n{target_summary}\n\n"
        f"/auto-heal"
    )
    try:
        asyncio.run(send_dev_report(msg))
        logging.info("Successfully sent [AUTO_HEAL_REQ] to Slack dev channel.")
    except Exception as e:
        logging.warning(f"Failed to send auto-heal Slack notification: {e}")
```

## 2. 単体テスト設計 (`test_slack_agent.py`)

以下のテストケースを追加：
1. `test_should_process_slack_event_auto_heal_tag_from_bot`:
   - `bot_id="B123"`, `text="🚨 [AUTO_HEAL_REQ] ... /auto-heal"` ➔ `(True, "/auto-heal")` を検証。
2. `test_should_process_slack_event_normal_bot_rejected`:
   - `bot_id="B123"`, `text="一般的なBot発言"` ➔ `(False, "")` を検証。
3. `test_should_process_slack_event_self_agent_markers_rejected`:
   - `bot_id="B123"`, `text="[AUTO_HEAL_REQ] Antigravity Agent 本体を起動中..."` ➔ `(False, "")` を検証。
4. `test_should_process_slack_event_allowed_user`:
   - `user="U12345"`, `text="修正して"` ➔ `(True, "修正して")` を検証。
5. `test_should_process_slack_event_unauthorized_user`:
   - `user="UNAUTHORIZED"`, `text="修正して"` ➔ `(False, "")` を検証。

# Slack Socket Mode 中継による Antigravity 自律修復トリガー機構 基本設計書

## 1. システム概要・アーキテクチャ

本機構は、クラウドまたはバッチ環境で実行されるクローラーの異常検知を契機として、Slack Socket Mode をメッセージブローカーとして中継し、ローカル環境上の常駐デーモンを介して Antigravity CLI (`agy.exe`) を自律起動する仕組みを提供する。

```
+-------------------------------------------------------------+
| クラウド / バッチ環境 (GCP / Docker / CLI)                   |
|  - run_pipeline.py / auto_heal_parsers.py                   |
|  - パース異常・データ不整合の検知                             |
|  - Temp/auto_heal_instruction.json 生成                      |
|  - send_dev_report() による Slack 発報                       |
+-------------------------------------------------------------+
                               |
                               | HTTPS (chat.postMessage)
                               v
+-------------------------------------------------------------+
| Slack クラウド基盤 (メッセージブローカー)                     |
|  - #dev-agent チャンネル                                    |
|  - メッセージ: "🚨 [AUTO_HEAL_REQ] クローラー自己修復..."      |
+-------------------------------------------------------------+
                               |
                               | WebSocket (Socket Mode / WSS)
                               | ※ポート開放・固定IP不要
                               v
+-------------------------------------------------------------+
| ローカル開発機 (Windows OS)                                  |
|                                                             |
|  [常駐デーモン: slack_agent_host.js / slack_agent.py]        |
|   1. Socket Mode でイベント受信                              |
|   2. should_process_event / shouldProcessEvent で検証       |
|      - [AUTO_HEAL_REQ] タグ検知 ➔ Bot発信でも許可             |
|      - 自己返信・通常Bot発言 ➔ 無限ループ防止で破棄           |
|      - 一般ユーザー発言 ➔ SLACK_ALLOWED_USERS 認可           |
|                                                             |
|   3. Antigravity CLI (agy.exe) ヘッドレス起動                |
|      agy --dangerously-skip-permissions -p "/auto-heal"     |
|                                                             |
|   4. 自律修復の実行                                          |
|      - auto-healing スキルに従いテスト・修正・/regression-test|
|      - 結果・差分・PRリンクを Slack スレッドに自動返信        |
+-------------------------------------------------------------+
```

## 2. コンポーネント設計

### 2.1 発信側: `auto_heal_parsers.py`
- `scan_anomalies_and_generate_instructions()` の末尾において、修復対象（`heal_targets`）が存在する場合に `notify_auto_heal_request()` を呼び出す。
- 送信先: `SLACK_DEV_CHANNEL`（デフォルト: `dev-agent`）。
- メッセージ構成:
  - プレフィックス: `🚨 **[AUTO_HEAL_REQ] クローラー自己修復リクエスト**`
  - 検知件数および対象サマリー
  - コマンド指示: `/auto-heal`

### 2.2 受信側: `slack_agent_host.js` (Node.js) & `slack_agent.py` (Python)
- **イベント選別ロジック (`should_process_event` / `shouldProcessEvent`)**:
  1. テキストが空、またはイベントにテキストがない場合は無視。
  2. 自己生成メッセージ（「Antigravity Agent 本体を起動中」「Antigravity Agent 実行完了」「Antigravity Agent タスク完了」等）を含む場合は、自己ループ防止として破棄。
  3. `[AUTO_HEAL_REQ]` を含む場合:
     - クローラー等のシステムBotからの発信であっても、正規の自律修復トリガーとして受諾（`allowed = True`）。
     - コマンド本文（`/auto-heal`）を抽出し、Antigravity CLI に渡す。
  4. 通常の `event.bot_id` が存在する場合:
     - `[AUTO_HEAL_REQ]` が含まれていなければ従来通り破棄。
  5. 人間ユーザー (`event.user`) の場合:
     - 許可リスト `SLACK_ALLOWED_USERS` に基づいて認可判定。

### 2.3 実行側: Antigravity CLI (`agy.exe`)
- 起動構文:
  `agy.exe --dangerously-skip-permissions --conversation <conversation_id> -p "<escaped_instruction>"`
- 自律型スキル `/auto-healing` をトリガーし、ワークスペース内で修復タスクを実行。

## 3. セキュリティおよび信頼性設計
- **無限ループ・連鎖起動の完全防止**:
  - エージェントが実行完了時に Slack スレッドへポストする投稿には `[AUTO_HEAL_REQ]` を絶対に含めない。
  - 受信側で自己発言キーワード（`Antigravity Agent` 等）をブラックリスト判定し、自作自演の再トリガーを遮断。
- **認可制御の維持**:
  - 人間からの指示に関しては `SLACK_ALLOWED_USERS` のホワイトリスト制を維持し、部外者による不正指示を防止。

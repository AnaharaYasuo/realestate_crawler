# 🔧 Slack 開発 Agent ボット運用・設定ガイド

出先（スマホやタブレット等の Slack）からコンテナ内の AI Agent に対して開発・テスト指示を行い、レスポンスを受け取るための設定手順ガイドです。

---

## 1. アーキテクチャの概要

* **Socket Mode (WebSocket)** を使用するため、グローバルなパブリック IP や Webhook URL (ngrok 等) の公開は不要です。
* **専用チャンネル**: 開発指示・応答専用チャンネル **`#dev-agent`** を作成済みです。本チャンネルでメッセージをやり取りします。
* 許可された Slack ユーザー ID のみ指示を実行可能に制限できます。


### 処理フロー図 (Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    actor User as 出先ユーザー<br/>(スマホ/PC Slack)
    participant SlackAPI as Slack クラウド API
    participant Bot as Slack Agent<br/>(Socket Mode Listener)
    participant AgCLI as Antigravity CLI<br/>(agy --continue -p)
    participant Agent as Antigravity Agent 本体<br/>(コード解析・編集・pytest実行)

    User->>SlackAPI: ① メンション/DM送信<br/>「@DevAgent パーサー修正して」
    SlackAPI-->>Bot: ② WebSocket (Socket Mode) で転送<br/>(パブリックIP不要・安全)
    
    rect rgb(240, 240, 240)
        note over Bot,Agent: セキュリティチェック & Antigravity 起動
        Bot->>Bot: ③ 送信者の User ID 検証<br/>(SLACK_ALLOWED_USERS チェック)
        Bot->>SlackAPI: ④ 即時レスポンス<br/>「🚀 Antigravity Agent 本体を起動中...」
        SlackAPI-->>User: (スレッドに通知)
        
        Bot->>AgCLI: ⑤ agy --continue --dangerously-skip-permissions -p "指示" 起動
        AgCLI->>Agent: ⑥ 会話コンテキストを継続し、指示を実行
        Agent->>Agent: ⑦ ファイル検索・コード編集・pytest 自律実行
        Agent-->>AgCLI: ⑧ 実行結果・変更ログ・解答テキスト
        AgCLI-->>Bot: ⑨ stdout / stderr のキャプチャ
    end

    Bot->>SlackAPI: ⑩ Antigravity Agent の成果・ログを返信
    SlackAPI-->>User: ⑪ Slack スレッドで結果確認
```

### 主要機能とセキュリティのポイント

1. **Antigravity Agent 本体直結 (`agy` CLI)**
   * 単なる簡易 API 呼び出しではなく、Antigravity の高度なツール・スキル・開発コンテキストをそのまま利用。
2. **継続セッション (`--continue`)**
   * 直前の会話履歴やコンテキストを継続して非対話実行 (`-p`)。
3. **暗号化 WebSocket 接続 (Socket Mode)**
   * 外部インバウンドポートの開口不要。
4. **実行権限フィルタリング**
   * `.env` の `SLACK_ALLOWED_USERS` に登録された ID 以外のアクセスを遮断。



---

## 2. Slack App の作成手順

### Step 1: Slack App の新規作成
1. [Slack API Apps ページ](https://api.slack.com/apps) にアクセスし、**「Create New App」** をクリック。
2. **「From an app manifest」** を選択し、対象のワークスペースを選択。
3. 以下の Manifest (JSON) を貼り付けて作成します:

```json
{
  "display_information": {
    "name": "DevAgent",
    "description": "DevContainer Development Agent Bot"
  },
  "features": {
    "bot_user": {
      "display_name": "DevAgent",
      "always_online": true
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "chat:write",
        "im:history",
        "im:read",
        "im:write"
      ]
    }
  },
  "settings": {
    "socket_mode_enabled": true,
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.im"
      ]
    }
  }
}
```

### Step 2: トークンの取得
1. **App Token (`xapp-...`) の取得**:
   - 左メニューの **「Basic Information」** > **「App-Level Tokens」** に移動。
   - **「Generate Token and Scopes」** をクリック。
   - Token Name を入力し、`connections:write` スコープを追加して生成。生成されたトークン (`xapp-...`) をコピー。
2. **Bot Token (`xoxb-...`) の取得**:
   - 左メニューの **「Install App」** を開き、**「Install to Workspace」** をクリックして承認。
   - 表示された **Bot User OAuth Token (`xoxb-...`)** をコピー。

---

## 3. 環境変数 (`.env`) の設定

プロジェクトルートの `.env` ファイルに以下を追加します:

```env
# Slack Agent 設定
SLACK_BOT_TOKEN=xoxb-YOUR-BOT-TOKEN
SLACK_APP_TOKEN=xapp-YOUR-APP-TOKEN
SLACK_ALLOWED_USERS=U12345678  # 指示を許可するSlack User ID (カンマ区切り)

# AI Engine キー
GEMINI_API_KEY=AIzaSy...
```

> 💡 **Slack User ID の確認方法**: Slack で自身のプロフィールを開き、「... (その他)」 > 「メンバーIDをコピー」 をクリック。

---

## 4. コンテナの起動

`docker-compose` で `slack-agent` サービスをバックグラウンド起動します:

```bash
docker-compose up -d --build slack-agent
```

### ログ確認・動作検証
```bash
docker-compose logs -f slack-agent
```
「`Starting Slack Agent Socket Mode Handler...`」が表示されていれば準備完了です。

---

## 5. 出先からの使い方

Slack 上で `@DevAgent` にメンションするか、ダイレクトメッセージ (DM) で指示を送信します。

* **テスト実行**:
  `@DevAgent test` または `@DevAgent テスト実行して`
* **コード開発・修正指示**:
  `@DevAgent パーサーの例外処理を修正して`

Agent がコンテナ内で作業を行い、実行結果やテスト合否を Slack スレッドに返信します。

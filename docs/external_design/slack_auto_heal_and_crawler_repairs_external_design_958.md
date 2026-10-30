# 外部設計書: Slackエラー読取・低件数検知のオートヒール統合およびathome/homesクローラー修復

## 1. 全体アーキテクチャ
```
[Slack Channels (#alerts-*, #dev-agent, #property_alert)]
                  │ (conversations.history API)
                  ▼
       [fetch_slack_anomalies()] ──┐
                                   ▼
 [DB PropertyEvaluation] ──> [aggregate_and_sort_targets()] ──> [Temp/auto_heal_instruction.json]
                                                                        │
                                                                        ▼
                                                         [Auto-Heal / Developer Execution]
                                                                        │
                                                         ┌──────────────┴──────────────┐
                                                         ▼                             ▼
                                                   [athome parser]               [homes parser]
```

## 2. 外部インターフェース
### 2.1 Slack API 連携
- 利用エンドポイント: `conversations.list`, `conversations.history`
- 認証: `SLACK_BOT_TOKEN`（保持スコープ: `channels:history`, `groups:history` 等）
- 対象チャンネル:
  - 既知のアラートチャンネル（`#alerts-mansion`, `#alerts-kodate`, `#alerts-tochi`, `#alerts-invest-*`, `#alerts-crawling`）
  - 開発報告チャンネル（`#dev-agent`, `#property_alert`）

### 2.2 自己修復指示書 (`Temp/auto_heal_instruction.json`)
- Slackから抽出された「0件警告」「パース例外」「低件数異常」のレコードを `source: "slack"` として識別し、DB不整合レコード（`source: "db"`）と一元集計して Top-50 の優先順位で格納する。

### 2.3 クローラー・パーサー外部仕様
- **athome**: 一覧ページ（HTML / JSON API）の最新構造に対応し、物件URL一覧の抽出を担保。
- **homes**: 一覧カード内の価格文字列パターンに対応し、正規表現パース時の NoneType ガードおよび安全な抽出を実装。

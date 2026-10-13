# 外部設計書: ProxySQL中断判定におけるトラフィック閾値チェック機能 (#901)

## 1. システム構成とインターフェース
- **コンポーネント**: `src/crawler/scripts/ensure_resources_stopped.py`
- **外部サービス**: Google Cloud Monitoring API (`monitoring_v3` / REST API `monitoring.googleapis.com`)
  - メトリクス: `compute.googleapis.com/instance/network/received_bytes_count`
  - 集計期間: 過去 10 分間（`window_sec = 600`）
  - アライメント: `ALIGN_SUM`
  - 判定閾値: 1 MB (`1_048_576` バイト)

## 2. 判定フロー
```
[ProxySQL インスタンスが RUNNING]
       │
       ▼
[起動猶予期間 (grace_period) 内？] ──(YES)──> 停止スキップ (grace_period)
       │ (NO)
       ▼
[最大連続稼働時間 (max_uptime: 8h) 超過？] ──(YES)──> 【強制停止】(max_uptime_exceeded)
       │ (NO)
       ▼
[Cloud Run Job が実行中？] ──(YES)──> 正常実行中として停止スキップ
       │ (NO: 0件)
       ▼
[直近10分間のネットワーク受信量 >= 1MB？]
       ├── (YES: アクティブトラフィックあり) ──> 停止スキップ (active_traffic)
       └── (NO: アイドル/ヘルスチェックのみ) ──> 【通常停止】(orphaned_instance)
```

## 3. Slack アラート仕様
- アクティブトラフィック検知時:
  - メッセージ: `:information_source: *【Safety-Net】アクティブな外部接続・トラフィックを検知したためProxySQLの起動を継続しました* (受信量: X.XX MB)`
- 最大稼働時間超過時:
  - メッセージ: `:warning: *【ゾンビ課金アラート】ProxySQL連続稼働時間上限超過検知*: 8時間を超過したため強制停止しました`

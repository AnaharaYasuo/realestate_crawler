# Auto-Heal Slack Telemetry Ingestion and Delisted/Anomaly Handling Requirements

## 1. 概要 (Overview)
`/auto-heal` および Slack アラート連携において、データ監視アラート（`alerts-mansion`, `alerts-kodate`, `alerts-tochi`, `alerts-investment-apartment`, `alerts-investment-kodate` 等）で通知された物件エラーおよび掲載終了（delisted）物件が適切に修復・処理されるようにする。

## 2. 機能要件 (Functional Requirements)
- **FR-001: Slackデータ監視アラート行の自動抽出**
  - `parse_slack_message_to_targets()` で `- :x: [Critical] [company/property_type] reason | name | URL: <url>` および `- :bulb: [Warning]` パターンを正規表現で抽出し、自己修復ターゲットとしてリスト化する。
- **FR-002: 掲載終了（404/not-found/募集終了）物件の安全な非公開化と例外処理**
  - 三井 (`rehouse.co.jp`) 等で掲載終了（`property-detail-not-found-template` や「掲載が終了したか、成約済みになった可能性」）となったページは `ListingEndedException` を送出する。
  - `validate_data.py` や `auto_heal_parsers.py` において、掲載終了物件は `PropertyEvaluation` または物件自体の `is_published=False` / `delisted` としてマークし、不要な未抽出エラー（交通未抽出等）として誤検知・蓄積させない。
- **FR-003: 交通フィールドの整合性向上**
  - 三井等のパーサーで、抽出された交通情報 (`traffic_lines`) が `traffic` および `station1` に確実に反映されるようにする。

# GCP コスト最適化・オンデマンドライフサイクル制御 内部設計書 (GCP Cost Optimization Internal Design)

## 1. 目的・背景
本設計書は、Google Cloud Platform 上で稼働する不動産クローラーシステムの運用固定費を最小化（月額1万円以内）し、夜間バッチ実行時のみリソースを安全にオンデマンド稼働させ、かつゾンビ課金を物理的に防ぐセーフティネットの内部構造を定義する。

---

## 2. オンデマンド起動・安全停止ライフサイクル

### 2.1 E2E シーケンス
```mermaid
sequenceDiagram
    autonumber
    actor Cron1 as Cloud Scheduler (00:55 JST)
    actor Cron2 as Cloud Scheduler (05:00 JST / Safety Net)
    participant Coord as Cloud Run Crawler Pipeline
    participant Proxy as ProxySQL MIG (e2-micro)
    participant NAT as Cloud NAT
    participant Slack as Slack Alert (#property_alert)

    Note over Cron1,Coord: [夜間バッチ実行フェーズ]
    Cron1->>Coord: 日次バッチ実行トリガー
    Coord->>Proxy: MIG スケールアウト (size: 0 -> 1)
    Coord->>NAT: NAT 有効化
    Coord->>Coord: クローリング & ML推論実行
    Coord->>Proxy: 完了後 MIG スケールイン (size: 1 -> 0)
    Coord->>NAT: 完了後 NAT 無効化

    Note over Cron2,Slack: [朝05:00 セーフティネット検査フェーズ]
    Cron2->>Coord: ensure_resources_stopped 実行
    alt リソースが size > 0 または NAT有効のまま放置
        Coord->>Proxy: 強制停止 (size -> 0)
        Coord->>NAT: 強制無効化
        Coord->>Slack: ⚠️ 停止漏れ検知 & 強制停止アラート送信
    else 正常に停止済み (size == 0)
        Coord->>Coord: 正常終了 (通知なし/監査ログのみ)
    end
```

---

## 3. ゾンビ課金防止スクリプト (`ensure_resources_stopped.py`)

### 3.1 役割と責務
- 毎朝 05:00 JST (20:00 UTC) に Cloud Scheduler 経由でキックされる（パイプライン異常終了時のセーフティネット）。
- Compute Engine API / REST API (`instanceGroupManagers`) を介して `proxysql-mig` の `target_size` および稼働インスタンス数を取得。
- `target_size > 0` または稼働インスタンスが存在する場合：
  1. Autoscaler 管理下 MIG の GCP API 制約（直接 `resize` 禁止）に適合させるため、Autoscaler の `min_num_replicas = 0` かつ `max_num_replicas = 0` へ更新（または Autoscaler 一時停止）し、インスタンスを 0 台へ完全削除・縮小。
  2. Slack チャンネル（`#property_alert`）に警告メッセージを発報。
  3. 戻り値としてステータスを返し、監査ログへ記録。
- **安全側に倒すエラーハンドリング (Fail-Safe)**:
  - API 通信エラー、404 Not Found、認証エラー等が発生した場合、決して「正常停止中」と偽装せず、緊急 Slack アラート（`:rotating_light:`）を発報し非ゼロ（Exit Code 1）で終了。

### 3.2 入力引数
- `--project-id`: GCP プロジェクトID（デフォルト: 環境変数 `GCP_PROJECT` または `sumifu`）
- `--region`: リージョン（デフォルト: `asia-northeast1`）
- `--mig-name`: MIG 名（デフォルト: `proxysql-mig-prod`）
- `--dry-run`: 判定のみ行い停止しないフラグ

### 3.3 パイプライン異常時クリーンアップ (`run_pipeline.py` finally ブロック)
- パイプラインのステップ（クローリング、データ検証、ML学習等）が途中で例外終了（Exit Code != 0）した場合でも、`try ... finally` ブロックにて確実に ProxySQL MIG の縮小・リソース解放を試行し、ゾンビ残存を根本防止。

---

## 4. Terraform リソース設計

### 4.1 ProxySQL MIG のオンデマンド定義 (`proxysql.tf`)
- `proxysql_min_replicas = 0`
- `proxysql_max_replicas = 2`
- 通常時の `target_size` を 0 とし、バッチ稼働時のみサイズ変更を許容する `lifecycle { ignore_changes = [target_size] }` の維持。

### 4.2 Direct VPC Egress 構成 (`cloud_run_job.tf`, `cloud_run_service.tf`, `cloud_run_api_service.tf`)
- `vpc_access` の `connector` を廃止し、Direct VPC Egress (`network_interfaces`) によるサブネット直接接続への切り替え。
- 常時稼働する VPC Access Connector (e2-micro 2台) の固定費（約 \$16/月）を削減。

### 4.3 日中帯稼働監視アラート (`alerting.tf`)
- メトリクス: `compute.googleapis.com/instance_group/size`
- フィルタ: `resource.type="gce_instance_group_manager" AND resource.labels.instance_group_manager_name="proxysql-mig-prod"`
- 条件: 閾値 `size > 0`
- アラート重要度: `ERROR`
- 目的: セーフティネットをもすり抜ける異常の早期人手介入。

### 4.4 統一ラベル仕様 (`variables.tf`, `main.tf`)
すべての主要リソースに以下を付与：
- `project`: `realestate-crawler`
- `environment`: `prod` / `staging` / `dev`
- `component`: `pipeline`, `proxy`, `database`, `api`, `networking`, `storage`
- `managed_by`: `terraform`

### 4.5 Artifact Registry ライフサイクル & デプロイ時プルーニング (`artifact_registry.tf`, `deploy-production.yml`)
- **Terraform クリーンアップポリシー**:
  - `realestate-crawler-prod` リポジトリに `keep-recent-3`（最新3世代保持）および `delete-untagged`（UNTAGGED削除）ポリシーを定義。
- **デプロイ時即時プルーニング**:
  - GitHub Actions `deploy-production.yml` での Docker push 直後に、最新3世代を超過する古いイメージダイジェストを取得して一括削除。
  - イメージが push された瞬間に即時削除され、月額約 1,000 円超のストレージ課金（81.6GB）を約 5GB へ圧縮・恒久維持。


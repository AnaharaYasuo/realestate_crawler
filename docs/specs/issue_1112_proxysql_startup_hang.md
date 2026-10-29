# ProxySQL 起動時外部通信ハング解消およびMLパイプライン起動保証仕様書 (Issue #1112)

## 1. 概要 (Overview)
Cloud NAT 撤廃（Issue #673）に伴い、GCE 上の単一 ProxySQL インスタンス (`proxysql-instance-prod`) は外部パブリック IP を持たず、直接インターネット通信ができない完全閉域 VPC 環境となっている。
しかし、`terraform/proxysql.tf` に定義されている GCE の `metadata_startup_script` は VM 起動のたびに毎回 `apt-get update` や `wget`（ProxySQL 公式リポジトリ接続）を実行しようとするため、外部接続タイムアウト待ち（指数バックオフで数分〜10分以上）によってスクリプトがハング状態に陥っていた。

この結果、深夜のクローラー完了後に起動される ML パイプラインジョブ (`realestate-ml-pipeline-prod`) の ProxySQL 接続確認 (`wait_for_proxysql_health(timeout_sec=240)`) が毎回 240 秒ジャストでタイムアウトし、コンテナが強制終了 (Exit Code 1) することで、価格推定および割安物件の Slack 通知まで一度も到達しない問題が発生していた。

## 2. 要件定義 (Requirements)
1. **既存インストール済み環境における外部通信完全スキップ**:
   - `proxysql` バイナリが既に存在し、設定ファイル `/etc/proxysql.cnf` が存在する場合は、`apt-get` や `wget` による外部リポジトリ通信を一切実行せず、即座にサービス起動・ステータス確認のみを行う。
2. **高速起動の保証**:
   - VM 起動から ProxySQL ポート 6033 受付開始までの所要時間を数秒以内に短縮し、ML パイプラインの 240 秒ヘルスチェック制限内に確実に稼働状態とする。
3. **新規プロビジョニング互換性の維持**:
   - 万が一 VM が初期化（再作成）された場合のみ、初期インストール処理へフォールバックするロジックを保持する。
4. **仕様整合性とテスト保証**:
   - 変更内容を Terraform 仕様書 (`docs/6_platform_and_release/terraform_specification.md`) 等に反映し、単体テスト・Terraform 構文テストを実施する。

# ランブック: ローカル本番パイプライン実行手順

## 1. 概要
本ランブックは、ローカル PC（Docker 環境）上で本番相当のクローリングパイプラインを安全かつ低コストに実行するための具象手順です（Issue #857 準拠）。

---

## 2. 前提条件と環境設定

### 2.1. 必要な環境
- Docker デーモンが稼働していること（[docker_daemon_management.md](docker_daemon_management.md) 参照）
- GCP IAM 権限（`roles/iap.tunnelResourceAccessor`）を持つ gcloud 認証が有効であること

### 2.2. IAP トンネルの開設 (Cloud SQL 安全接続)
Cloud SQL のパブリック IP 開放を行わず、VPC Private IP のみを維持したまま、既存の ProxySQL GCE インスタンス（`proxysql-instance-prod`）を踏み台にして IAP トンネルを開設します：
```powershell
gcloud compute start-iap-tunnel proxysql-instance-prod 6033 --local-host-port=localhost:6033 --zone=asia-northeast1-b
```

---

## 3. パイプライン実行手順

### 3.1. コンテナ環境での実行
`run_pipeline.py` を呼び出し、一連の収集・クレンジング・ML評価・リコメンドを実行します：
```powershell
docker compose exec -T -e DB_HOST=host.docker.internal -e DB_PORT=6033 -e STORAGE_BACKEND=gcs app python -m src.crawler.scripts.ops.run_pipeline
```

### 3.2. ローカル実行時の自動安全策 (Safety-Net)
- `IS_CLOUD` 環境変数が未設定の場合、`run_pipeline.py` はクラウドインフラ操作（ProxySQL や Cloud SQL の GCE/Cloud SQL API 起動・停止）を自動的にスキップします。
- 共有 ProxySQL インスタンスの直接停止コマンド（`gcloud compute instances stop` 等）は絶対に発行してはなりません。

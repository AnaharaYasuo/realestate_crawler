# 要件定義書: ローカル Docker クローラー実行による Cloud Run コスト削減 (Issue #857)

## 1. 背景と課題
現在、日次クローラーパイプラインは GCP Cloud Run Jobs 上で実行されている。
Cloud Run Jobs の実行時間に応じた vCPU / メモリ課金および、それに付随する ProxySQL インスタンスの稼働により、クラウド実行コストが発生している。
開発時やデータ収集において、手元のローカル PC（Docker 環境）の余剰計算リソースを活用してクローリングを実行することで、Cloud Run の実行コストを大幅に削減したい。

## 2. 目的と要件
1. **追加インフラコスト ¥0 の安全な Cloud SQL 接続**:
   - Cloud SQL のパブリック IP 開放（`ipv4_enabled=true`）や VPN 導入を行わず、VPC Private IP のみを維持する。
   - 既存の ProxySQL GCE インスタンス（`proxysql-instance-${var.environment}`）を踏み台とし、Google Identity-Aware Proxy (IAP) トンネル経由で安全に暗号化接続を確立する。
   - 固定 IP を不要とし、IAM 認証（`roles/iap.tunnelResourceAccessor`）を持つユーザーのみがトンネルを開設できるようにする。
2. **画像データの GCS 直接永続化**:
   - ローカル Docker 上でスクレイピングした物件画像を、ローカル MinIO ではなくクラウドの GCS バケットへ直接アップロードできるようにする（`STORAGE_BACKEND=gcs`）。
   - ローカルからクラウドへの画像同期バッチ等の余計な運用コストを発生させない。
3. **ローカル環境に適したリソース・並列度制御**:
   - クラウド向けの大規模並列（標準 9 / Playwright 3）ではなく、ローカルマシンの負荷や Cloud SQL の同時接続数に配慮した並列度（環境変数 `CRAWLER_PARALLEL`, `CRAWLER_PLAYWRIGHT_PARALLEL`, `DETAIL_CONCURRENCY`）を柔軟に設定可能にする。
4. **クラウド専用インフラ操作の安全なバイパス**:
   - ローカル実行時（`IS_CLOUD` 未設定）は、`run_pipeline.py` から ProxySQL や Cloud SQL の GCE/Cloud SQL API 操作を呼び出さず、安全にスキップする。

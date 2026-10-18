# 環境制御およびヘッドレス運用ポリシー (Environment Control Policy)

## 1. 目的と存在理由 (Why)
開発やパイプラインの実行にあたり、ユーザーへ環境準備の手間を返さず、かつユーザーのデスクトップ作業（GUI画面）を一切妨害しないことを目的とします。

---

## 2. コア規範 (Rules & Boundaries)

### 2.1. 自律準備の義務 (Self-Sufficiency)
- Docker やローカルサービスが停止していても、「起動してください」とユーザーに作業を丸投げしない。
- 必要なランタイムはエージェント自身の手で自律的に準備・起動してから作業を完遂すること。

### 2.2. 完全ヘッドレス原則 (Strictly Headless / Background-Only)
- エージェントは CLI・サービス・デーモンとしてのみ環境を制御する。
- ユーザーのデスクトップにウィンドウをポップアップさせたり、GUI アプリケーション（`Docker Desktop.exe` 等）を直接開く行為は「ユーザーの作業領域への不法侵入」とみなし全面厳禁とする。
- 具象手順: [docker_daemon_management.md](../../docs/runbooks/docker_daemon_management.md)

### 2.3. 共有インフラ保護原則 (Shared Infrastructure Protection)
- 複数セッションや本番定期パイプラインで共有されるインフラリソース（ProxySQL VM `proxysql-instance-prod`、Cloud SQL、VPC等）を、エージェントの自律判断で直接停止コマンド（`gcloud compute instances stop` 等）を発行して停止することを全面禁止とする。
- 停止が必要な場合は、必ず稼働中ジョブを検証する安全停止スクリプト（`src/crawler/scripts/ensure_resources_stopped.py`）を経由させること。

### 2.4. ホスト・コンテナ間依存の排除 (Host-Container Isolation)
- Python を動かすコード（スクリプト実行・クローラー実行・pytest）は、必ず Docker コンテナ内で実行すること。ホスト環境の Python に依存してはならない。
- パス指定において `/app/` などの特定の絶対パスをハードコードしてはならない。常に `__file__` から動的に相対解決すること。

# GCP Terraform デプロイ・運用ガイド

本ディレクトリは、不動産クローラーおよびML価格推定パイプライン（案A：Cloud Run Jobs + Cloud SQL + GCS、将来の案C対応）を GCP 上に一括プロビジョニングするための Terraform コード群です。

---

## 前提条件

1. **Google Cloud SDK (`gcloud`) のインストールおよび認証**:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project sumifu
   ```
2. **Terraform CLI (>= 1.5.0) のインストール**:
   - Windows: `winget install HashiCorp.Terraform` または [公式配布ページ](https://developer.hashicorp.com/terraform/install) より導入。

---

## デプロイ手順

### 1. 変数の設定
`terraform.tfvars.example` をコピーして `terraform.tfvars` を作成し、必要に応じて設定値を調整します：
```bash
cp terraform.tfvars.example terraform.tfvars
```

### 2. 初期化とプロビジョニング
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### 3. コンテナイメージのビルドとプッシュ
Terraform 適用後に出力される Artifact Registry リポジトリに、Docker イメージをビルド＆プッシュします：
```bash
# Docker の gcloud 認証設定
gcloud auth configure-docker asia-northeast1-docker.pkg.dev

# イメージのビルド & プッシュ
docker build -t asia-northeast1-docker.pkg.dev/sumifu/realestate-crawler-prod/crawler:latest .
docker push asia-northeast1-docker.pkg.dev/sumifu/realestate-crawler-prod/crawler:latest
```

### 4. マイグレーションの実行
Cloud Run Job またはローカル（Cloud SQL Auth Proxy経由）から初期マイグレーションを実行：
```bash
python src/crawler/scripts/ops/run_migrations.py
```

### 5. 手動スモーク実行（テスト）
```bash
gcloud run jobs execute realestate-crawler-pipeline-prod --region asia-northeast1
```

---

## 案C（並列分散実行）への拡張方法
将来的に 20 サイトの同時並列実行を行いたい場合、`cloud_run_job.tf` の以下を変更して `terraform apply` を再実行するだけで拡張可能です：
```hcl
template {
  task_count  = 20  # 20並列タスク
  parallelism = 5   # 同時実行数 5〜10
  ...
}
```
コンテナ内では環境変数 `CLOUD_RUN_TASK_INDEX` を参照して対象サイトが自動分散されます。

---

## ProxySQL コネクションプーリング層 (`proxysql.tf`)
大量並行クローラープロセスからの同時DB接続を集約・多重化し、Cloud SQL (MySQL 8.0) の耐用上限ギリギリのコネクション数を安全に維持するためのプロキシ基盤です：
- **MIG & Autoscaler**: `e2-micro`（通常1台 ➔ CPU負荷に応じて最大2台へオートスケール、2ゾーン分散）
- **ILB**: 内部TCPロードバランサー（ポート 6033、TCPヘルスチェック、コネクションドレイン 300秒）
- **Cloud Run からの接続**: ILB のプライベート IP（`proxysql_ilb_ip` 出力値）に対してポート 6033 で接続

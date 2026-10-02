# deploy-production ワークフローにおけるイメージ管理・デプロイ順序安全化内部設計書 (Issue #593)

## 1. 概要
本内部設計書は、`.github/workflows/deploy-production.yml` におけるジョブ・ステップ構造の YAML 定義および具体的な変更内容を規定する。

## 2. ワークフロー定義変更仕様

### 2.1 対象ジョブ: `build-and-deploy-container`
ステップ実行リストを以下の順序に再編成する：

1. `Checkout repository` (`actions/checkout@v7.0.1`)
2. `Authenticate to Google Cloud` (`google-github-actions/auth@v3`)
3. `Set up Cloud SDK` (`google-github-actions/setup-gcloud@v3`)
4. `Configure Docker for Artifact Registry` (`gcloud auth configure-docker`)
5. `Set up Docker Buildx` (`docker/setup-buildx-action@v4`)
6. `Build and push Docker image` (`docker/build-push-action@v7`)
7. `Run Database Migrations on Cloud SQL` (`gcloud run jobs update/execute realestate-migrate-prod`)
8. `Update Cloud Run Job Image` (`realestate-crawler-pipeline-prod`)
9. `Update Cloud Run Service Image` (`realestate-slack-agent-prod`)
10. `Update Cloud Run API Service Image` (`realestate-api-prod`)
11. `Update Crawler Worker Service Image` (`realestate-crawler-worker-prod`)
12. `Update Crawler Dispatcher Job Image` (`realestate-crawler-dispatcher-prod`)
13. `Update ML Pipeline Job Image` (`realestate-ml-pipeline-prod`)
14. `Update Safety Net Job Image` (`realestate-safety-net-prod`)
15. **`Prune old images (Keep latest 3 versions)`** (★全更新ステップ完了後に移動)
16. `Notify New Relic Deployment (Change Tracking)`

### 2.2 Prune ステップのシェルスクリプト仕様
```yaml
      - name: Prune old images (Keep latest 3 versions)
        run: |
          set -euo pipefail
          echo "Pruning Artifact Registry images, keeping latest 3 versions..."
          old_digests=$(gcloud artifacts docker images list \
            asia-northeast1-docker.pkg.dev/sumifu/realestate-crawler-prod/crawler \
            --sort-by=~CREATE_TIME \
            --format="value(version)" | sed -e '1,3d' || true)
          if [ -n "$old_digests" ]; then
            while read -r digest; do
              if [ -n "$digest" ]; then
                echo "Deleting old image digest: $digest"
                if ! gcloud artifacts docker images delete \
                  "asia-northeast1-docker.pkg.dev/sumifu/realestate-crawler-prod/crawler@$digest" \
                  --quiet --delete-tags; then
                  echo "::warning::Failed to delete image digest: $digest"
                fi
              fi
            done <<< "$old_digests"
          fi
```

### 2.3 安全性の根拠
- `set -euo pipefail` により先行ステップで非ゼロ終了した時点でジョブは即座に FAIL し、以後のステップはスキップされる。
- したがって、DBマイグレーションまたは Cloud Run 更新のいずれかが失敗した場合、`Prune old images` ステップは絶対に実行されない。
- 新規イメージがデプロイされ全サービスが正常に稼働を確立した後にのみ古いイメージが削除されるため、稼働中リソースのイメージ消失が防止される。

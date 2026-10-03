# deploy-production ワークフローにおけるイメージ管理・デプロイ順序安全化要件定義書 (Issue #593)

## 1. 概要
本要件定義書は、本番環境デプロイパイプライン（`.github/workflows/deploy-production.yml`）におけるコンテナイメージのライフサイクル管理、およびビルド・マイグレーション・サービス更新・プルーニング（Prune）の安全な実行順序に関する要件を規定する。

## 2. 背景・課題
- **事象**: `deploy-production.yml` において、Docker イメージのビルド・プッシュ直後に Artifact Registry 上の古いイメージを削除する `Prune old images` ステップが配置されていた。
- **問題の発生機構**:
  1. 新しいイメージをプッシュ。
  2. `Prune old images` で最新3世代以外（直前まで稼働していたイメージ実体を含む）を削除。
  3. `Run Database Migrations on Cloud SQL` でマイグレーションジョブが失敗・中断。
  4. 後続の `Update Cloud Run Job Image`（`realestate-crawler-pipeline-prod` 等）および `Update Cloud Run Service Image` がスキップされる。
  5. 結果として、Cloud Run Job 側が「削除されて存在しなくなった古いコミットハッシュタグ」を参照したまま取り残され、日次定期実行時に `Image not found` によるハング・起動失敗が発生する。
- **要件の目的**: デプロイが途中のステップ（マイグレーション等）で失敗・中断した場合であっても、本番稼働中の Cloud Run Job / Service が参照不能な孤立状態（Untagged/Image not found）に陥ることを物理的に根絶する。

## 3. 機能要件

### FR-DEP-001: デプロイ完了後プルーニング原則（Post-Deployment Pruning）
- `Prune old images` ステップは、すべての Cloud Run Job（`realestate-migrate-prod`, `realestate-crawler-pipeline-prod`, `realestate-crawler-dispatcher-prod`, `realestate-ml-pipeline-prod`, `realestate-safety-net-prod`）および Cloud Run Service（`realestate-slack-agent-prod`, `realestate-api-prod`, `realestate-crawler-worker-prod`）のイメージ更新が完全に成功した後にのみ実行すること。
- デプロイの途中でマイグレーション失敗や設定不整合等のエラーが発生して中断した場合、後続のプルーニングは実行されず、既存の稼働中イメージが安全に維持されること。

### FR-DEP-002: 不変イメージ参照およびタグ整合性の保証
- ビルド・プッシュされたコンテナイメージは、コミットハッシュタグ（`${{ github.sha }}`）および最新タグ（`latest`）として Artifact Registry に保持され、各 Cloud Run コンポーネントへ確実に伝播されること。
- 全更新が成功した後にのみ最新 3 世代以外の不要イメージを削除（`keep latest 3 versions`）すること。

## 4. 非機能要件
- **NFR-DEP-001 安全性（Fail-Safe）**: デプロイジョブのいずれかの先行ステップが失敗した場合、稼働中リソースが参照している可能性のあるイメージを絶対に削除しないこと。
- **NFR-DEP-002 保守性（Maintainability）**: ワークフロー定義のステップ順序が明示的かつ直感的であり、New Relic デプロイ通知等の外部通知処理と矛盾なく整流化されていること。

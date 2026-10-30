# クローラーからのDBマイグレーション撤去 外部設計書 (Issue #932)

## 責務分離
| 工程 | 担当 | スキーマ変更 |
|------|------|-------------|
| 本番デプロイ | `deploy-production.yml` → Cloud Run Job `realestate-migrate-prod` | 実行する（唯一） |
| クロール/ディスパッチ | `run_pipeline.py` / `run_dispatcher.py` | 実行しない |
| ローカル本番実行 | `run_pipeline.py` | 実行しない（#909 ガードでも遮断） |

## パイプライン手順（変更後）
Step 0 Slack疎通 → Step 0.4 DB疎通 → クロール（旧 Step 0.5 の migrate は撤去）

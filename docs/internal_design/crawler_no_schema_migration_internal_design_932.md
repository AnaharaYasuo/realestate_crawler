# クローラーからのDBマイグレーション撤去 内部設計書 (Issue #932)

## 変更点
- `src/crawler/scripts/ops/run_pipeline.py`: `# Step 0.5` の coordinator `migrate` 実行ブロックと、worker 側の 10 秒待機 `else` ブロックを削除。
- `src/crawler/scripts/ops/run_dispatcher.py`: `run_db_migration()` 関数と `main()` 内の呼び出しを削除。
- `src/crawler/tests/unit/test_dispatcher_and_ml_pipeline.py`: `run_db_migration` のパッチ/検証を削除。
- `src/crawler/tests/unit/test_no_migrate_in_crawler_932.py`: ソース上に `migrate` 実行が残っていないことを検証する回帰テストを追加。

## 影響範囲
`manage.py migrate` の呼び出し元は `deploy-production.yml`（Cloud Run Job `realestate-migrate-prod`）と `terraform/cloud_run_job.tf` の `db_migrate_job` のみとなる。

## 起動順序の保証（スキーマ更新完了が前提）
- deploy-production.yml は Run Database Migrations on Cloud SQL ステップ（gcloud run jobs execute realestate-migrate-prod --wait）が成功した後に、はじめて ealestate-crawler-pipeline-prod / ealestate-crawler-dispatcher-prod 等のジョブイメージを更新する。--wait により失敗時はステップが失敗し後続のイメージ更新は実行されない。
- よって新コード（スキーマ前提のクローラー/ディスパッチャー）は、マイグレーション成功後にしか配備されない。クローラー側でスキーマ更新を待機・実行する必要はない。
- ローカル本番実行は、デプロイ済みスキーマ（production マージ後）を前提とする。

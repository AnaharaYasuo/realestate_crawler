# クローラーからのDBマイグレーション撤去 要件定義書 (Issue #932)

## 背景
`run_pipeline.py`（Step 0.5）と `run_dispatcher.py`（`run_db_migration`）が起動のたびに `manage.py migrate` を実行していた。クロールは INSERT/UPDATE のみで、スキーマ変更権限をクローラーが持つ必要はない。#909 の本番DB保護ガードにより、ローカル本番実行は Step 0.5 で `CRITICAL BLOCK` され起動不能となった。

## 要件
- FR-1: `run_pipeline.py` は `manage.py migrate` を実行しない。
- FR-2: `run_dispatcher.py` は `manage.py migrate` を実行しない（`run_db_migration` を撤去）。
- FR-3: スキーマ変更は `.github/workflows/deploy-production.yml` の `realestate-migrate-prod` ジョブ（CI/CD）のみが実行する。
- FR-4: 非 coordinator ワーカーの「マイグレ完了待機(10秒)」も不要のため撤去する。

## 受入基準
Issue #932 参照。

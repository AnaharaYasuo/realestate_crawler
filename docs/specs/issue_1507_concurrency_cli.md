# Issue #1507 仕様設計書
## バルク推論 Concurrency CLI 引数化 & マンション4並列検証

### 1. 概要
- `run_ml_pipeline.py` において、バルク価格推論（Step 4）の並列度を CLI 引数 `--concurrency` で直接指定可能にする。
- ユーザー指示に基づき、データ量が最も多いマンションモデルにおいて 4並列でのバルク推論の安定稼働とメモリ消費（2GiB上限内）を検証する。

### 2. 要件仕様
1. `run_ml_pipeline.py`:
   - `--concurrency` 引数を追加。
   - デフォルト値は環境変数 `BULK_EVAL_CONCURRENCY`（未設定時は `"2"`）。
   - `eval_cmd` 構築時に `--concurrency <concurrency>` を透過的に渡す。
2. SDD & テスト:
   - `docs/4_valuation_and_ml/ml_model_specifications.md` に `--concurrency` CLI オプションを追記。
   - 単体テストで `--concurrency 4` 指定時に `eval_cmd` へ正しく渡されることを検証。

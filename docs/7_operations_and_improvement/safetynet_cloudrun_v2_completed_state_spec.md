# Safety-Net Cloud Run v2 Execution 完了状態判定仕様

## 1. 背景・課題 (Issue #1732)
`src/crawler/scripts/ensure_resources_stopped.py` は Cloud Run Jobs の実行中ジョブを検知する際、`completionTime` が未設定の場合に `conditions` の `Completed` 条件を参照して完了済みかどうかを判定している。

Cloud Run Jobs v2 REST API / gRPC クライアントでは、失敗した execution（例: `realestate-migrate-prod-lsfkh`）において `completionTime` が `null` となり、完了状態が `conditions[].status`（v1 仕様: `"True"` / `"False"`）ではなく `conditions[].state`（v2 仕様: `"CONDITION_SUCCEEDED"` / `"CONDITION_FAILED"`）に格納される。

従来の実装は `status` のみを参照していたため、既に `CONDITION_FAILED` で終了済みのジョブを実行中（active）と誤認し、長時間経過したハングジョブとして「ゾンビ課金アラート」および ProxySQL 強制停止を誤発動していた。

## 2. 仕様・変更内容
- `_is_completed_condition(cond)` ヘルパー関数を導入し、gRPC オブジェクト・REST API 辞書の両方に対して以下の判定を行う。
  - `type` / `type_` が `"Completed"` であること。
  - `state` に `"CONDITION_SUCCEEDED"` または `"CONDITION_FAILED"` が含まれる場合（v2 仕様）、完了とみなす。
  - `status` に `"TRUE"` または `"FALSE"` が含まれる場合（v1 仕様）、完了とみなす。
- ユニットテスト `src/crawler/tests/unit/test_crawler_hang_timeout_861.py::test_is_completed_condition_handles_cloud_run_v2_states` にて v1/v2 両形式の判定を検証する。

# 内部設計書: Bulk ML イテレータ接続維持・Teardown確実停止・クローラー無応答Fast-Fail仕様 (Issue #883)

## 1. モジュール構成と変更概要
- `src/crawler/package/ml/evaluation/targets.py`:
  - `iter_active_items`:
    - 単一の長大なカーソルイテレーション (`.iterator(chunk_size=2000)`) を利用せず、`pk > last_pk` によるキーセットページネーション（`order_by("pk")[:fetch_size]`）またはチャンク取得ごとに `django.db.close_old_connections()` を呼ぶ設計へ変更。
    - これにより、1チャンクの推論・DB保存（`bulk_create` / `bulk_update`）にどれだけ時間がかかっても、次チャンク取得時に常に健全な DB コネクションが使用され、OperationalError (2006) が発生しない。
- `src/crawler/scripts/ops/run_ml_pipeline.py`:
  - `finally` 句の teardown 処理:
    - `scale_proxysql_mig(target_size=0, dry_run=args.dry_run)` の呼び出しを最大 3 回リトライ。
    - ゾンビ課金を防止するため、確実に API 要求が受理されたことを確認する。
- `src/crawler/package/parser/baseParser.py`:
  - `_getContent`:
    - `CONNECT_TIMEOUT_SEC`（10秒）および `REQUEST_TIMEOUT_SEC`（15秒）を有限厳格化。
    - 連続タイムアウト発生時のバックオフを適正化し、`ServerDownException` による即時中断（Fast-Fail）を徹底。
- `src/crawler/scripts/ops/run_all_crawlers.py`:
  - プロセス終了回収ロジックにおいて、`exit_code == -9` または `-1`（SIGKILL / Watchdog キル）の検知時に、`ProcessCrashFailure` ではなく `WatchdogTerminatedFailure` として詳細な理由（「Watchdogにより600秒無進捗で強制終了」）を FailureReporter とログに明示。

## 2. インターフェース設計
### `package.ml.evaluation.targets.iter_unprocessed_chunks`
```python
def iter_unprocessed_chunks(
    model: Any,
    existing_eval_map: dict[str, Any],
    force: bool = False,
    limit: int | None = None,
    chunk_size: int = 1000,
) -> Iterator[tuple[list[Any], int]]:
    # pk > last_pk 方式で chunk_size ずつ取得
    # 各バッチ走査前後で close_old_connections() を実行
```

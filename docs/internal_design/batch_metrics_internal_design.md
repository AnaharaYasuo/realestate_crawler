# バッチ処理標準メトリクス内部設計書 (Batch Metrics Internal Design)

## 1. 概要
本設計書は、基本設計書（`docs/basic_design/batch_metrics_design.md`）に基づき、`BatchMetrics` クラスの内部実装仕様、各バッチスクリプト（`train.py`, `run_bulk_ml_evaluation.py`, `send_recommendations.py`）への組み込み詳細、およびスレッドセーフティ/例外耐性を規定する。

---

## 2. 内部モジュール設計: `package.utils.batch_metrics`

### 2.1 クラス構成
- **ファイル配置**: `src/crawler/package/utils/batch_metrics.py`
- **主要クラス**: `BatchMetrics`
- **ヘルパー関数**:
  - `format_batch_duration(seconds: float) -> str`
  - `format_iso_datetime(timestamp: float | None) -> str`
  - `format_throughput(count: int, seconds: float) -> tuple[float, float]`

### 2.2 メソッド仕様
1. `record_processed(n: int = 1)`: 処理完了件数をスレッドセーフにインクリメント。
2. `record_skipped(n: int = 1)`: スキップ件数をインクリメント。
3. `record_failed(n: int = 1)`: 失敗件数をインクリメント。
4. `set_metric(key: str, val: Any)`: 任意ドメイン固有メトリクス（1次通過数、重複数等）を保持。
5. `finish() -> float`: 終了時刻を確定し、所要秒数を返却。
6. `build_slack_summary(title: str, custom_lines: list[str] | None = None) -> str`: Slack通知用ブロック文字列を生成。
7. `build_log_banner(title: str, custom_sections: list[str] | None = None) -> str`: ログバナー文字列を生成。

---

## 3. 各バッチスクリプトへの組込仕様

### 3.1 価格推定処理 (`run_bulk_ml_evaluation.py`)
- `run_bulk_evaluation()` の開始時に `metrics = BatchMetrics("Bulk ML Evaluation")` を初期化。
- `existing_eval_map` から既存評価件数をカウントし、対象全モデルの物件総数を `metrics.total_count` に設定。
- スレッドプール実行内で、モデルごとに `cnt`, `skp` を集計。
- 1次通過件数 (`is_first_stage_passed=True`)、重複件数 (`duplicate_of__isnull=False`)、投資評価件数をカウントして `set_metric()` に格納。
- 完了時に `metrics.finish()` を実行し、`build_slack_summary()` で生成された文字列を `_notify_slack()` で送信。

### 3.2 割安物件配信処理 (`send_recommendations.py`)
- `send_recommendations()` 開始時に `metrics = BatchMetrics("Slack Recommendation")` を初期化。
- `candidates = _fetch_recommendation_candidates()` の件数を `metrics.total_count` に設定。
- 基準合致件数 (`len(matched_candidates)`) を `metrics.set_metric("matched_count", ...)` に記録。
- 配信成功時、チャンネル別カウンタ（`channel_counts[channel_name] += 1`）を更新。
- 0件終了時および配信完了時に、`build_slack_summary()` を用いて正確な所要時間と内訳を含むメッセージを Slack に投稿。

### 3.3 学習処理 (`train.py`)
- `main()` 開始時に `metrics = BatchMetrics("ML Model Training")` を初期化。
- `_train_single_ptype_models()` 実行ごとに、種別（mansion, kodate, tochi, apartment）、投入件数、クレンジング後有効件数、MdAPE、R²、所要時間を辞書として記録。
- 全種別の学習完了時に、構造化されたバナーを出力して全体スループットおよび保存アーティファクト件数を可視化。

---

## 4. テスト設計 (TDD)
- **テストファイル**: `src/crawler/tests/unit/test_batch_metrics.py`
- **検証項目**:
  1. `BatchMetrics` の初期化、時間計測、所要時間フォーマット（秒、分秒、時間分秒）の正常性。
  2. スループット（件/秒）および平均レイテンシ（ms/件）の計算精度（ゼロ除算耐性含む）。
  3. Slack サマリーメッセージの生成フォーマット検証。
  4. ログバナーメッセージの生成フォーマット検証。
  5. スレッドセーフなカウンタ操作の検証。
  6. `run_bulk_ml_evaluation.py` および `send_recommendations.py` のメッセージフォーマット統合検証。

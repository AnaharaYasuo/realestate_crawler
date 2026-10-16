# 内部設計書: Issue #952 クローラー子プロセスからの処理件数直接回収およびステップ間DB接続回復

## 1. モジュール修正詳細

### 1.1 `src/crawler/main.py`
- クローラー完了時、`CrawlerReporter` または `JobMetrics` が保持する `detail_cnt`, `skipped_cnt` などの実績値を JSON ファイルに保存する関数 `export_job_metrics(company, property_type, metrics)` を実装・呼び出し。
- ディレクトリ: `logs/runs/<today_str>/` を作成し、ファイル名 `metrics_<company>_<property_type>.json` でアトミックに書き込み。

### 1.2 `src/crawler/scripts/ops/run_all_crawlers.py`
- `read_job_metrics(company, property_type, run_date)` 関数を追加。
- ジョブ終了判定処理部において:
  1. `read_job_metrics()` を呼び出し、取得成功した場合はその件数をそのまま採用し、DB クエリ `get_count_for_job()` を発行しない。
  2. メトリクスファイルが存在しない場合のみ `get_count_for_job()` を呼び出す。
  3. `get_count_for_job()` 内で例外が発生した場合、子プロセスの `returncode == 0` であれば例外をログ警告にとどめ、`count = 0` または `None` を返しジョブ自体は「正常完了」として扱う。

### 1.3 `send_recommendations.py` & `run_daily_prediction_diagnostics.py`
- スクリプト冒頭（DBクエリ発行前）で `django.db.connections.close_all()` を実行し、残留した不健全なコネクションを確実に破棄。

### 1.4 マイグレーション整合性回復
- `src/crawler/package/migrations/` 配下に `ReguideInvestment` の最新差分（0065）を追加し、`python src/crawler/manage.py makemigrations --check --dry-run` を Exit 0 にする。

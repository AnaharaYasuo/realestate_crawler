# 外部設計書: クローラー全体タイムアウト4時間化・東急無差別取得是正・DB負荷軽減 (Issue #1055)

## 1. システム全体への影響範囲
- **インフラ (Terraform)**:
  - `terraform/variables.tf`: `crawler_timeout` default="14400s", validation 14400
  - `terraform/cloud_run_job.tf`: `CRAWLER_HANG_THRESHOLD_SEC` = 180
- **クローラー運用スクリプト**:
  - `src/crawler/scripts/ops/run_pipeline.py`: `DEFAULT_TIMEOUT_SEC = 14400.0`
  - `src/crawler/scripts/ops/run_all_crawlers.py`: `timeout_sec = 14400`, 監視DBクエリ撤廃
  - `src/crawler/scripts/ensure_resources_stopped.py`: `DEFAULT_HUNG_THRESHOLD_SEC = 15000.0`
- **パーサー (`src/crawler/package/parser/tokyuParser.py`)**:
  - `TokyuParser.parsePropertyListPage`: `seen = set()` による重複排除
  - `TokyuParser.parseRootPage`: 都道府県リンクの重複排除
  - `TokyuParser.parseAreaPage`: 市区町村リンクの厳格フィルタと重複排除
- **監視ユーティリティ (`src/crawler/package/utils/crawler_watchdog.py`)**:
  - 既定ハング閾値 180.0s、Windows環境対応（`os.getpgid` fallback）

---

## 2. 外部インターフェース仕様
- **Slack通知**:
  - ハング検知メッセージに「180秒間無進捗のため打ち切り」と反映される。
- **New Relic メトリクス**:
  - `CrawlerExecution` の status="hung_timeout" において、`metadata.error_msg` に「180s」と記録される。
- **GCS メトリクス**:
  - `metrics_tokyu_tochi.json` などの total_cnt が、重複排除により実物件数（千数百件規模）に正常化される。

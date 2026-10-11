# 要件定義書: Task 0 ハング防止・Watchdog確実検知・タイムアウト3時間短縮・HTTPタイムアウト厳格化 (Issue #861)

## 1. 背景と課題
- **事象**: 2026-10-10 夜間の定期クローリング実行において、Cloud Run Job (`realestate-crawler-pipeline-prod`) の Task 0 が 5時間16分にわたって起動し続け、ハングしたまま大量の無駄なクラウドリソース・コストが発生した。
- **根本原因**:
  1. `api.py` の `_apply_download_delay_if_needed`: クラス変数 `_SITE_RATE_LOCKS` に保存された `asyncio.Lock` が、`_handle_local_execution` 内でリクエストごとにスレッド生成される新しいイベントループと一致せず `RuntimeError: Lock is bound to a different event loop` を発生させ、さらにデッドロック／スレッドハングを誘発。
  2. `api.py` の `_handle_local_execution`: ワーカー子スレッド `t.join(1.0)` に全体タイムアウトが設定されておらず、スレッドハング時に無制限にループし続けた。
  3. `run_all_crawlers.py` の Watchdog: `HANG_THRESHOLD_SEC`（600秒）による進捗沈黙監視ループにおいて、`break` 文が存在するため1ループに1ジョブしか検査されず、全アクティブジョブの公平な巡回が阻害されていた。
  4. クローリング全体のタイムアウトが 9時間（32,400秒）と長大であり、ハング検知漏れ時に不要な高額稼働が継続した。
  5. HTTP/スクレイピングリクエストにおける `aiohttp.ClientTimeout` の総タイムアウトが明示的に徹底されていなかった。

## 2. 要件一覧
- **REQ-861-01 (レートリミッターのスレッドセーフ化)**:
  `ParseDetailPageAsyncBase._apply_download_delay_if_needed` におけるサイト別レート制御ロックを、イベントループ依存の `asyncio.Lock` からスレッドセーフな `threading.Lock` に移行し、異なるイベントループ間での `RuntimeError` やデッドロックを根絶する。
- **REQ-861-02 (ローカル実行スレッドの有限時間タイムアウト保証)**:
  `ApiAsyncProcBase._handle_local_execution` において、ワーカースレッドの累積実行時間に上限（デフォルト120秒、または `_getTimeOutSecond()` 連動）を設け、タイムアウト時はスレッドを切り捨てて `(detail_url, 504, "LocalTimeout")` を返却する。
- **REQ-861-03 (Watchdog の全アクティブジョブ走査と即時強制終了)**:
  `run_all_crawlers.py` の子プロセス進捗監視ループから不当な `break` を撤廃し、15秒の点検間隔を満たした全アクティブジョブを公平に走査・検査する。進捗が `HANG_THRESHOLD_SEC`（600秒）を超えて沈黙したプロセスグループは `kill_hung_job_process` により確実に SIGKILL で強制終了する。
- **REQ-861-04 (クローリング全体タイムアウトの3時間短縮)**:
  クローリング全体の実行タイムアウトを 9時間（32,400秒）から 3時間（10,800秒）へ短縮する。
  連動して `terraform/variables.tf` (`crawler_timeout` default="10800s")、`run_all_crawlers.py`、`run_pipeline.py`、Safety-Net (`ensure_resources_stopped.py` の `DEFAULT_HUNG_THRESHOLD_SEC` = 11,400秒 = 10,800 + 600)、Workflows (`daily_pipeline.yaml`, `recrawl_anomalies_pipeline.yaml`) をすべて 10,800秒基準に整合させる。
- **REQ-861-05 (HTTP / スクレイピングリクエストタイムアウトの厳格化)**:
  パーサーおよび API 基底クラスにおける HTTP 取得処理に有限タイムアウト（最大15秒）を厳格に適用し、ネットワーク無応答によるハングを防止する。

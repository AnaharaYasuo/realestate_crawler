# 要件定義書: Bulk ML イテレータ接続維持・Teardown確実停止・クローラー無応答Fast-Fail仕様 (Issue #883)

## 1. 背景と課題
- **事象1 (Bulk ML OperationalError 2006)**:
  2026-10-12 01:37 JST 起動の ML パイプライン (`realestate-ml-pipeline-prod`) において、`run_bulk_ml_evaluation.py` (Step 3/5) の実行中に `MySQLdb.OperationalError: (2006, '')` が発生し、ジョブが異常終了した。
  原因は `package/ml/evaluation/targets.py` の `iter_active_items` が `model.objects.all().order_by("pk").iterator(chunk_size=2000)` で単一カーソルを長時間保持したままチャンク処理を進めるため、1チャンクの推論・保存に時間がかかると MySQL / ProxySQL のアイドルタイムアウト (`wait_timeout`) を超過して接続が切断され、次チャンク取得時にエラーとなること。
- **事象2 (ProxySQL ゾンビ課金リスク)**:
  `run_ml_pipeline.py` の `finally` 句で `scale_proxysql_mig(target_size=0)` を実行しているが、REST API タイムアウトや例外ハンドリング不足によりインスタンスが `TERMINATED` にならず `RUNNING` のまま残存していた。
- **事象3 (クローラー大量ハング・Exit Code -9)**:
  相手先 Web サーバーが無応答または極めて遅延している際、`crawler_watchdog` が 600 秒間進捗（DB保存件数増分）なしとして子プロセスグループを SIGKILL (`Exit Code: -9`) していた。
  また中間ページ探索 (`_getContent`) において、リトライや Playwright / HTTP タイムアウトが相手無応答時に有限上限で素早く中断されず、ジョブが沈黙状態に陥っていた。

## 2. 要件一覧
- **REQ-883-01 (Bulk ML イテレータの接続切断防止・接続リフレッシュ)**:
  `iter_active_items` および `iter_unprocessed_chunks` において、チャンク単位ごとに `django.db.close_old_connections()` を適切に呼び出すか、長時間の単一カーソルイテレーションを避け、`pk > last_pk` 方式（キーセットページネーション）またはチャンク単位の安全なクエリ分割により DB アイドル切断（OperationalError 2006）を根絶する。
- **REQ-883-02 (ML パイプライン teardown での確実な ProxySQL 停止保証)**:
  `run_ml_pipeline.py` の終了時 teardown フックにおいて、`scale_proxysql_mig(target_size=0)` の呼び出しをリトライ付きで確実に行い、停止成功を自己検証する。
- **REQ-883-03 (クローラー無応答時の Fast-Fail 保証)**:
  相手サーバーの無応答・タイムアウト頻発時に、長時間ブロックせず Fast-Fail 原則に従って例外（`ServerDownException`）を送出し、Watchdog の 600 秒沈黙 SIGKILL を回避して正常なエラー回収（リトライ・スキップ）へ遷移させる。
- **REQ-883-04 (Watchdog の死因ログ明確化)**:
  Watchdog が 600 秒無進捗でプロセスグループを強制終了した際、単に「Exit Code: -9」として扱われるだけでなく、対象プロセスの PID、経過時間、直前の状態を明確にログおよび Slack 通知に記録する。

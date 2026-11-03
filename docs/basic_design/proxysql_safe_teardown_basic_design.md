# ProxySQL停止安全ガード化と並列実行巻き込み停止防止 基本設計書 (Issue #1216)

## 1. システム方針
共有リソースである ProxySQL インスタンス（`proxysql-instance-prod`）は、複数の実行主体（ローカル手動実行、クラウド日次クローラー、クラウドMLパイプライン）から同時接続されうる。
したがって、単一の処理が完了または異常終了したからといって、無条件で停止APIを発行してはならない。

## 2. 設計方針
1. **停止判断の厳格化**:
   - `run_ml_pipeline.py` においても、`run_pipeline.py` と同様に `has_active_other_cloud_run_executions` を用いて、稼働中の別ジョブが存在するかを必ず確認する。
   - ホスト上のローカル実行時は、クラウド上の ProxySQL をコードから勝手にシャットダウンさせない（`IS_CLOUD` チェック）。
2. **Workflows と Safety-Net の責務境界**:
   - Cloud Workflows はバッチ全体の直列実行制御（Orchestration）に特化し、リソースのシャットダウン判断は個別のジョブ内部の Teardown、および監視デーモンである Safety-Net に委譲する。
   - Safety-Net は直近 10 分間のネットワーク通信量（受信バイト数）を Cloud Monitoring 経由で確認してから安全に停止するため、ローカルからの外部通信も検知して保護できる。

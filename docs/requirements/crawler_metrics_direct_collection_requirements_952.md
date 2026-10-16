# 要件定義書: Issue #952 クローラー子プロセスからの処理件数直接回収によるDB負荷根絶およびステップ間DB接続回復

## 1. 概要
昨晩の本番定期クローリングパイプラインにおいて、以下3点の重大障害が発生した。
1. **多発するDB件数取得エラー (延べ427回誤アラート):** `run_all_crawlers.py` の親プロセスが子プロセス完了ごとに発行する `get_count_for_job`（`COUNT(*)` クエリ）が ProxySQL hostgroup 0 の接続プールを枯渇させ、クローラー自体は正常終了しているにもかかわらずジョブ失敗アラートが大量発報された。
2. **ステップ間のDB接続遮断エラー (2013 Lost Connection during handshake):** Step 5（お宝物件レコメンド）および Step 6（日次予測診断）の起動時、直前ステップの待機で切断・ハングしたDBコネクションの再利用により通信が断絶した。
3. **マイグレーション未反映不整合:** `0064_reguideinvestment.py` の定義とモデルクラス `ReguideInvestment` の定義に不一致があり、`verify_migrations_sync.py`（CI）で `makemigrations` 差分が検知される状態となっていた。

本改修ではこれらを根絶し、安定した夜間バッチ実行を実現する。

## 2. 目的と価値
- 親プロセスからの重い `COUNT(*)` クエリを全廃し、子プロセスが算出した処理件数を直接回収することでDB負荷を0にする。
- 子プロセスが正常終了（Exit Code 0）していれば、仮に件数回収に失敗してもジョブを「成功」として扱い、誤アラートを完全に排除する。
- 各後続ステップ起動時に既存コネクションを安全にリセット（`close_old_connections()`）し、接続断ハンドシェイクエラーを防ぐ。
- マイグレーションの整合性を完全に回復し、CIおよび自動デプロイでの整合性検査を100%通過させる。

## 3. 機能要件 (FR)
- **FR-001 (メトリクス直接記録):** `main.py` によるクローラー実行時、各ジョブの終了時に処理件数（`detail_cnt`, `skipped_cnt` 等）を `logs/runs/<today>/metrics_<company>_<property_type>.json` にアトミックに書き出すこと。
- **FR-002 (メトリクス直接回収):** `run_all_crawlers.py` は子プロセス完了時、該当メトリクスファイルから件数を取得し、存在する場合はDBへの `get_count_for_job` クエリ発行をスキップすること。
- **FR-003 (フォールバック & 誤失敗抑止):** メトリクスファイルが存在しない場合のみ `get_count_for_job` を実行する。仮に `get_count_for_job` がDBタイムアウト等で失敗しても、子プロセスの exit code が 0 であればジョブを「失敗」と判定せず「DB件数取得スキップ（成功）」として処理すること。
- **FR-004 (ステップ間コネクション明示クローズ):** `send_recommendations.py` および `run_daily_prediction_diagnostics.py` の実行開始直後に Django の `db.connections.close_all()` / `close_old_connections()` を呼び出し、安全に新規接続を確立すること。
- **FR-005 (マイグレーション同期):** `ReguideInvestment` のモデル定義とマイグレーションファイル群の整合性を完全同期させ、`python src/crawler/manage.py makemigrations --check --dry-run` が差分0（Exit code 0）で通過すること。

## 4. 非機能要件 (NFR)
- **NFR-001 (レイテンシ・負荷削減):** 100以上のクローラージョブ完了に伴う `COUNT(*)` クエリ発行数を 0 に削減し、ProxySQL/Cloud SQL への負荷を最小化する。
- **NFR-002 (冪等性・安全性):** メトリクスファイル書き込み・読み込み時の排他制御やI/Oエラーハンドリングを万全にし、ファイル破損時もプロセスがクラッシュしないこと。
- **NFR-003 (SonarCloud / 品質):** 修正コードは SonarCloud 認知複雑度15以下を遵守し、ユニットテストで100%検証すること。

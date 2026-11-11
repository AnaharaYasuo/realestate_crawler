# 割安物件通知（MLパイプライン）の独立スケジュール一本化および一次スクリーニング割安度上限撤廃仕様書 (Issue #1348)

## 1. 概要 (Overview)
1. **二重実行の解消**:
   - これまで、割安物件通知（ML価格推定・お宝物件配信）が午前3時頃と午前5時10分頃の1日2回実施されていた。
   - 1回目 (約 03:00 JST): Cloud Workflows (`realestate-daily-pipeline-prod`) 内の直列ステップ `runMLAndEstimation` による実行。
   - 2回目 (05:10 JST): Issue #1143 で新設された独立 Cloud Scheduler (`realestate-ml-pipeline-daily-prod`) による実行。
   - ユーザー要望「一日一回で良い」に基づき、午前05:10 JST の独立スケジュールに一本化する。

2. **一次スクリーニングにおける割安度上限閾値の撤廃**:
   - 候補物件抽出時の一次スクリーニングにおいて、ディスカウント率（割安度）の上限（`MAX_RECOMMEND_DISCOUNT_PCT` = 60.0% や `MAX_PREDICTION_PRICE_RATIO` = 2.5倍）が設けられていた。
   - 後続にキャピタルゲイン評価・投資スコアおよびAI多面鑑定レポートによる「二次スクリーニング」が存在するため、一次スクリーニング段階で割安度が高すぎる物件を機械的に足切りする必要はない。
   - したがって、一次スクリーニングにおける割安度の上限閾値（ディスカウント率上限・倍率上限）を撤廃し、下限（`MIN_RECOMMEND_DISCOUNT_PCT` = 15.0%）のみを適用する。

3. **毎日の通知物件数の厳選3件への変更**:
   - 各種別ごとの二次スクリーニング通過後の配信枠（`STAGE2_PER_CATEGORY_QUOTA`）について、これまでの5件から「厳選3件」に変更する。
   - 本当に投資価値・割安度が高い上位3件に絞り込んで通知することで、通知の質と視認性を向上させる。

## 2. 要件定義 (Requirements)

1. **Cloud Workflows (`daily_pipeline.yaml`) のクローラー特化化**:
   - `runMLAndEstimation`, `calculateRemainingTime`, `checkMLDeadline`, `resolveMLExecution`, `waitMLCompletion` 等の直列 ML 実行ステップを撤去。
   - `daily_pipeline.yaml` は ProxySQL 起動 -> クローラージョブ実行監視 -> クローラー終了判定 のみを担当する。
   - 不要となった引数・変数（`mlPipelineJob`, `skipTrain`, `mlArgs` 等）を削除し、引数定義・初期化を整理する。

2. **割安物件通知の完全一本化 (05:10 JST)**:
   - 既存の Cloud Scheduler `realestate-ml-pipeline-daily-prod`（`10 20 * * *` UTC = 05:10 JST）を唯一の実行トリガーとして維持する。
   - クローラーの稼働状況（早期完了・長時間実行・部分エラー等）に干渉されることなく、毎朝定時（05:10 JST）に前日・当日深夜までの収集データに基づき価格推定と割安物件配信が行われる。

3. **一次スクリーニングにおける割安度上限閾値の撤廃**:
   - `src/crawler/scripts/ops/send_recommendations.py`:
     - `_evaluate_investment_candidate`: `discount_pct > MAX_RECOMMEND_DISCOUNT_PCT` および `price_ratio > MAX_PREDICTION_PRICE_RATIO` による上限カットを撤廃。`discount_pct >= MIN_RECOMMEND_DISCOUNT_PCT`（15.0%以上）を満たすすべての物件を一次スクリーニング通過とする。
     - `_evaluate_residential_candidate`: `discount_pct > MAX_RECOMMEND_DISCOUNT_PCT` による上限カットを撤廃。`discount_pct >= MIN_RECOMMEND_DISCOUNT_PCT`（15.0%以上）を満たすすべての物件を一次スクリーニング通過とする。
     - 二次スクリーニング（定性評価スコアリング・AI多面鑑定レポート）にて総合判断・選抜を行う。

4. **毎日の通知物件数の各種別3件への縮小**:
   - `src/crawler/scripts/ops/send_recommendations.py`:
     - `STAGE2_PER_CATEGORY_QUOTA = 3` に変更（旧: 5件）。
     - `send_recommendations(quota_per_category=3)` をデフォルトとする。

5. **Terraform 定義およびテストコードの整合**:
   - `terraform/workflows/daily_pipeline.yaml`: ML 関連ステップおよび不要引数の撤去。
   - `terraform/scheduler.tf`: `crawler_daily_trigger` の HTTP ターゲット引数から不要な `mlPipelineJob` を整理。
   - `terraform/workflows.tf`: ワークフロー説明文・コメントの同期。
   - 単体テスト（`test_workflows_orchestration_568.py`, `test_daily_skip_portals_813.py`, `test_selective_crawl_801.py`, `test_send_recommendations.py`, `test_investment_recommendations.py`, `test_issue_1343_investment_recommendation_and_discount.py`）を新仕様に合わせて更新。

## 3. テスト計画
- 単体テスト（pytest）によりワークフロー構文および引数パースの検証。
- 単体テスト（pytest）によりディスカウント率上限撤廃（例: 60%超、70%割安でも一次通過すること）の検証。
- アーキテクチャハーネス検証の実行。

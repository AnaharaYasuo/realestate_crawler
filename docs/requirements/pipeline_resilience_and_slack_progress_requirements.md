# パイプライン耐障害性向上＆ML価格推定・お宝物件通知進捗Slack通知 要件定義書

## 1. 概要・ユーザーストーリー
* **ユーザーとして**: クローリングパイプラインの運用者・投資物件探索者として
* **要求**: クローリング処理が一部または全体で異常終了した場合でも、データ検証・価格推定・お宝物件Slack通知を確実に完遂させ、かつクローリングと同様に価格推定とお宝物件通知の進捗をSlackでリアルタイムに把握したい
* **価値**: 一部のクローラーの不調やタイムアウトがあっても、正常に取得された物件や蓄積された未評価物件の価格推定および優良物件通知を漏れなく受け取ることができ、運用の透明性と信頼性を最大化する

## 2. 背景と課題
1. **クローリング異常終了時のパイプライン中断**:
   - `run_pipeline.py` において、`_run_crawler_step` が例外（子プロセスのエラーやタイムアウトなど）を発生させた場合、パイプライン全体が即座に異常終了（`sys.exit(1)`）し、後続の価格推定（`run_bulk_ml_evaluation.py`）やお宝物件通知（`send_recommendations.py`）が一切実行されなかった。
2. **価格推定・お宝物件通知の進捗不透明性**:
   - クローリング（`run_all_crawlers.py`）は開始・各ジョブ結果・サマリーをSlackに通知しているのに対し、バルク価格推定およびお宝物件通知はコンソールログのみで、Slack上に進捗や完了サマリーが一切通知されていなかった。

## 3. 機能要件 (Functional Requirements)
* **FR-001: クローリング異常時の耐障害性パイプライン継続 (Resilient Pipeline Continuation)**
  - クローリング（Step 1/6: `run_all_crawlers.py` または分散タスク待機）が非ゼロ終了コードや例外を発生させた場合でも、パイプラインは即座に停止せず、警告ログおよび障害記録を残した上で後続のデータ検証、価格推定（Step 4/6）、お宝物件Slack通知（Step 5/6）を実行すること。
* **FR-002: 後続ステップのエラー隔離 (Step Error Isolation)**
  - 後続パイプラインの各ステップ（データ検証、ML再学習等）で個別にエラーが発生した場合でも、エラーを隔離・記録し、可能な限り後続の「バルク価格推定」および「お宝物件Slack通知」を継続実行すること。
* **FR-003: バルク価格推定のSlack進捗・結果通知 (Bulk ML Evaluation Slack Progress)**
  - `run_bulk_ml_evaluation.py` の実行開始時に開始通知をSlack（`property_alert` チャンネル）へ送信すること。
  - 各モデル（または一定バッチ）の評価完了時に進捗通知（処理件数、累計件数）をSlackへ送信すること。
  - 処理完了時に全体サマリー（評価完了件数、スキップ件数、所要時間、失敗モデル一覧）をSlackへ送信すること。
* **FR-004: お宝物件スクリーニングのSlack進捗・結果通知 (Recommendation Slack Progress)**
  - `send_recommendations.py` の実行開始時に開始通知をSlack（`property_alert` チャンネル）へ送信すること。
  - 候補抽出完了時（検出件数、配信対象件数）および配信完了時（配信成功件数）のサマリーをSlack（`property_alert` チャンネル）へ送信すること。
  - 配信対象が0件の場合も、未配信ではなく正常に0件であった事実を明示通知すること。

* **FR-005: Cloud Workflows におけるクローラー障害時のMLパイプライン自動継続 (Cloud Workflows Orchestration Resilience)**
  - Cloud Workflows (`daily_pipeline.yaml`) において、クローラージョブ（`crawlerJob`）の監視ステップで障害（`JobExecutionFailed` や `JobExecutionTimeout`）が発生した場合でも、即座に例外再送出（ProxySQL停止）せずエラーを記録・捕捉した上で、残余時間（`remainingMLTimeout`）が確保されている限り、後続のML・価格推定ジョブ（`mlPipelineJob`）を確実に実行すること。
  - MLパイプライン完了後にクローラーまたはMLジョブの失敗を評価し、いずれかで失敗があった場合は最終的にワークフロー全体としてエラー状態を報告すること。
* **FR-006: Cloud Workflows における子ジョブ消失・取得エラー時の高速失敗 (Fast-Fail on Missing Execution)**
  - Cloud Workflows (`daily_pipeline.yaml`, `recrawl_anomalies_pipeline.yaml`) の `monitorJobExecution` において、対象 Cloud Run Job Execution が削除・消失・404 Not Found または連続取得失敗した場合、タイムアウト（9〜11時間）まで無限リトライせず、上限試行回数（3回）を超えた時点で直ちに `JobExecutionNotFound` エラーを発生させて Fast-Fail すること。
  - これにより親ワークフローのゾンビ化を根絶し、`except` ブロックで ProxySQL 等のリソース停止が遅滞なく実行されること。
* **FR-007: 死活検証（URL verification）のワークフローパラメータ化とデフォルトスキップ (Configurable URL Verification)**
  - Cloud Workflows (`daily_pipeline.yaml`) において、死活検証（URL verification / 約24分所要）の実施要否をワークフロー実行時パラメータ（`skipUrlCheck` / デフォルト `true`、または `enableUrlCheck` / デフォルト `false`）で制御可能とすること。
  - デフォルトおよび Cloud Scheduler による日次定期スケジュール実行では死活検証を実施しない（スキップする）設定とし、通常パイプライン実行時間を短縮すること。明示的に実行指定された場合のみ死活検証を有効化すること。
  - `run_pipeline.py` および `run_ml_pipeline.py` に `--skip-url-check` オプションを安全に伝搬すること。

## 4. 非機能要件 (Non-Functional Requirements)
* **NFR-001: 既存クローリングアラートおよび個別通知チャネルの保全**
  - 個別のお宝物件カード通知（`goodproperty-*` チャンネル）の仕様・レイアウトはそのまま維持すること。
  - 進捗通知はクローリングサマリーと同じ `property_alert` チャンネルに集約し、通知スパムにならないよう適切な粒度（モデル完了単位・サマリー単位）に保つこと。
* **NFR-002: タイムアウトおよびリソース停止（Graceful Teardown）の厳守**
  - エラー継続時にもパイプライン全体のタイムアウト監視（Cloud Run期限前安全停止）およびProxySQL等の停止処理が確実に実行されること。

## 5. アクセプタンスクライテリア (受入基準)
* [ ] 【基準1】クローリング処理（Step 1/6）が異常終了（exit code != 0 や例外）した場合でも、後続の価格推定（Step 4/6）とお宝物件通知（Step 5/6）がスキップされず確実に実行されること。
* [ ] 【基準2】バルク価格推定（`run_bulk_ml_evaluation.py`）の開始・進捗・完了サマリーがSlack（`property_alert`）に通知されること。
* [ ] 【基準3】お宝物件配信（`send_recommendations.py`）の開始・候補抽出状況・完了サマリーがSlack（`property_alert`）に通知されること。
* [ ] 【基準4】後続ステップ（ML再学習等）でエラーが発生した場合でも、隔離されて価格推定とお宝物件通知が継続実行されること。
* [ ] 【基準5】Cloud Workflows (`daily_pipeline.yaml`) において、クローラージョブが一部または全体で失敗しても後続のML・価格推定ジョブが確実に実行され、ProxySQLが正しくクリーンアップされること。
* [ ] 【基準6】Cloud Workflows (`daily_pipeline.yaml`, `recrawl_anomalies_pipeline.yaml`) において、監視対象 Execution が消失（404）または連続取得失敗した場合に `JobExecutionNotFound` で Fast-Fail して ProxySQL が停止されること。
* [ ] 【基準7】ユニットテストおよび統合テストで上記動作が検証され、100% 成功すること。
* [ ] 【基準8】死活検証がワークフローパラメータで実施制御可能であり、デフォルトおよび Cloud Scheduler 日次実行でスキップ（非実施）されること。

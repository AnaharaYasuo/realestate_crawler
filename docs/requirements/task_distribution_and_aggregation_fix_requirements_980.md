# クローラータスク分散最適化および集約レポート母数是正 要件定義書 (Issue #980)

## 1. 概要
日次スケジュール実行におけるCloud Run Jobsタスクアレイ（8タスク並列）において、一部タスクが未完了（タイムアウト等）となり、多数の未実行ジョブが発生していた問題を解消する。また、全ジョブ集約レポートにおいてハードコードされていたジョブ総数（89件）を実態（104件）および動的フィルタリングに即した正確な値へと是正する。

## 2. 課題と原因分析
1. **Task 4 への過度な負荷集中**:
   - 従来の `_assign_8_task_index` では、大手5社・信託3社・投資用・ポータル以外のすべてのジョブ（信託居住用＋中堅仲介＋電鉄系＋ハウスメーカー系）が Task 4 に割り振られており、全104ジョブ中 **60ジョブ** が1つのコンテナに集中していた。
   - このため Task 4 の実行時間が極端に長くなり、タイムアウトまたは未完走を誘発していた。
2. **集約レポートのハードコード乖離**:
   - `run_ml_pipeline.py` および `pipeline_coordinator.py` で `total_jobs = 89` とハードコードされていた。
   - 新規パーサー（健美家、リガイド等）の追加に伴い実ジョブ数は 104 件に増加しており、母数定義が乖離していた。
3. **未実行ジョブの大量発生**:
   - 長時間稼働する Task 4 が完了しないまま ML Pipeline Job が集約を実行したため、完了済みの少数タスク（16ジョブ等）のみが集計され、残りが未実行として報告されていた。

## 3. 要件一覧
* **REQ-980-01 (タスク負荷の平準化)**:
  - 8タスク分散（`_assign_8_task_index`）を再設計し、Task 4 の集中を各タスクへ平準化する。
    - **Task 0**: 大手5社 mansion (5) + daikyo mansion (1) = 6 jobs
    - **Task 1**: 大手5社 kodate (5) + daikyo kodate (1) + daikyo tochi (1) = 7 jobs
    - **Task 2**: 大手5社 tochi (5) + 信託3社居住用 (9) = 14 jobs
    - **Task 3**: 投資用・事業用全般 (18 jobs)
    - **Task 4**: 電鉄・ハウスメーカー系 kodate & tochi (26 jobs)
    - **Task 5**: homes 全種別 (4 jobs)
    - **Task 6**: athome mansion (1) + 中堅仲介全種別 (12 jobs) = 13 jobs
    - **Task 7**: athome その他 (3) + 電鉄・ハウスメーカー系 mansion (13) = 16 jobs
  - 各タスクの担当ジョブ数を 4〜26 件の範囲に収め、最大タスクでも従来の半数以下に抑制する。
* **REQ-980-02 (集約レポートの総ジョブ数動的化)**:
  - `pipeline_coordinator.aggregate_task_array_reports` の `total_jobs` 既定値を `89` から `len(CRAWL_JOBS)`（104）に変更する。
  - `run_ml_pipeline.py` において、`aggregate_task_array_reports(records, total_jobs=total_jobs)` を呼び出す際、`len(CRAWL_JOBS)` または適用されたフィルタ（`--skip-portals`, `--skip-uncrawled` 等）を反映したジョブ数を自動計算して渡す。
* **REQ-980-03 (リグレッション防止・テスト網羅)**:
  - 単体テスト（`test_crawler_ml_split_549.py`, `test_crawl_speed_and_cost_optimization_851.py` 等）を最新のタスク分散定義および動的ジョブ数に合わせて同期・更新する。

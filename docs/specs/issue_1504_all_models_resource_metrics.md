# Issue #1504 要件定義・仕様設計書
## ML再学習 全物件種別（all）サポート & リアルタイムCPU/メモリ使用量テレメトリ機能

### 1. 目的・背景
- **背景**:
  - `run_ml_pipeline.py` における ML 再学習（Step 2/5）は、曜日ローテーションまたは `--property-type <ptype>` による単一物件種別（tochi, mansion, kodate, apartment）のみを受け付ける設計となっていた。
  - ユーザー要求として「全てのモデルでテストして欲しい（全物件種別の再学習を一括実行）」「メモリ使用量、CPU利用率も把握して（Cloud Run 2GiB RAM コンテナ環境下でのリソース消費を可視化）」が提示された。
  - 過去の履歴調査において、全件学習時に `exit code -9`（OOM / Out of Memory）が発生した形跡があり、各モデル学習ごとのメモリ・CPU消費の定量的観測および全種別順次学習の安全な実行制御が急務である。

### 2. 機能要件 (Requirements)
1. **`run_ml_pipeline.py` での `--property-type all` サポート**:
   - `--property-type` の choices に `"all"` を追加する。
   - `--property-type all` 指定時、`train.py` に対し全対象種別（`mansion`, `kodate`, `apartment`, `tochi`）を引数として渡す（`--property-type mansion --property-type kodate ...` または引数省略）。
2. **プロセス内部リアルタイム CPU・メモリ計測 & 構造化ログ記録**:
   - `package.ml.training.pipeline` の `train_property_type` および `run_training` において、`newrelic_helper` の堅牢なフォールバック付きリソース取得機構（`_read_host_memory_fallback`, `_read_cpu_metrics`）を活用。
   - モデル学習前（初期メモリ）、各ステージ学習中、学習完了後（ピークメモリ、解放後メモリ、CPU利用率）を計測。
   - `BatchMetrics` のカスタムセクションおよびログ出力に以下を明示：
     - 開始時 RSS (MB) / 終了時 RSS (MB) / 推定 Peak RAM (MB)
     - プロセス CPU 利用率 (%) / システム CPU 利用率 (%)
3. **安全なメモリ解放 (Garbage Collection)**:
   - 各種別の学習終了ごとに `del` および `gc.collect()` を確実に呼び出し、次種別の学習前にメモリフットプリントを最小化。

### 3. 影響範囲 (Blast Radius)
- `src/crawler/scripts/ops/run_ml_pipeline.py`: `--property-type` 引数処理と `train_cmd` 構築ロジック。
- `src/crawler/package/ml/training/pipeline.py`: リソース計測ヘルパーの呼び出しとログバナー表示の拡張。
- `tests/test_ml_pipeline.py` / `tests/test_run_ml_pipeline.py`: 引数検証・テストケース追加。
- `docs/4_valuation_and_ml/ml_model_specifications.md`: ML再学習仕様の更新。

# MLモデル種別単位ローテーション再学習・直列化・メモリ最適化仕様書 (Issue #1482)

## 1. 概要 (Overview)
日曜定例のML再学習発火時に、全物件種別（mansion, kodate, apartment, tochi）の全モデル（LightGBM, XGBoost, CatBoost, RandomForest）を一度に学習しようとしたため、Cloud Run Jobs のメモリ上限（2GiB）を超過して Linux Kernel OOM Killer によりプロセスが SIGKILL (-9) 終了した。
これにより、後続のバルク推論とお宝物件通知が中断された。

本改修では以下の4点を実装し、再学習の負荷・メモリ消費を大幅に削減し、安定した日次パイプライン運用を実現する。
1. **種別引数の新設 (`--property-type` / `ML_TRAIN_PROPERTY_TYPES`)**: 単一種別（あるいは指定された複数種別）のみを個別に学習可能とする。
2. **曜日分散ローテーション**: 日次パイプラインの週次再学習発火時に、全種別ではなく曜日ごとに1種別ずつローテーション学習する。
   - 木曜: `mansion`
   - 金曜: `kodate`
   - 土曜: `apartment`
   - 日曜: `tochi`
   - 月〜水: 再学習スキップ（推論・配信のみ）
3. **既存モデルメタデータ保護と個別マージ保存**:
   - `save_metadata` において、学習対象外の種別の既存モデル・重み（`ensemble_weights.joblib`, `smearing_factors.joblib` など）を上書き削除せず、既存ファイルを読み込んでマージ保存する。
4. **学習プロセスの直列化および内部メモリ最適化**:
   - アルゴリズム間での不要オブジェクトの明示的 `del` と `gc.collect()`。
   - First Stage と Second Stage の直列化とメモリ解放。
   - スレッド数 `ML_NUM_THREADS` のデフォルト上限（コンテナリソースに合わせた適切なスレッド管理）。

---

## 2. 外部設計 (External Specification)

### 2.1 CLI 引数および環境変数
- `src/crawler/package/ml/train.py`:
  - `--property-type` (`-p`): 学習対象の物件種別を指定（例: `mansion`, `kodate`, `apartment`, `tochi`）。カンマ区切りまたは複数回指定可能。
  - 指定がない場合は環境変数 `ML_TRAIN_PROPERTY_TYPES` を参照。環境変数も未設定の場合は従来互換として全種別（`mansion,kodate,apartment,tochi`）を対象とする。
- `src/crawler/scripts/ops/run_ml_pipeline.py`:
  - `--property-type`: `train.py` に引き渡す対象物件種別。
  - 自動スケジュール判定ロジック:
    - 曜日分散（木曜: mansion, 金曜: kodate, 土曜: apartment, 日曜: tochi）。

---

## 3. 内部設計 (Internal Specification)

### 3.1 `package.ml.training.pipeline`
- `run_training(target_types: list[str] | None = None, allow_dummy_fallback: bool | None = None) -> None`:
  - `target_types` で指定された種別のみループして学習を実行。
  - ループごとにメモリを `gc.collect()`。

### 3.2 `package.ml.training.regressors` (Issue #1672)
- `_get_ml_thread_limit()`: 環境変数 `ML_NUM_THREADS` 未指定時のデフォルトスレッド数を `2` に制限し、2GiB RAM 環境でのメモリスパイクを抑制する。
- `RandomForestRegressor`: joblib によるメモリ複製での OOM を防ぐため、`n_jobs=1` に固定する。

### 3.2 `package.ml.training.artifacts`
- `save_metadata`:
  - 既存の `ensemble_weights.joblib`, `smearing_factors.joblib`, `location_encoders.joblib`, `p10_conformal.joblib` が存在する場合、読み込んで今回学習した種別のキーのみ更新・マージして保存する。

### 3.3 `package.ml.training.ensemble`
- `train_and_compare`:
  - 各アルゴリズム（`lgb`, `xgb`, `cat`, `rf`）の学習完了ごとに `gc.collect()` を呼出。

---

## 4. テスト計画 (Testing Plan)
- `tests/unit/test_ml_training_rotation_1482.py`:
  - `--property-type` 指定時に単一種別のみが学習されること。
  - 既存のメタデータが保持され、学習種別のみがマージ更新されること。
  - 曜日ローテーション判定関数が木/金/土/日に正しくマッピングされること。
- アーキテクチャハーネス検証 (`test_architecture_harness.py`) の全件合格。

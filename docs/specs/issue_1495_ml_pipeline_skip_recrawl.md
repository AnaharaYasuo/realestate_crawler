# Issue #1495 仕様書: ML パイプラインにおける異常再取得スキップ (--skip-recrawl) および明示的物件種別 (--property-type) 対応

## 1. 背景・目的
`src/crawler/scripts/ops/run_ml_pipeline.py` において、以下の2点の課題が存在していた。
1. Step 0.9 (`recrawl_anomalies.py`) が無条件で呼び出され、ML再学習や価格推定のみを迅速に実行・検証したい場合にも 300〜500件の遅延再スクレイピングが強制実行されていた。
2. `--property-type` 引数がパイプライン CLI の最上位パーサーに定義されておらず、手動で特定モデル（土地など）の単一再学習を指示した際に `unrecognized arguments: --property-type` で異常終了していた。

## 2. 変更仕様
1. **`--skip-recrawl` オプションの追加**:
   - `argparse` に `--skip-recrawl` を追加。
   - 環境変数 `ML_PIPELINE_SKIP_RECRAWL=true` にも対応。
   - 指定時は Step 0.9 をスキップログ出力してパスする。
2. **`--property-type` オプションの追加**:
   - `argparse` に `--property-type` (choices: `['tochi', 'mansion', 'kodate', 'investmentapartment', 'investmentkodate']`) を追加。
   - 指定時は曜日ローテーション判定をオーバーライドし、指定された物件種別で `train.py --property-type <type>` を実行する。未指定時は従来どおり曜日ローテーションに従う。

## 3. テスト計画
- ユニットテスト `test_run_ml_pipeline_options_1495.py`:
  - `--skip-recrawl` 時に Step 0.9 がスキップされることの検証。
  - `--property-type tochi` が指定された際に `train.py` にそのまま渡されることの検証。

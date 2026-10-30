# 仕様書: Issue #1116 投資用物件推薦配信における異常予測価格ガード追加および旧レコード整合性修復

## 1. 概要
`フローラ・国分寺ＡＢ`（売出価格3,560万円に対し理論予測価格174,133万円）など、Slack通知されたお宝物件の一部で理論予測価格が売出価格の数十倍〜数百倍に達する異常値が検出された。
本仕様変更では、以下の恒久対策を実施する：
1. `send_recommendations.py` 内の投資用物件判定ロジック（`_evaluate_investment_candidate`）における理論予測価格の異常値ガード（2-sigma / 安全弁）の導入
2. 既存DB内に残留している乖離異常レコードの最新モデルによる再計算修復

## 2. 変更仕様

### 2.1 `send_recommendations.py` の安全弁ガード
- `_evaluate_investment_candidate(eval_rec, prop=None)` において：
  - 投資スコア (`total_investment_score` または `investment_score`) が70点以上の場合でも、`prop` が提供されている場合は理論予測価格 (`pred_price`) と正規化売出価格 (`asking_price_man`) の乖離率を検証する。
  - `pred_price` が `asking_price_man` の 3.0倍（+200%）を超える、あるいは 0.33倍（約-67%）未満となるような極端な乖離が存在する場合、2-sigma異常値・モデル不整合とみなして警告ログを出力し推薦候補から除外（スキップ）する。
  - これにより、万が一DB内に異常な予測価格が残存していた場合でも、ユーザーに異常な推定価格がSlack配信されることを100%防止する。

### 2.2 既存DB異常レコードの再計算・修復スクリプト
- `scripts/maintenance/repair_anomalous_predictions.py` を作成：
  - `PropertyEvaluation` 内で `first_stage_predicted_price` が `asking_price_man` の 3.0倍超または0.33倍未満となっているレコードを抽出。
  - 最新の学習済みアンサンブルモデル（`bulk_predict_first_stage`）を用いて再推論し、適正な理論予測価格に更新する。
  - 投資用物件の場合は投資スコア（`evaluate_investment_property`）も再計算して整合性を確保する。

## 3. テスト計画
- `test_investment_recommendations.py` に、極端な予測価格乖離（例: 3560万に対して174133万）を持つ投資物件がレコメンド対象から安全に除外されることを検証するユニットテストを追加。
- `test_repair_anomalous_predictions.py` にて修復ロジックの動作検証テストを追加。

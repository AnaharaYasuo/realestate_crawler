# Issue #1399: 下限予測価格P10による一次スクリーニング判定の厳格化 仕様書

## 1. 概要
機械学習モデルの予測において、下限予測価格（$P_{10}$、LightGBM Quantile Regression × Split Conformal Prediction）の予測精度が高いことが確認された。
これに伴い、一次スクリーニング合格フラグ（`is_first_stage_passed`）の判定ロジックにおいて、点予測値（平均予測値 $\hat{y}$）だけでなく、不確実性を織り込んだ保守的下限予測価格 $P_{10}$（`first_stage_p10_price` / `p10_stage1`）を最優先判定基準として採用する。

## 2. 背景・目的
- **背景**:
  従来の一次スクリーニング（`build_or_update_eval_record`）では、平均理論予測値 $P_{\text{stage1}}$ が売出価格以上（$P_{\text{stage1}} \ge P_{\text{asking}}$）であれば一次合格としていた。
  しかし、分散や不確実性が大きい外れ値・スペック欠損物件において、平均予測値が高めに出てしまい一次合格と判定されるケースが存在した。
  現在システムには高精度な下限予測価格 $P_{10}$（90%コンフォーマル被覆率保証）が算出・提供されている（Issue #1380）。
- **目的**:
  一次スクリーニング判定を保守的かつ高精度な下限予測価格 $P_{10}$ 基準へと厳格化し、スペック欠損や過大予測ノイズによる「偽のお宝（False Positive）」を一次スクリーニング段階で確実に遮断する。

## 3. 詳細仕様

### 3.1 一次スクリーニング合格判定（`is_first_stage_passed`）
評価レコード生成処理（`build_or_update_eval_record` 等）における一次合格判定ロジックを以下のように改修する：

```python
# 有効なP10値が存在する場合 (p10_dec > 0)
# 判定基準価格を p10_dec（万円単位）とする
# P10値が存在しない／未算出の場合、後方互換性のため従来通り price_stage1 を基準とする
benchmark_price = float(p10_dec) if p10_dec is not None and p10_dec > 0 else float(price_stage1)
is_passed = bool(benchmark_price > 0 and asking_price > 0 and benchmark_price >= asking_price)
```

1. **優先評価**:
   - `p10_stage1`（および有界化された `p10_dec`）が有効値（$> 0$）として存在する場合、売出価格（`asking_price`）との比較には $P_{10}$ を使用する：
     $$\text{is\_first\_stage\_passed} = (P_{10} \ge P_{\text{asking}})$$
2. **フォールバック（後方互換性）**:
   - $P_{10}$ が `None` または `<= 0` の場合（専用モデル未ロード時やテストモック環境等）、従来通りの点予測値 $P_{\text{stage1}}$ を判定基準としてフォールバックする：
     $$\text{is\_first\_stage\_passed} = (P_{\text{stage1}} \ge P_{\text{asking}})$$
3. **境界値・ゼロ除外**:
   - `asking_price <= 0` または `benchmark_price <= 0` の場合は従来通り `False` とする。

### 3.2 影響範囲と適用箇所
1. `src/crawler/package/ml/evaluation/record_builder.py`:
   - `build_or_update_eval_record` 内の判定ロジック改修。
2. `src/crawler/package/api/api.py`:
   - 単体物件評価等のリアルタイムAPI・クローラー内インライン判定ロジックが存在する場合、同様の基準を適用または統合。
3. `docs/4_valuation_and_ml/ml_model_specifications.md`:
   - §16.1 に一次スクリーニングでのP10採用仕様を明記。
4. 単体テスト:
   - `src/crawler/tests/unit/test_issue_1399_p10_first_stage_screening.py` を新規作成し、P10基準での一次合否判定、P10未設定時のフォールバック動作、境界値（P10 < asking <= price_stage1）での不合格化を厳密に検証する。

## 4. 移行・互換性
- DBスキーマの変更は不要（既存の `first_stage_p10_price` および `is_first_stage_passed` を利用）。
- 既存のモデルファイルやバッチ評価パイプライン（`runner.py`）は既に `p10_prices` を `save_chunk` に渡しているため、追加の引数変更なく即座に全自動で適用される。

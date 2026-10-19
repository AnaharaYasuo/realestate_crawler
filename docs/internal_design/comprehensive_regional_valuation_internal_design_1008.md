# 内部設計書: 都市部・地方の駅アクセス感応度・地価フォールバック・広大地規模減退の包括的適正化 (Issue #1008)

## 1. 概要
都市部と地方における金額予測の精度格差を是正するため、以下の4つの根本要因を包括的に改修する。
1. 駅徒歩評価の逆転現象解消 (`calculate_effective_walk_min`)
2. 郡・町・村における都道府県平均地価への不当フォールバック防止 (`_get_land_price_stats`)
3. 広大地残余土地価値の規模減退率適用 (`calculate_tochi_appraisal_factors`)
4. 駅力（乗降客数）および車社会環境に応じたアクセス感応度の適正化 (`calculate_regional_sensitivity_features`)

## 2. 詳細仕様

### 2.1 駅徒歩評価の逆転現象解消 (`package/ml/features/reference_data.py`)
- **問題**: `walk_min_penalty_scale = max(0.4, min(1.0, 0.4 + 0.6 * (pop_density / 4000.0)))` により、低人口密度地域で `walk_min` が 0.4 倍（20分 ➔ 8分）に圧縮され、地方駅遠物件が過大評価されていた。
- **仕様**: 徒歩時間は実測値を歪めず、バス利用時の換算補正のみに限定。`pop_density` による無条件な徒歩分数圧縮を廃止。

### 2.2 郡・町・村における地価フォールバックの是正 (`package/ml/features/reference_data.py`)
- **問題**: 郡部・町・村に個別地価レコードがない場合、県平均（大都市高額地を含む）にフォールバックして地価が数十万円/㎡に跳ね上がっていた。
- **仕様**: 住所（`address2`）に「郡」「町」「村」が含まれる場合、都道府県平均へのフォールバックを行わず、`_get_nationwide_base_land_price` の町村基準値（県基準地価の0.45倍）を採用する。

### 2.3 残余地価（`residual_land_value`）の規模減退率適用 (`package/ml/features/appraisal.py`)
- **問題**: 土地面積が数千㎡に達する広大地でも、平米単価がそのまま乗算され、数十億円の非現実的評価額が算出されていた。
- **仕様**: 国税庁の広大地評価基準に準拠した `scale_discount`（規模減退率: $A^{-0.08}$ 等）を `residual_land_value` の算出式に乗算する。

### 2.4 駅力・車社会感応度の適正化 (`package/ml/features/reference_data.py`)
- `walk_min_elasticity` および `effective_station_distance` の計算において、地方の低乗降客数駅に対する過度な駅近評価を抑制し、都市部主要駅との勾配差を正確にモデリングする。

## 3. テスト計画 (TDD)
- `tests/unit/test_comprehensive_regional_valuation_1008.py`:
  - 湯河原町などの町村で県平均（80万円等）に跳ね上がらず、町村地価（3〜4万円等）に収まること。
  - 1000㎡超の広大地で `residual_land_value` に `scale_discount` が乗算され適正化されること。
  - 地方駅遠物件（徒歩20分）で `effective_walk_min` が 8 分などに圧縮されず、20 分以上として維持されること。

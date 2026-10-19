# 内部設計書: 都市部・地方の感応度差を調整する交互作用特徴量設計 (Issue #1003)

## 1. 概要
`package.ml.features` 配下に都市部・地方の感応度差を変調させる交互作用特徴量を設計・実装する。

## 2. 追加特徴量定義 (`FEATURE_SETS`)

全種別（`mansion`, `kodate`, `apartment`）の `first` および `second` 特徴量セットに以下の 4 特徴量を追加する。

| 特徴量名 | 型 | 定義式 | 物理的・経済的意義 |
| :--- | :--- | :--- | :--- |
| `walk_min_elasticity` | float32 | `walk_min * log1p(pop_density)` | 駅徒歩の地域弾力性。人口密度の高い都市部ほど徒歩増に伴う減価勾配を急峻化。 |
| `effective_station_distance` | float32 | `walk_min / log10(max(passenger_volume, 100))` | 駅集客力連動徒歩距離。巨大ターミナル駅徒歩とローカル線無人駅徒歩の価値差を変調。 |
| `chikunen_depreciation_resistance` | float32 | `chikunen * (1.0 - land_value_share)` | 築年数減価耐性。立地（土地）価値比率が高いほど、築古化による減価カーブを平坦化。 |
| `area_value_intensity` | float32 | `area * log1p(average_land_price)` | 面積価値強度。高地価（都市部）では面積増が資産総額に大きく寄与する非線形性を表現。 |

### 補助計算: `land_value_share`（土地価値シェア）
```python
# 潜在的土地価値と建物再調達原価の比率
potential_land_val = tochi_area * (average_land_price / 10000.0) if property_type != 'mansion' else (area * 0.2) * (average_land_price / 10000.0)
potential_building_val = tatemono_area * cost_unit if property_type != 'mansion' else area * cost_unit
total_potential_val = potential_land_val + potential_building_val
land_value_share = potential_land_val / total_potential_val if total_potential_val > 0 else 0.5
```

## 3. 影響範囲 (Blast Radius)
- `package/ml/features/feature_sets.py`: 特徴量名リストの拡張
- `package/ml/features/builder.py`: 4特徴量の算出および辞書への格納
- `package/ml/inference/predictor.py`: `prepare_df_features` による整列・キャスト（実装変更不要、自動対応）

# 機械学習・価格推定・お宝判定ルール (src/crawler/package/ml/AGENTS.md)

本ディレクトリ（`src/crawler/package/ml/`）配下の特徴量生成・学習・推論・評価コードを実装・改修する際は、以下の MLOps 不変条件を厳守すること。

## 1. 空間・建物リークの完全防止（Spatial / Building `GroupKFold` 必須）
- 同一マンション（同一建物・同一所在地）や同一町丁目の物件が Train Fold と Validation Fold に跨ってリークするランダム `KFold` の使用を禁止する。
- [`training/ensemble.py`](training/ensemble.py) の交差検証では、必ず建物識別子または所在地グループに基づく `GroupKFold` を使用し、未知の物件に対する真の汎化性能（OOF MAPE / MdAPE）を計測すること。

## 2. サンプル重み（Time-Decay Weights）の一貫適用
- 直近の市場トレンドを重視する時間減衰重み（`calculate_time_decay_weights`）は、ベースモデル（LightGBM / XGBoost / CatBoost）の `fit` 時だけでなく、**OOF アンサンブル重み最適化** および **Duan's Smearing 補正係数の算出** にも一貫して適用すること。

## 3. マイクロロケーション特徴量（OOF Target Encoding & Spatial Comps）
- 市区町村単位の粗い集約だけでなく、町丁目（Chome）および駅×徒歩分数帯の Out-of-Fold (OOF) Target Encoding ならびに近傍・同一建物の類似取引単価アンカー（Spatial Comps）をリークなしで算出すること。

## 4. 予測不確実性（下限予測値 $P_{10}$）に基づくリスク調整後お宝判定
- お宝物件（割安物件）のスクリーニングにおいて、点予測（平均予測値 $\hat{y}$）との単純乖離率のみで判定してはならない。
- 予測モデルの不確実性（Fold間予測分散または分位点予測による 10% 下限予測値 $P_{10}$）を算出し、**保守的な下限予測値 $P_{10}$ に対してもなお割安である物件（Risk-Adjusted Bargain Score）** を優先抽出することで、スペック欠損や外れ値による誤報（False Positive）を排除すること。

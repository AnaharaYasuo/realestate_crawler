# 仕様書: Issue #1087 投資用物件（区分マンション・一棟・戸建等）のお宝物件レコメンド抽出＆配信対応

## 1. 背景と課題
ユーザーより「レコメンドって投資用物件も含めて欲しい」との要求を受けた。
現在のお宝物件レコメンド機能（`send_recommendations.py`）では、候補抽出関数 `_fetch_recommendation_candidates()` が未通知の全物件（主にマンション、戸建て、土地）を走査するが、総数が多いため ID 上位（最新クロール）のみで枠が埋まり、投資用物件の比率が極端に低くなっていた。
また、投資用物件の評価関数 `_evaluate_investment_candidate()` において、しきい値 `score >= 80.0` の判定や、理論予測価格（`first_stage_predicted_price` / `second_stage_predicted_price`）が存在する場合の割安度判定が投資用物件に適用されていなかった。

## 2. 要件定義 (Requirements)
1. **種別ごとの候補抽出枠（Type-Balanced Fetch）**:
   - `_fetch_recommendation_candidates()` において、住居系（`mansion`, `kodate`, `tochi`）だけでなく、投資用物件（`investment`, `investmentapartment`, `apartment`, `investmentkodate`, `invest_kodate`, `invest_apartment` 等）も一定件数（各最大 500 件等）確実に候補リストへ含める。
2. **投資用物件のハイブリッド評価（スコア ＆ 割安度）**:
   - 投資用物件判定において、`total_investment_score` または `investment_score` が 70点以上（または基準以上）の場合に優良投資物件として検出。
   - さらに、理論予測価格（`first_stage_predicted_price` / `second_stage_predicted_price`）が存在し、売出価格より割安（`discount_pct >= 20.0%`、外れ値ガード付き）な場合も「割安＆収益物件」として検出する。
3. **配信クォータの種別バランス（Quota Balancing）**:
   - 全体配信枠（15〜20件）の中で、投資用物件（区分・一棟・戸建て）が必ず複数件（例: 最低3〜5件）選定されるように配分を保証する。
4. **Slack 通知フォーマットの最適化**:
   - 投資用物件チャンネル（`goodproperty-invest-apartment`, `goodproperty-invest-kodate`）へ、利回り・キャッシュフロー・DSCR・割安度を含めて正しく配信。

## 3. 実装方針
- 対象ファイル: `src/crawler/scripts/ops/send_recommendations.py`
- 単体テスト追加: `tests/test_send_recommendations.py` または `tests/test_investment_recommendations.py`
- 既存のテストスイートおよび全件リグレッションテストへの適合。

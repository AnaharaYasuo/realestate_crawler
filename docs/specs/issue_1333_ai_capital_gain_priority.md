# 仕様書: Issue #1333 ML理論価格アンカリング排除とAI直接目利きによるキャピタルゲイン最優先選抜

## 1. 概要と背景
従来の二次スクリーニング選抜およびAI定性レポート生成においては、以下のような構造的課題が存在していた：
1. **AIへのML理論価格アンカリング**:
   AIプロンプト作成時に関数引数およびプロンプト内部で `pred_price`（ML理論価格）やその乖離を注入・参照していたため、MLの統計的バイアスや推論エラーにAIが引きずられ、客観的なAI目利き・調査を行う意義が損なわれていた。
2. **二次選抜スコアのML理論価格依存**:
   `_rank_by_qualitative_score` において、`base_rating_score`（定性レーティング）に `ml_priority`（ML理論価格ディスカウント率由来の優先度）を直接加算してソートしていた。そのため、ML理論価格が大きく歪んでいる物件が優先され、真のキャピタルゲイン（潜在売却益・地価上昇・容積余力・相場歪み）が反映されにくかった。

本仕様では、これらを抜本的に是正し、**客観的生データ（立地・駅力・ハザード・地価公示・成約事例・容積余力・修繕状態等）のみからAIが独自に適正相場とキャピタルゲインポテンシャルを査定し、二次選抜ではAIのキャピタルゲイン評価を最優先する**アーキテクチャへと刷新する。

---

## 2. 要件定義

### 2.1 AIレポート生成（`report_generator.py`）
- `generate_professional_and_danchou_report` から `pred_price` の引数・参照を完全撤廃。
- プロンプトからML理論価格およびその乖離率の文言を排除。
- AIに対し、売出価格・積算価格・地価公示・成約坪単価・容積余力・人口動態・駅乗降客数などの客観データから、以下の項目を直接査定・出力させる：
  - `capital_gain_score`: キャピタルゲインポテンシャルスコア（0〜100点）。将来の値上がり益、再販バリューアップ余力、割安仕入れ余力を総合評価。
  - `ai_fair_price_man`: AIが独自に査定した適正相場価格（万円）。
  - `capital_gain_perspective`: キャピタルゲイン（値上がり益・バリューアップ・出口戦略）に関する詳細評価解説。
  - `investment_rating`: 総合投資レーティング（AAA / AA / A / B）。
- `PropertyEvaluation` モデルのカラムまたは `report_data` に安全に保持し永続化。

### 2.2 二次選抜スクリーニング（`send_recommendations.py`）
- `_rank_by_qualitative_score` を `_rank_by_capital_gain_score` へ刷新。
- `ml_priority`（ML理論価格の割安率）は二次選抜スコアから**完全に排除**。
- スコアリング基準：
  - `capital_gain_score`（0〜100点）を主軸。
  - AI定性レーティング（AAA: 400点, AA: 300点, A: 200点, B: 100点）
  - 合計スコア = `rating_score` + `capital_gain_score`（最大500点満点）
  - ※未評価時はベース点のみとし、AI評価済みのキャピタルゲイン高評価物件が確実に最上位に選抜される。
- 各カテゴリ（mansion, kodate, tochi, investment）ごとに、キャピタルゲイン優先スコア上位5件を選抜。

---

## 3. 影響範囲（Blast Radius）
- `src/crawler/package/ml/report_generator.py`: プロンプト生成、関数シグネチャ、JSON出力スキーマ、永続化処理
- `src/crawler/scripts/ops/send_recommendations.py`: 二次選抜スコアリング関数、AI呼び出し処理
- `src/crawler/package/models/evaluation.py`: 必要に応じたフィールド追加、または既存カラム（`property_spec_evaluation` 等）への格納
- `src/crawler/tests/unit/test_two_stage_recommendations.py`: キャピタルゲイン最優先選抜の単体テスト
- `src/crawler/tests/unit/test_danchou_rag.py`: プロンプト生成およびレポート生成テスト

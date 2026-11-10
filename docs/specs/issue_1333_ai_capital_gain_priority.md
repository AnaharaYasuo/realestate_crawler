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

### 2.3 ディスカウント率カット条件の緩和・候補抽出クエリ改善・投資物件ルーティング適正化（Issue #1343）
- **ディスカウント率（割安率）カット条件の緩和**:
  - 予想価格が物件特性により散らばり、一定数が実勢より高めに算出されがちな傾向、および投資物件で保守的に予測されたケースの双方を考慮し、一次定量スクリーニング（`_evaluate_investment_candidate` / `_evaluate_residential_candidate`）のディスカウント率許容レンジを従来の `20.0% <= discount_pct <= 35.0%` から **`15.0% <= discount_pct <= 60.0%`（予測価格 / 売出価格比率 2.5倍まで許容）** へ緩和する。
  - 予測価格が売出価格の2.5倍超（`discount_pct > 60.0%`）または0.33倍未満の極端な異常値のみを安全弁ガードで除外し、一次網を広く取った上で Stage 2 の AI キャピタルゲイン目利きによって真のお宝物件を厳選する。
- **候補抽出クエリ（`_fetch_recommendation_candidates`）のフィルタ精緻化**:
  - `is_first_stage_passed=True`, `duplicate_of__isnull=True`, `first_stage_predicted_price__gt=0` をクエリ条件に必須化し、理論価格割れ（不合格）や未算出レコードによって上位300件枠が埋め尽くされる事象を防止する。
- **実物件解決（`batch_resolve_properties` / `get_property_record`）の堅牢化**:
  - `pageUrl` 完全一致で解決できない場合（`athome` のクエリパラメータ付きURLや `property_type='apartment'` 等の歴史的表記揺れ）に備え、`property_id` による主キー解決フォールバックおよび `*Investment*` モデルへの柔軟なマッチングを実装する。
- **投資物件のSlackチャンネルルーティングと枠配分の改善**:
  - `property_type == "investment"`（`ReguideInvestment`, `OdakyuInvestment`, `Sumai1Investment`, `SumirinInvestment` 等）や `KenbiyaInvestmentBuilding` の配信先判定において、物件名キーワードだけでなく `PropertyTypeDetector.detect_from_object(prop)` の判定結果（`apartment` / `mansion` ➔ `goodproperty-invest-apartment`、`invest_kodate` / `kodate` ➔ `goodproperty-invest-kodate`）を併用し、一棟アパート・マンションが戸建てチャンネルへ誤配信される問題を根絶する。
  - `investment` カテゴリ内の選抜において、一棟アパート系（`goodproperty-invest-apartment`）と投資戸建て系（`goodproperty-invest-kodate`）の双方が候補に存在する場合は特定サブタイプが枠を独占しないようバランス配分を行い、`BatchMetrics.build_recommendation_slack_summary` でも配信先チャンネル種別を正確に集計・表示する。

---

## 3. 影響範囲（Blast Radius）
- `src/crawler/package/ml/report_generator.py`: プロンプト生成、関数シグネチャ、JSON出力スキーマ、永続化処理
- `src/crawler/scripts/ops/send_recommendations.py`: 二次選抜スコアリング関数、AI呼び出し処理
- `src/crawler/package/models/evaluation.py`: 必要に応じたフィールド追加、または既存カラム（`property_spec_evaluation` 等）への格納
- `src/crawler/tests/unit/test_two_stage_recommendations.py`: キャピタルゲイン最優先選抜の単体テスト
- `src/crawler/tests/unit/test_danchou_rag.py`: プロンプト生成およびレポート生成テスト

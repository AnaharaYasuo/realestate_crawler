# 仕様書: Issue #1175 割安物件通知の所在地・駅・割安額視認性向上、投資前提条件強制、およびプロ鑑定×元祖狼旅団団長RAGレポート基盤

## 1. 背景と課題 (Background & Issues)
1. **通知文の情報不足・視認性の課題**:
   - 割安物件・投資物件のSlack通知文において、物件所在地や最寄り駅・徒歩分数が欠落しやすい。
   - 理論予測価格と売出価格の差額（割安金額）や割安率が一目でわかりにくく、投資判断が遅れる。
2. **投資物件ピックアップの前提条件欠落**:
   - `_evaluate_investment_candidate` において、投資スコア基準（`score >= 70.0`）による抽出時、理論予測価格（`predicted_price`）が存在する場合でも「理論予測価格 > 売出価格（割安であること）」が前提条件として強制されていなかった。
3. **プロ水準の目利きと定性評価のDB永続化の欠如**:
   - 高額なプロの不動産投資・鑑定評価レポート（3面アプローチ、最有効使用・容積未消化余力、法的/物理的リスク）と同等以上のインサイトが不足していた。
   - さらに、元祖FC2ブログ『狼旅団の地下に潜った不動産ブログ』の団長（メカ団長）が持つ「瞬間蒸発の嗅ぎ分け、挨拶代わりの指値の是非、レントロール原契約チェック、泥水再生力」という実戦的リアリズムを取り入れたい。
   - これらの定性評価を通知時だけでなく `PropertyEvaluation` DBモデルに永続化し、資産として蓄積したい。
   - クラウド本番実行とローカル本番実行の双方が同一のGoogle Cloud（GCS/Cloud SQL）上の団長ナレッジベース（RAG）を参照可能とする。

## 2. 要件定義 (Requirements)

### 要件 1: 投資物件ピックアップの前提条件強制（理論価格 > 売出価格）
- `_evaluate_investment_candidate(eval_rec, prop)` において：
  - 売出価格（万円単位）および理論予測価格（`pred_price`）を取得。
  - **`pred_price > 0` の場合、必ず `pred_price > asking_price_man`（理論価格が売出価格を上回っていること）を必須条件とする。**
  - 理論価格が売出価格以下の場合は、投資スコアが高くても選定対象外（`return False, "", 0.0`）とする。

### 要件 2: 通知対象（ピックアップ通過物件）のみに限定したAI高度レポート生成
- 全クロール物件ではなく、**通知対象として最終選抜された物件（1回あたり数件〜十数件）のみ** を対象にGemini（`gemini-3.8-flash` / `gemini-2.5-flash`）を呼び出す。
- **団長RAG（Retrieval-Augmented Generation）**:
  - Google Cloud Storage (`gs://{GCS_BUCKET}/rag/danchou_kb.jsonl`) またはローカルキャッシュ/内蔵シードナレッジから、物件特徴（ボロ戸建、木造アパート、積算超え、容積余力、指値など）にマッチする団長エピソード（2〜3件）を動的検索。
  - プロンプトに注入し、元祖ブログの語り口で辛口実戦レビューを生成。
- **プロ鑑定・最有効使用分析**:
  - 3面価格アプローチ（売出価格、ML理論価格、積算価格）
  - 指定容積率と現況消化率のギャップから「未消化容積余力（増床・建て替えポテンシャル）」を算出。
  - 法的・物理的DDチェック（接道・私道・旧耐震・擁壁等）。

### 要件 3: データベース（PropertyEvaluation）への定性評価カラム追加
- `PropertyEvaluation` に以下のカラムを追加（マイグレーション実施）：
  - `ai_evaluation_summary`: 総合査定サマリー（TextField, blank=True）
  - `highest_and_best_use`: 最有効使用・容積余力分析（TextField, blank=True）
  - `danchou_comment`: 元祖・狼旅団 団長の実戦辛口講評（TextField, blank=True）
  - `ai_positive_points`: 高評価ポイント（TextField, blank=True）
  - `ai_negative_points`: 留意・リスクポイント（TextField, blank=True）
  - `far_slack_ratio`: 未消化容積率（FloatField, null=True, blank=True）
  - `investment_rating`: 総合投資レーティング（CharField(max_length=10), blank=True）

### 要件 4: 通知メッセージ（Slack配信）の刷新
- 所在地・駅情報（各社モデルの全フィールドから漏れなくフォールバック抽出）
- 価格・割安情報（売出価格、理論価格、割安額、割安率、積算価格）
- 容積余力・スペック
- プロ鑑定 ＋ 団長RAG講評ブロックをわかりやすく整理して配信。

## 3. アーキテクチャと影響範囲 (Blast Radius)
- `src/crawler/package/models/evaluation.py`: カラム追加
- `src/crawler/package/migrations/0066_*.py`: マイグレーション
- `src/crawler/package/ml/danchou_rag.py`: 団長RAG検索・ナレッジ管理モジュール（新設）
- `src/crawler/scripts/ops/send_recommendations.py`: 前提条件判定、AIレポート生成、Slack通知文刷新
- `src/crawler/tests/unit/test_investment_recommendations.py`: 前提条件および評価判定テスト
- `src/crawler/tests/unit/test_danchou_rag.py`: RAG検索およびプロンプト生成テスト
- `src/crawler/tests/unit/test_send_recommendations.py`: メッセージ整形・通知テスト

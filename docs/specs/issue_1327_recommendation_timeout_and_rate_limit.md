# 仕様書: Issue #1327 お宝物件通知パイプラインのGeminiレート制限タイムアウト防止と選抜フロー適正化

## 1. 概要・背景
2026-11-08 05:10 JST 起動の Cloud Run Job `realestate-ml-pipeline-prod-gtltr` において、Slackお宝物件通知（`send_recommendations.py`）が Cloud Run Job の最大実行時間（7200秒 = 2時間）を超過し、タイムアウト強制終了によりSlack通知が未達となった。

### ログ証跡（事実）
- `2026-11-07 20:10:01 UTC` (05:10 JST) にジョブ起動。
- `21:39〜22:10 UTC` (06:39〜07:10 JST) にかけて、`package.ml.report_generator` が `gemini-3.6-flash` に対してレート制限 `HTTP 429` で連続失敗し、`retry 1/3 (24.9s)`, `retry 2/3 (69.7s)`, `retry 3/3 (116.6s)` などの指数バックオフで長時間停止を繰り返していた。
- `22:10:01 UTC` (07:10 JST) に `The configured timeout was reached.` で強制終了。

### 根本原因
1. **処理対象件数の過大**:
   - Issue #1311 で二段階スクリーニングが導入された際、Stage 1（一次選抜）で4カテゴリ（mansion, kodate, tochi, investment）× 各50件 = 最大200件 が選抜された。
2. **無駄なフルレポート生成**:
   - Stage 2 で最終配信されるのは各カテゴリ5件（計20件程度）であるにもかかわらず、Stage 1 で抽出された全件（最大200件）に対して、詳細Web本文のスクレイピング・Gemini API（`generate_professional_and_danchou_report`）を直列同期ループで呼び出していた。
3. **レート制限（429）による指数バックオフの累積**:
   - Gemini API の短時間呼び出し急増により 429 エラーが多発。指数バックオフリトライにより1件あたり数分間停止し、最大200件の直列実行では数時間を要し、確実にジョブタイムアウト（2時間）に突き当たった。

---

## 2. 改善・改修設計 (Architecture Design)

### 2.1 スクリーニング＆評価フローの再構築
全体の処理時間を 5〜10分以内（Gemini API 呼び出し総数 20〜30回以下）に収める設計とする。

1. **Stage 1（ML割安度一次スクリーニング）の適正化**:
   - 各カテゴリの上限 `STAGE1_PER_CATEGORY_LIMIT` を 50件 から **10〜15件** に適正化（4カテゴリ計40〜60件程度）。
   - ML予測価格との乖離率（割安度）および総合スコア順でソート。

2. **Stage 2（選抜とレポート生成の分離・遅延実行）**:
   - **ここが最大の設計改善点**: 全候補に対して重たいフルレポートを生成してから5件を選ぶのではなく、
   - **事前スコアリングまたはすでにレポート生成済みの優先度** で各カテゴリ上位 `STAGE2_PER_CATEGORY_QUOTA`（5件、計最大20件）を最終選抜する。
   - **最終選抜された上位20件に対してのみ**、未生成であれば `generate_professional_and_danchou_report` を呼び出してAI多面鑑定レポートを生成・永続化する。
   - これにより、Gemini API の呼び出し回数は **最大でも20回（新規物件のみ）** に激減する。

3. **レートリミット対策 & 全体タイムアウト安全弁**:
   - 各API呼び出し間の待機インターバル: 2.0秒（クォータ安全圏）。
   - `report_generator.py` の 429 リトライ設定: 最大待機時間の上限を緩和しすぎず、かつ過度なリトライで全体をハングさせない。
   - レポート生成処理全体にタイムアウトガード（例: 最大15分経過、または連続429失敗時はフォールバックして既存データでSlack通知を強行）を設ける。
   - 万が一 Gemini API が一時的に全滅した場合でも、ML割安度・基本スペック情報のみの標準Slack通知メッセージで確実に配信を完遂する（Slack未通知という最悪の障害を防止）。

---

## 3. 影響範囲 (Blast Radius)
- `src/crawler/scripts/ops/send_recommendations.py`:
  - `send_recommendations()` 内の選抜・レポート生成ループの順序を「選抜 ➔ 上位のみレポート生成」に変更。
  - `STAGE1_PER_CATEGORY_LIMIT` を 15 に調整。
  - タイムアウト・エラーハンドリング強化。
- `src/crawler/tests/unit/test_two_stage_recommendations.py`:
  - 変更後の二段階選抜およびレポート生成フローの単体テスト更新・追加。

---

## 4. 検証計画
- `pytest src/crawler/tests/unit/test_two_stage_recommendations.py` 全テストパス
- `pytest src/crawler/tests/unit/test_architecture_harness.py` パス
- 本番反映後、未送信分の通知ジョブを実行し Slack 通知が正常着信することを確認

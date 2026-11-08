# 仕様書: Issue #1327 お宝物件通知パイプラインのGeminiレート制限タイムアウト防止と選抜フロー適正化

## 1. 概要・背景
2026-11-08 05:10 JST 起動の Cloud Run Job `realestate-ml-pipeline-prod-gtltr` において、Slackお宝物件通知（`send_recommendations.py`）が Cloud Run Job の最大実行時間（7200秒 = 2時間）を超過し、タイムアウト強制終了によりSlack通知が未達となった。

### ログ証跡（事実）
- `2026-11-07 20:10:01 UTC` (05:10 JST) にジョブ起動。
- `21:39〜22:10 UTC` (06:39〜07:10 JST) にかけて、`package.ml.report_generator` が `gemini-3.6-flash` に対してレート制限 `HTTP 429` で連続失敗し、`retry 1/3 (24.9s)`, `retry 2/3 (69.7s)`, `retry 3/3 (116.6s)` などの指数バックオフで長時間停止を繰り返していた。
- `22:10:01 UTC` (07:10 JST) に `The configured timeout was reached.` で強制終了。

### 根本原因
1. **Geminiモデルのクォータと負荷**:
   - `gemini-3.6-flash` は Google Workspace / Gemini API の RPM / TPM クォータ制約が厳しく、連続呼び出し時に 429 レートリミットが多発。
   - `report_generator.py` の指数バックオフリトライにより1件あたり数分間停止し、ジョブタイムアウト（2時間）に到達した。
2. **無駄な全件事前フルレポート生成**:
   - Stage 1 で抽出された全候補に対して、詳細Web本文のスクレイピング・Gemini API（`generate_professional_and_danchou_report`）を直列同期ループで呼び出していた。

---

## 2. 改善・改修設計 (Architecture Design)

件数は削減せず（`STAGE1_PER_CATEGORY_LIMIT = 50` を維持）、**モデルの軽量化（クォータ緩和・高速化）** および **遅延生成・タイムアウトガード** により安定完走を実現する。

1. **モデルの軽量化（スループット向上・レート制限回避）**:
   - 既定モデル: **`gemini-3.5-flash-lite`**（高スループット、緩やかなレート制限 `_model_wait_factor = 1.0`）を採用。
   - フォールバックモデル: **`gemini-3.1-flash-lite`** を第一フォールバックとし、次点に **`gemini-2.5-flash-lite`** を配置。
   - これにより、429発生リスクを最小化し、発生時の待機時間も大幅短縮。

2. **選抜母数（件数）の維持**:
   - `STAGE1_PER_CATEGORY_LIMIT = 50`（4カテゴリ×50件 = 計最大200件）を維持。
   - 候補物件を絞ることなく十分な母数から二次選抜を行う。

3. **Stage 2 選抜後の遅延レポート生成**:
   - 事前スコアリングで各カテゴリ上位 `STAGE2_PER_CATEGORY_QUOTA`（5件/種別、計最大20件）を最終選抜。
   - 最終選抜された上位20件に対してのみ、未生成であれば `generate_professional_and_danchou_report` を呼び出してAI多面鑑定レポートを遅延生成。
   - API呼び出しインターバル: 2.0秒。

4. **15分全体タイムアウトガード & スレッド個別タイムアウト制御**:
   - Stage 2 レポート生成全体に最大15分（`MAX_STAGE2_DURATION_SEC = 900`）の安全弁を設定。
   - 各物件の生成呼び出しにも残り時間予算（`remaining_budget`）を適用し、期限超過時は即座にSlack配信へ進む。

---

## 3. 検証計画
- `pytest src/crawler/tests/unit/test_two_stage_recommendations.py` 全テストパス
- `pytest src/crawler/tests/unit/test_architecture_harness.py` パス
- 本番反映後、未送信分の通知ジョブを実行し Slack 通知が正常着信することを確認

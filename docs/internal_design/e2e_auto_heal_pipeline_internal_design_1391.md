# 内部設計書: パイプラインE2E包括オートヒール指示書生成とGemini分析高度化 (Issue #1391)

## 1. 概要・背景
現行のリアルタイム不動産パイプライン（`run_pipeline.py`）では、Step 2.5（クローリング直後）に自己修復指示書生成（`auto_heal_parsers.py`）が配置されていた。
このため、後続の Step 3（MLモデル学習）、Step 4（バルク価格推定・評価）、Step 5（Slackリコメンド配信）、Step 6（日次精度診断）で発生したエラー（例: DB接続切れ `2006 Server has gone away`、推論モデルクラッシュ、データ型不整合）を拾えず、パイプライン全体の自己修復機能として実効性が乏しかった。
さらに、Gemini モデル指定が廃止済みの `gemini-2.5-flash`（404 Not Found）のままであったため、AI によるインテリジェントな根本原因分析や解決策提示が行われず、単なるエラー文字列の生ダンプに退行していた。

## 2. 改善方針

### 2.1 パイプライン末尾への移動 (Step 7 / Comprehensive Post-Pipeline)
- Step 2.5 を廃止し、パイプラインの全ステップ完了後（または失敗時の `finally` / teardown 直前）に包括的自己修復指示書を生成する。
- 実行ログ、Slackテレメトリ、パイプラインの各ステップの成否（`failed_steps`）を包括的に集約する。

### 2.2 Geminiモデル最新化 & 環境変数追従
- `gemini-2.5-flash` を廃止し、`GEMINI_RECOMMEND_MODEL` 環境変数（デフォルト: `gemini-3.8-flash`、フォールバック: `gemini-3.1-flash-lite`）を優先使用する。

### 2.3 AI分析プロンプトの抜本的強化（実効性の確保）
- 単なるエラーの要約ではなく、エージェントが直ちに修正対応（`/auto-heal`）に着手できるよう以下の構成で出力させる：
  1. **Phase / Component**: 障害発生フェーズ（Crawler / Data Cleaning / ML Training / Bulk Evaluation / Slack Delivery）
  2. **Root Cause**: 根本原因（DOM変更、MySQL切断、メモリ枯渇、モデル入力不正など）
  3. **Actionable Fix**: 修正すべきファイルパス、関数・クラス名、推奨される修正コード方針
  4. **Next Command**: テスト実行および修正反映のための具体的コマンド

## 3. 変更対象ファイル
- `src/crawler/scripts/ops/run_pipeline.py`:
  - Step 2.5 の呼び出しを削除し、パイプラインの最終段（Step 6の後）に「Step 7: E2E Pipeline Comprehensive Health & AI Auto-Heal Instruction Generation」として配置。
  - 各ステップの失敗情報（`failed_steps`）を引数または環境変数経由で `auto_heal_parsers.py` に伝達。
- `src/crawler/scripts/debug_tools/auto_heal_parsers.py`:
  - `summarize_errors_with_gemini` の Gemini モデル指定を `os.getenv("GEMINI_RECOMMEND_MODEL", "gemini-3.8-flash")` に更新。
  - パイプライン各ステップ（ML学習、バルク推論、Slack配信等）の失敗ログや引数を解析・収集対象に追加。
  - AI プロンプトを根本原因分析および具体的修正ファイル提示に高度化。
- `src/crawler/tests/unit/test_auto_heal_parsers.py`:
  - E2E エラー集約および最新モデル連携のユニットテストを作成・検証。

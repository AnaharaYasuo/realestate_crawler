# Google GenAI SDK 移行要件定義 (Issue #502)

## 1. 概要 / ユーザーストーリー
* **ユーザーとして**、不動産クローラーおよびMLパイプラインの開発運用者
* **`google-genai` SDK への移行** をしたい
* **なぜなら**、従来の `google.generativeai` パッケージは非推奨（FutureWarning / EOL）となり、今後の更新停止および脆弱性リスク・互換性問題を防ぐため

## 2. アクセプタンスクライテリア (受入基準)
* [x] 【基準1】`google-generativeai` への直接依存を排除し、`google-genai` SDK を使用して種別判定・画像分析・統一プロパティ抽出・診断が動作すること
* [x] 【基準2】`pyproject.toml`、`poetry.lock`、`requirements.txt` の依存関係が正しく `google-genai` に更新され、ビルド・テストが通ること
* [x] 【基準3】`google.generativeai` 非推奨警告 (FutureWarning) が発生しないこと
* [x] 【基準4】関連ユニットテスト (`test_image_handler.py`, `test_ml_diagnostics.py` 等) およびパース処理がすべてパスすること

## 3. 影響範囲
* `src/crawler/package/utils/property_type_detector.py`
* `src/crawler/package/utils/image_handler.py`
* `src/crawler/package/ml/unified_property_extractor.py`
* `src/crawler/scripts/ops/run_daily_prediction_diagnostics.py`
* `src/crawler/pyproject.toml`, `src/crawler/poetry.lock`, `src/crawler/requirements.txt`
* `src/crawler/tests/test_image_handler.py`, `src/crawler/tests/unit/test_ml_diagnostics.py`

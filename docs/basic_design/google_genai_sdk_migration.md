# Google GenAI SDK 移行基本設計 (Issue #502)

## 1. 目的
非推奨となった旧 `google-generativeai` パッケージから新公式 SDK `google-genai`（`from google import genai` / `client = genai.Client(...)`）へ移行し、警告解消と今後の Gemini モデル利用の持続可能性を確保する。

## 2. アーキテクチャ変更点

| 項目 | 旧 SDK (`google-generativeai`) | 新 SDK (`google-genai`) |
|---|---|---|
| パッケージ名 | `google-generativeai` | `google-genai` |
| インポート | `import google.generativeai as genai` | `from google import genai` |
| クライアント初期化 | `genai.configure(api_key=api_key)`<br>`model = genai.GenerativeModel("...")` | `client = genai.Client(api_key=api_key)` |
| コンテンツ生成 | `model.generate_content(...)` | `client.models.generate_content(model="gemini-2.5-flash", contents=...)` |
| タイムアウト設定 | `request_options={"timeout": 30.0}` | `client = genai.Client(..., http_options={"timeout": 30.0})` |
| レスポンス取得 | `response.text` | `response.text` |

## 3. モデル指定方針
* `gemini-1.5-flash` または `gemini-2.5-flash` をプロジェクトのコスト・速度要件に合わせて指定。

## 4. 依存管理
* `src/crawler/pyproject.toml` の `google-generativeai` を `google-genai (>=2.0.0)` に置換。
* `poetry lock --no-update` または `poetry update google-genai` で `poetry.lock` 更新。
* `poetry export` で `src/crawler/requirements.txt` 同期。

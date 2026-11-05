# Issue #1260: Gemini API リトライ方針（エラーコード別）と推奨モデル変更

## 1. 背景
- 2026-11-05 のMLパイプライン再実行で `gemini-3.8-flash` が 30 回失敗（503: 17 / 429: 7 / 読取タイムアウト: 6）。
- 従来のリトライは「固定 1.5 秒 × 最大 2 回」で、1 回目に失敗した 15 件はすべて 2 回目も失敗した（リトライが無効）。通知が全件出たのはモデルフォールバックのおかげである。
- 429 でも 400/401/403 でも区別なく再試行しており、`Retry-After` も尊重していなかった。

## 2. 要件
1. 推奨モデルの既定値（環境変数 `GEMINI_RECOMMEND_MODEL` 未設定時）を `gemini-3.8-flash` の一段下である **`gemini-3.6-flash`** に変更する。`gemini-3.5-flash` は非推奨で API 側が `gemini-3.6-flash` に自動転送するため、既定値には実体の `gemini-3.6-flash` を明示する。フォールバック順は `[GEMINI_RECOMMEND_MODEL, gemini-3.5-flash-lite]`（重複除去。転送先と同一になる `gemini-3.5-flash` はフォールバックに含めない）。
2. リトライ可否・待機時間は **HTTP ステータスコード（またはエラー種別）に従って決定** する。

## 3. リトライ方針

| エラー | 分類 | リトライ | 基本待機（初回） | 備考 |
|---|---|---|---|---|
| 429 Too Many Requests | レート制限 | する（最大 `MAX_RETRIES_RATE_LIMIT=3` 回） | `RATE_LIMIT_BASE_SEC=15` × モデル係数 | `Retry-After` ヘッダがあれば優先（上限 `MAX_WAIT_SEC=180`）。2 回目以降は指数的に倍加 |
| 500 / 502 / 503 / 504 | サーバー側一時障害 | する（最大 `MAX_RETRIES_TRANSIENT=3` 回） | `TRANSIENT_BASE_SEC=3` | 指数バックオフ（×2） |
| 読取タイムアウト / 接続断 (`OSError` 系) | 一過性ネットワーク/過負荷 | する（最大 3 回） | `TRANSIENT_BASE_SEC=3` | 指数バックオフ（×2） |
| 応答が JSON として解釈不能 | LLM 出力不良 | 1 回のみ | `PARSE_RETRY_SEC=2` | 生成の非決定性に依存 |
| 400 / 401 / 402 / 403 / 404 その他 4xx | クライアント/認証/課金/モデル不在 | **しない** | – | そのモデルは即座に断念し、次のフォールバックモデルへ進む |

### 3.1 モデル係数（429 の待機延長）
上位モデルほどレート制限が厳しいため、429 の待機を長くする。

| モデル名 | 係数 |
|---|---|
| `*lite*` | 1.0 |
| `*flash*`（lite 以外） | 2.0 |
| それ以外（`*pro*` 等の上位モデル） | 4.0 |

待機時間 = `min(MAX_WAIT_SEC, base × 係数 × 2^(retry_index))` に ±20% のジッターを付与する。`Retry-After` がある場合は `max(Retry-After, 計算値の下限)` ではなく `Retry-After` を優先し、`MAX_WAIT_SEC` で頭打ちとする。

`Retry-After` は **秒数** または **HTTP-date** のどちらも解釈する（`_parse_retry_after()`）。HTTP-date は現在時刻との差分秒に変換する。負数・ゼロ・`nan`・解釈不能・過去日時は無効として既定のバックオフに戻し、`time.sleep` に不正値を渡さない。

### 3.2 応答 JSON の抽出
`_extract_json_object()` は応答全体をまず JSON として解析し、前後に文章がある場合のみ最初の `{` から `json.JSONDecoder().raw_decode` でオブジェクト終端を判定する（文字列値内の `}` で誤って途中切断しない）。

## 4. 実装
- 変更ファイル: `src/crawler/package/ml/report_generator.py`
  - `_classify_gemini_error()`: 例外から (リトライ可否, 種別, Retry-After 秒) を判定
  - `_model_wait_factor()`: モデル名から係数を返す
  - `_compute_retry_wait_sec()`: 待機時間算出（ジッター注入可能・テスト容易）
  - `_call_gemini_api()`: 上記に従ってリトライ。各リトライを `WARNING` ログ（モデル・HTTP コード・待機秒・試行回数）で可観測化
- 既存の `_call_gemini_api(model_name, api_key, prompt)` シグネチャは不変。

## 5. テスト
`src/crawler/tests/unit/test_gemini_retry_policy_1260.py`
- 既定モデルが `gemini-3.6-flash` であること（フォールバックに `gemini-3.5-flash` を含まない）
- `Retry-After` の HTTP-date を残り秒数へ変換し、負数・`nan`・解釈不能・過去日時は無効（既定バックオフ）とすること
- 文字列値内に `}` を含む有効な JSON 応答、前後に文章がある応答を正しく抽出すること
- 429 は 3 回までリトライし、`Retry-After` を尊重する
- 429 の待機は上位モデルほど長い（lite < flash < pro）
- 503 / タイムアウトは指数バックオフでリトライする
- 400 / 401 / 403 / 404 はリトライしない（`sleep` が呼ばれない）
- JSON 不能応答は 1 回のみ再試行する

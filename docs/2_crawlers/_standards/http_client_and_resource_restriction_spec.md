# 共通HTTPクライアント設計・MIME制限・リクエスト集約仕様書 (http_client)

## 1. 概要と背景
これまでのクローラーシステムでは、`baseParser.py`、`api.py`、および各個別パーサー（`keioParser`, `rearieParser`, `mizuhoParser` 等）に HTTP リクエスト処理（`aiohttp.ClientSession.get`, `requests.get` 等）が散逸していた。
これにより以下の問題が生じていた：
1. **リクエストヘッダー（`Accept`, `Accept-Language`）の不統一**：サーバー側で最適な圧縮形式（gzip/br）が選択されないリスクや、ブラウザ互換性の欠落によるWAF誤検知。
2. **不要な巨大バイナリ（PDF、動画、zipなど）の無制御ダウンロード**：HTML一覧/詳細ページを巡回する過程で誤ってPDFパンフレットや巨大ファイルを踏んだ場合、数十MBの無駄な通信とメモリを消費する。
3. **リクエスト遮断（Fast Abort）・タイムアウト・リトライ制御の重複と不統一**。

本仕様では、上記を一元管理する共通HTTPクライアントモジュール `package.utils.http_client` を新設し、全クローラー・パーサーのリクエスト処理をここに集約・統一する。

---

## 2. 内部設計

### 2.1 モジュール構成
- ファイルパス: `src/crawler/package/utils/http_client.py`
- 主なインターフェース:
  1. `async_fetch_html_or_data(session, url, ...)`: 非同期HTML/JSON取得関数（パーサー・クローラー用）
  2. `fetch_image_bytes(url, ...)`: 画像専用取得関数（画像解析・ダウンロード用）
  3. `FastAbortNonHtmlException`: 許可されていない Content-Type（PDF等）を検出した際の早期切断例外
  4. `MaxPayloadExceededException`: 許容サイズ（デフォルト10MB）を超過した際のメモリ防衛例外

### 2.2 リソース制限 ＆ 最適化仕様
1. **最適化ヘッダーの自動注入**:
   ```python
   DEFAULT_HEADERS = {
       "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
       "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,application/json;q=0.8,*/*;q=0.7",
       "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
   }
   ```
2. **`Content-Type` 早期切断（Fast Abort）**:
   - `session.get` 直後、ボディ（Body）をダウンロードする前に `response.headers.get("Content-Type")` を検査。
   - 許可ホワイトリスト:
     - `text/html`
     - `application/xhtml+xml`
     - `application/json`
     - `text/xml`
     - `application/xml`
     - `text/plain`
   - 禁止バイナリ（`application/pdf`, `video/*`, `application/zip`, `application/octet-stream` など）が返された場合、即座に `response.close()` して切断し、ボディをダウンロードしない。
3. **最大ペイロード長ガードレール**:
   - HTML等のテキストであっても、10MBを超える巨大レスポンスはストリーミング読み込みで遮断し、OOM（Out of Memory）を防止する。
4. **画像取得（`fetch_image_bytes`）の防衛**:
   - `Content-Length` を事前検査し、5MBを超える巨大画像は取得をスキップ。
   - `Content-Type` が `image/` で始まることを検証。

---

## 3. 呼び出し箇所の集約

| 呼び出し元 | 従来の処理 | 集約後の処理 |
|---|---|---|
| `package.parser.baseParser.ParserBase._getContent` | 独自 `session.get` ループ | `async_fetch_html_or_data` を呼出 |
| `package.parser.keioParser.KeioMansionParser._fetchJson` | `requests.get` (同期) | `async_fetch_html_or_data` を呼出 |
| `package.parser.rearieParser.RearieParser` | 独自 `session.get` | `async_fetch_html_or_data` を呼出 |
| `package.parser.reguideParser.ReguideParser` | 独自 `session.get` | `async_fetch_html_or_data` を呼出 |
| `package.parser.mizuhoParser.MizuhoParser` | 独自 `session.get` | `async_fetch_html_or_data` を呼出 |
| `package.parser.kenbiyaParser.KenbiyaParser` | 独自 `session.get` | `async_fetch_html_or_data` を呼出 |
| `package.utils.image_handler._fetch_single_pil_image` | 独自 `requests.get` | `fetch_image_bytes` を呼出 |
| `scripts.ops.run_ttl_expired_recrawl.crawl_ttl_expired_targets_async` | 共有 `ClientSession` に旧 `api.header` (UAのみ) | `http_client.DEFAULT_HEADERS` を共有セッション標準ヘッダーに統一 (#1439) |

---

## 4. 期待効果
- **ネットワーク転送量削減**: 不要バイナリ（PDFなど）の誤取得時のトラフィックとメモリ消費を 0% に削減。
- **保守性と可観測性の向上**: ヘッダー仕様変更やWAF対策、プロキシ対応などを `http_client.py` 1箇所で制御可能に。

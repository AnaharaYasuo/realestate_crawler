# 健美家 (Kenbiya) サイト構造および通信仕様仕様書

## 1. 概要
健美家（Kenbiya）は、一棟アパート・一棟マンション・区分マンション・戸建て・土地等の収益・投資用不動産を中心とした大手ポータルサイトである。
本ドキュメントでは、健美家のURL体系、F5 BIG-IP WAFによるレートリミット挙動（HTTP 429）、およびクローラー・価格推定APIでの耐障害性向上仕様を定義する。

## 2. URL体系
- 物件詳細URL: `https://www.kenbiya.com/pp2/s/<prefecture>/<city>/.../re_<property_id>/`
- メール通知URL: `https://www.kenbiya.com/.../?utm_source=newmail&utm_medium=email&utm_campaign=newmail`
- 追跡用クエリパラメータ（`utm_*`, `mail_*` 等）は物件特定には無関係であり、パースおよび保存前に `UrlMatcher.normalize()` により除去・正規化を行う。
- ただし物件識別子がクエリに載るサイト（Rearie の `?id=` 等）では識別子クエリを保持する（Issue #317）。

## 3. WAF & レートリミット (HTTP 429) / IPブロック対策と住宅用Proxy運用仕様
### 3.1 挙動
- 健美家のフロントには F5 BIG-IP WAF が配置されており、短時間の連続アクセスやデータセンターIP等に対して `HTTP 429 Too Many Requests` や `HTTP 403 Forbidden`（IPブロック）を返却する。
- 429/403発生時は一時的なIP制限状態となり、極めて短いスリープ（2〜4秒）では解除されない。

### 3.2 回避・ハンドリング仕様
1. **User-Agent ローテーション**:
   - 古いハードコードUA（Chrome 123等）を廃止し、最新のモダンブラウザUA（Chrome 130+, Safari 17+, Firefox 132+）をリクエスト毎にローテーション適用する。
2. **住宅用Proxy（Residential Proxy）の選択的適用 (Issue #1486)**:
   - 従量課金の住宅用Proxyを健美家に限定して投入できるように、`KENBIYA_PROXY_URL`（またはフォールバックとして `RESIDENTIAL_PROXY_URL`）環境変数をサポートする。
   - `KenbiyaParserBase._getContent` の `aiohttp.ClientSession.get(..., proxy=...)` に設定済みProxyを自動注入する。
   - Proxy未設定時（デフォルト）は従来通り直接アクセスを行い、既存動作との完全な後方互換性を維持する。
3. **Playwright フォールバック時の Proxy 連動 ＆ ギガ浪費防止ガード**:
   - HTTP 403検知時に発動する Playwright ヘッドレスブラウザ処理（`_fetch_with_playwright`）にも同一Proxy設定を連動させる。
   - 従量課金通信量を最小化（1件あたり50〜70KBを死守）するため、Playwright ページ内での画像・メディア・フォント・スタイルシート等の静的リクエストをルート遮断（`page.route("**/*", abort)`）する。
4. **RateLimitedException の導入**:
   - HTTP 429 を単なるタイムアウト（504）や一般的パース失敗（422）と混同せず、`RateLimitedException` として明示的に捕捉・分類する。
5. **API レスポンスマッピング**:
   - `/api/evaluation/predict-by-url` において `RateLimitedException` を検知した場合、HTTP 429 `TARGET_SITE_RATE_LIMITED` を返却し、呼び出し元に適切な待機・再試行を促す。
4. **Playwright フォールバック時の静的アセット取得遮断 (Issue #1484)**:
   - WAFブロック時の Playwright ステルス取得において、画像（png, jpg, webp 等）、CSS、フォント（woff, ttf 等）、メディア等の静的アセットへのリクエストを `page.route` で即座に `abort()` 遮断する。
   - これにより、健美家サーバーおよび WAF への通信負荷を最小化し、ページ描画時間とメモリ使用量を大幅に低減する。


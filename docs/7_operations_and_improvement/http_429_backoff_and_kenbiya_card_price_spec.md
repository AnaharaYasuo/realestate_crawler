# 全サイト共通HTTP 429バックオフリトライおよび健美家カード価格抽出・差分スキップ仕様書 (Issue #1577)

## 1. 概要
本改修では、以下の2つの根本対策を実施する：
1. **全サイト共通の429自動バックオフ・リトライ**:
   - 一時的なレートリミット（HTTP 429 Too Many Requests）が発生した際、即座にエラー・スキップとせず、指数バックオフで間隔を空けて自律リトライし、クロールを正常継続させる。
2. **健美家一覧カードからの価格抽出による差分スキップ（Differential Crawl）復旧**:
   - 健美家の物件一覧ページから物件価格を確実にパースして `ListItem(url, price=...)` に設定する。
   - これにより、価格変更のない既存物件を `Skip (Cached Active)` とし、無駄な大量詳細アクセス（約1.5万件）を数千件規模で削減する。

---

## 2. 変更仕様

### 2.1 全サイト共通基底パーサーにおける429リトライ (`package.parser.baseParser.ParserBase`)
- **対象**: `ParserBase._getContent`
- **仕様**:
  - `status_validator` または通信結果において HTTP 429 (`RateLimitedException`) が検知された場合、試行回数上限（`max_timeouts`、既定3回）まで指数バックオフ（`2 ** (attempt + 1)` 秒スリープ）を挟んで再試行する。
  - 最大試行回数を超過した場合は `RateLimitedException` を送出する。
  - これにより、健美家固有のコードだけでなく、全クローラーで 429 レートリミットの一時的発生を吸収可能とする。

### 2.2 健美家パーサーにおけるカード価格抽出の最適化 (`package.parser.kenbiyaParser.KenbiyaParserBase`)
- **対象**: `KenbiyaParserBase.parsePropertyListPage` および価格抽出ロジック
- **仕様**:
  - `a` タグの親コンテナ（`div.bf-box`, `div.articleItem`, `tr`, `div`, `section` 等）から価格要素（`.price`, `dd.price`, `span.num`, テキスト `X,XXX万円`）を特定し、数値をパースして `ListItem(url, price=price)` を返却する。
  - `tr` 内にリンクと価格が別々の `td` に分かれているテーブル構造や、カード内 `dl > dd.price` 構造でも価格を厳格に取得する。

---

## 3. テストと検証方針 (TDD)
1. **`test_http_429_backoff_and_kenbiya_card_price.py`**:
   - `ParserBase._getContent` が 429 応答を受けた際にスリープを挟んでリトライし、成功時にコンテンツを返すことを検証。
   - 429 が連続して上限超過した際に `RateLimitedException` が送出されることを検証。
   - `KenbiyaParserBase.parsePropertyListPage` がカードHTMLから正しく `item.price` を抽出することを検証。
2. **アーキテクチャハーネス**:
   - `test_architecture_harness.py` を通過すること。

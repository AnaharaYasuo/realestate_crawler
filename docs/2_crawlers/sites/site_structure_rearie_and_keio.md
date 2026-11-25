# サイト構造仕様書: パナソニックホームズ不動産 (Rearie) & 京王不動産 (Keio)

## 1. パナソニックホームズ不動産 (Rearie)
### 1.1 概要
Rearie は静的HTML一覧/詳細ページから、Repros (`phfudousan.repros.jp`) REST API を利用したクライアントサイドレンダリング (CSR) 構成へ移行。

### 1.2 エンドポイント仕様
- **基底URL**: `https://phfudousan.repros.jp`
- **必須リクエストヘッダー**:
  - `Origin`: `https://homes.panasonic.com`
  - `Referer`: `https://homes.panasonic.com/`
  - `x-Requested-With`: `XMLHttpRequest`
- **一覧取得API (v2)**:
  - マンション: `/api/v2/kubunList/?key={KEY}&page={PAGE}`
  - 戸建て: `/api/v2/kodateList/?key={KEY}&page={PAGE}`
  - 土地: `/api/v2/tochiList/?key={KEY}&page={PAGE}`
- **詳細取得API (v1)**:
  - マンション: `/api/v1/kubunDetail/?id={ID}&key={KEY}`
  - 戸建て: `/api/v1/kodateDetail/?id={ID}&key={KEY}`
  - 土地: `/api/v1/tochiDetail/?id={ID}&key={KEY}`

### 1.3 パース方針
- 一覧取得時: JSONレスポンスの `data.list` から各物件IDを抽出し、詳細API URLを生成・ディスパッチ。
- ページネーション: `data.page < data.maxPage` の場合に次ページURL（`page=N+1`）を呼び出し。
- 詳細取得時: JSONレスポンスの `data` 直下から各フィールド（`propName`, `price`, `address`, `tateMenseki`, `tochiKenri`, `torihiki` 等）を直接マッピング。

---

## 2. 京王不動産 (Keio)
### 2.1 概要
京王不動産仲介サイト (`chukai.keiofudosan.co.jp`) は、一覧ページでスケルトンローディングを行い、WordPress REST API から物件一覧HTMLを非同期取得する構成。

### 2.2 エンドポイント仕様
- **基底URL**: `https://chukai.keiofudosan.co.jp`
- **検索結果API**:
  - URL: `/wp-json/wp/v2/get_search_result_sale`
  - パラメータ:
    - `rent_or_sale`: `sale`
    - `area_or_line`: `area`
    - `item_per_page`: `30`
    - `page_num`: `1`
    - `pref`: `13`
    - `boshu_kind_summary_code[]`: マンション=`1`, 戸建て=`3`, 土地=`4`
- **詳細ページ**:
  - URL: `https://chukai.keiofudosan.co.jp/sale/<PROPERTY_ID>/`
  - 静的HTMLサーバーサイドレンダリング (SSR)。

### 2.3 パース方針
- 一覧取得時: `/wp-json/wp/v2/get_search_result_sale` を呼び出し、レスポンスJSONの `html` から物件詳細リンク `/sale/<ID>/` を抽出。
- ページネーション: `div.block_pager a.pager` の `data-page` または現在の `page_num` に基づき次ページURL（`page_num=N+1`）を生成。
- 詳細取得時: 既存の `KeioParser._parsePropertyDetailPage` (HTMLパース) にて抽出。

## Auto-Heal バッチ修復仕様追記 (#1444, #1447, #1450, #1453, #1455, #1458, #1468, #1470, #1480, #1774)
- **掲載終了・非販売ページのスキップ防衛**: Rearie (`RearieMansionParser`), Misawa (`MisawaMansionParser`), Sumai1 (`Sumai1MansionParser`), Mitsui (`MitsuiInvestmentKodateParser`) において、物件名・価格・面積・間取り等の必須詳細情報が空の掲載終了／ライブラリページは `SkipPropertyException` でスキップする。
- **4層種別判定防衛の強化**: Afr (`AfrMansionParser`, `AfrTochiParser`), Daikyo (`DaikyoMansionParser`), Sekisui (`SekisuiMansionParser`) において、一棟物件・戸建て・土地URL混入を `SkipPropertyException` で除外する。
- **複合表記・テーブル抽出の強化**: Toho (`TohoBaseParser._get_specs`) で `<table><tr><th>/<td>` 抽出および `建ぺい率/容積率` 複合表記パースをサポートし、`afr.yaml` で漢字表記 `建蔽率` をマッピングする。
- **隔離済みレコードの自己修復ループ根治 (#1468)**:
  - `auto_heal_parsers.py` は `PropertyEvaluation` の異常スキャン時に `heal_status="source_data_invalid"`（`recrawl_anomalies.py` で再クロール対象外として隔離済み）を除外し、ゾンビレコードによる Issue 無限再オープンを防止する。

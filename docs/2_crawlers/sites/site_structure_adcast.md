# サイト構造: アドキャスト (Ad-Cast)

## 概要
- **サイト名:** アドキャスト (ad-cast.info)
- **ベースURL:** `https://www.ad-cast.info`
- **タイプ:** 居住用（土地, 戸建て, マンション ※城南・都心特化）
- **レンダリング方式:** 静的HTML (SSR)

## URLパターン

### 1. スタート・検索結果 (一覧ページ)
- **新着一覧:** `https://www.ad-cast.info/sch/osusume_list.php?flg1=2&prm1=15`
- **アドキャスト限定:** `https://www.ad-cast.info/sch/osusume_list.php?flg1=1&prm1=1`
- **ページネーション戦略:** `UrlPatternPagination`（`&page={n}`）

### 2. 詳細ページ
- **URLパターン:** `https://www.ad-cast.info/sch/detail.php?k_number={id}&div={code}` (例: `/sch/detail.php?k_number=20261002z&div=005`)

## セレクタ (詳細ページ)

### 共通情報
- **物件名:** `h1` または タイトル
- **価格:** `.price` から正規表現抽出 (`converter.parse_price` で円単位化)
- **スペックマップ:** 詳細テーブル (`table tr th, td`) を走査してキャッシュ

### 種別判定ルール
- スペック表に「建物面積」あり ➔ `KodateParserBase`
- スペック表に「土地面積」のみで建物面積なし ➔ `TochiParserBase`
- 「専有面積」あり ➔ `MansionParserBase`

| 項目名 (th) | モデルフィールド | 抽出・変換ルール |
| :--- | :--- | :--- |
| **所在地** | `address` | 文字列抽出 |
| **交通** | `traffic` | 駅徒歩分数 |
| **土地面積** | `tochiMenseki` | `converter.parse_menseki` |
| **建物面積** | `tatemonoMenseki` | `converter.parse_menseki` |
| **間取り** | `madori` | 文字列抽出 |
| **権利形態** | `tochikenri` | 所有権等 |
| **建ぺい率 / 容積率** | `kenpei`, `youseki` | 正規表現抽出 |

### 掲載終了検知
- HTTP 404
- 本文中の「掲載終了」「成約済」検知で `ListingEndedException` 送出。

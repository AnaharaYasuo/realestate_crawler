# サイト構造: 東宝ハウス (Toho House)

## 概要
- **サイト名:** 東宝ハウス (th-yokohama.com 等)
- **ベースURL:** `https://th-yokohama.com` (代表例: 東宝ハウス横浜)
- **タイプ:** 居住用（土地, マンション, 戸建て）
- **レンダリング方式:** 静的HTML (SSR)

## URLパターン

### 1. スタート・検索結果 (一覧ページ)
- **土地一覧:** `https://th-yokohama.com/estates/index?div=0&page={n}`
- **マンション一覧:** `https://th-yokohama.com/estates/index?div=1&page={n}`
- **戸建て一覧:** `https://th-yokohama.com/estates/index?div=2&page={n}`
- **ページネーション戦略:** `UrlPatternPagination`（`&page={n}`）

### 2. 詳細ページ
- **URLパターン:** `/estate_list_{area}/estate_detail_{id}_{sub}.html`

## セレクタ (詳細ページ)

### 共通情報
- **物件名:** `h1`
- **価格:** `.price` (`converter.parse_price` で円単位化)
- **スペックマップ:** `<dl>` タグ内の `<dt>` と `<dd>` を1対1で抽出・キャッシュ

| 項目名 (dt) | モデルフィールド | 抽出・変換ルール |
| :--- | :--- | :--- |
| **物件種別** | `propertyType` | 中古戸建 / 中古マンション / 売地 |
| **所在地** | `address` | 文字列抽出 |
| **交通** | `traffic` | 駅徒歩分数 |
| **土地面積** | `tochiMenseki` | `converter.parse_menseki` |
| **建物面積** | `tatemonoMenseki` | `converter.parse_menseki` |
| **築年月** | `chikunengetsu` | `converter.parse_chikunengetsu` (和暦「平成15年4月」対応) |
| **構造・階建て** | `kouzou`, `kaisu` | 文字列分割 |
| **権利形態** | `tochikenri` | 所有権等 |

### 掲載終了検知
- HTTP 404
- 本文中の「成約済」「お探しの物件は見つかりませんでした」検知で `ListingEndedException` 送出。

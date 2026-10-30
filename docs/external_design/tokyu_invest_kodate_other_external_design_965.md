# 東急リバブル投資用戸建て conditions-use=other からの判別抽出 外部設計書 (Issue #965)

## 1. 概要
東急リバブル投資用戸建て（`tokyu - invest_kodate`）の取得において、`conditions-use=other/` 一覧ページおよび詳細ページのインターフェース、フィルタリングフロー、データ連携仕様を定義する。

## 2. 外部インターフェース仕様

### 2.1 クロール開始URL
- **URL**: `https://www.livable.co.jp/fudosan-toushi/tatemono-bukken-all/conditions-use=other/`
- **ページネーション**: `?page={page_num}`
- **1ページあたりの件数**: 30件
- **総件数規模**: 約200〜250件（8〜9ページ）

### 2.2 Next.js 一覧データスキーマ
一覧ページの `<script id="__NEXT_DATA__">` 内にある `props.pageProps.propertyList` より以下を取得：
- `labelList`: ラベルオブジェクトのリスト（`listText`, `detailText` 等）
- `propertyDetail`: スペック文字列リスト（例: `['建物 45.88m²', '土地 42.46m²', '-', '1972年12月築', '木造 2階 地上2階建']`）
- `detailUrl`: 物件詳細URL（例: `/fudosan-toushi/C13263901/`）
- `price` / `salesPrice`: 販売価格数値

### 2.3 フィルタリングルール一覧

| 判定項目 | 抽出条件 | 除外（スキップ）条件 |
|---|---|---|
| ラベル種別 | `その他(土地・建物)` を含む | `ホテル`, `旅館`, `車庫・立体駐車場`, `店舗`, `事務所`, `倉庫`, `工場`, `寮・社宅`, `医療施設`, `マンション一棟売`, `アパート一棟売`, `ビル一棟`, `リゾートマンション・別荘` のいずれかを含む（複合ラベルのスラッシュ分割後も含む） |
| 戸数表記 | `-` または `1戸` または未記載 | `2戸` 以上の複数戸表記（アパート等） |
| 階数・構造 | 地上3階建以下（または階数未記載） | 地上4階建以上の中高層物件 |
| 詳細ページ | 土地面積が存在し、戸建てスペック | 土地面積なし、または物件名・タイトルに「マンション」「ビル」「アパート」「店舗」含有 |

## 3. シーケンス
```
ParseTokyuInvestKodateStartAsync
   │ (HTTP GET conditions-use=other/)
   ▼
TokyuInvestmentKodateParser.parsePropertyListPage
   │
   ├─ Next.js propertyList 走査
   │   ├─ 除外ラベル判定 (ホテル/ビル/マンション等) ──[該当]──> スキップ
   │   ├─ 「その他(土地・建物)」有無 ──[無]──> スキップ
   │   ├─ 戸数判定 (>=2戸) ──[複数戸]──> スキップ
   │   ├─ 階数判定 (>=4階) ──[高層]──> スキップ
   │   └─ [適合] ──> ListItem(url, price) 生成
   │
   ▼
ParseTokyuInvestKodateDetailFuncAsync
   │ (HTTP GET 物件詳細URL)
   ▼
TokyuInvestmentKodateParser._parsePropertyDetailPage
   │
   ├─ 二次ガード (タイトル/物件名チェック、土地面積チェック)
   └─ TokyuInvestmentKodate エンティティ生成・DB保存
```

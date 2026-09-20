# サイト構造: みずほ不動産販売 (Mizuho)

## 概要
- **サイト名:** みずほ不動産販売 (mizuho-re.co.jp)
- **ベースURL:** `https://www.mizuho-re.co.jp`
- **タイプ:** 居住用（中古マンション, 一戸建て, 土地）および投資用（一棟アパート・マンション、ビル等）

## URLパターン

### 1. スタート・検索結果 (一覧ページ)
- **中古マンション:** `https://www.mizuho-re.co.jp/buyers/search/area/type_Mansion/pref_13/list/`
- **一戸建て:** `https://www.mizuho-re.co.jp/buyers/search/area/type_House/pref_13/list/`
- **土地:** `https://www.mizuho-re.co.jp/buyers/search/area/type_Land/pref_13/list/`
- **投資用:** `https://www.mizuho-re.co.jp/investors/search/area/all_apartment-building-dormitory-office-store-warehouse-factory-land-other/pref_13/list/`
- **注意点:** 
  - 市区町村コード（`city_13102` 等）で指定したエリアに対象物件が0件の場合、みずほサーバーは検索結果0件画面ではなく **HTTP 404 (Not Found)** を返却する仕様となっている。そのため、巡回起点URLは都道府県レベル（`pref_13/list/`）を標準とし、404によるクローラー停止を防止する。
  - 一覧ページはAzure/ASP.NETのWAFおよびJavaScriptレンダリングを要求し、静的HTTPクライアントには`<title>403</title>`（JS有効化要求）を返す。そのため、一覧取得はPlaywright Stealthバイパス（`mizuho_bypass.py`）により動的実行する。

### 2. 詳細ページ
- **居住用URLパターン:** `https://www.mizuho-re.co.jp/buyers/property/[12桁数字]/`
- **投資用URLパターン:** `https://www.mizuho-re.co.jp/investors/property/[12桁数字]/`
- **特徴:** 物件詳細ページは静的HTML取得（aiohttp）で正常に取得可能。

## セレクタ (詳細ページ)

### 共通基本情報
| 項目 | セレクタ | 備考 |
| :--- | :--- | :--- |
| **物件名** | `.detailTitle .h3Title`, `.detailTitle h4` | NEWマーク等のimgを除去 |
| **価格** | テーブル内 `th="価格"` の `td` | 「ローンシミュレーション」等のボタン除去 |
| **所在地** | テーブル内 `th="所在地"` の `td` | 「周辺地図」等のボタン除去 |
| **交通** | テーブル内 `th="交通"` の `td` | |

### 物件スペック (`table`)
テーブル行に複数の `th` と `td` が並ぶ構造（例: `<tr><th>建物面積</th><td>...</td><th>土地面積</th><td>...</td></tr>`）。
`ParserBase._get_specs` により各ペアを辞書化して抽出。

#### 抽出ルール
- **尚早な検証の排除**: 基底パーサー（`MizuhoParser`）では `clean_parsed_item` を呼び出さず、各派生クラス（`MizuhoMansionParser`, `MizuhoKodateParser`, `MizuhoTochiParser`）が種別固有フィールド（間取り、面積、構造等）を設定し終えた後、または `_parsePageCore` / `baseParser` の末尾で一括検証する。
- **Playwright終了処理の安全性**: `mizuho_bypass.py` において、`async with async_playwright()` による自動終了後の二重クローズ例外を安全に処理し、偽陽性のERRORログを出力させない。

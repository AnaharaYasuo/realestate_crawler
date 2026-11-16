# LIFULL HOME'S サイト構造仕様書 (`site_structure_homes.md`)

## 1. サイト概要
- **サイト名**: LIFULL HOME'S / LIFULL HOME'S 不動産投資
- **会社識別コード**: `homes`
- **対象URL**:
  - マンション: `https://www.homes.co.jp/mansion/`
  - 一戸建て: `https://www.homes.co.jp/kodate/`
  - 土地: `https://www.homes.co.jp/tochi/`
  - 不動産投資: `https://toushi.homes.co.jp/`

---

## 2. 不動産投資 (`toushi.homes.co.jp`) のパーサー仕様

### 2.1 区分マンション判定とオーバーライド (`_apply_homes_unit_mansion_override`)
投資用物件一覧・詳細（`HomesInvestmentApartmentParser`）において、以下の条件のいずれかを満たす場合は「区分マンション（`Mansion`）」として扱い、専有面積をセットした上で土地面積（`tochiMenseki`）をクリアする：
1. タイトルまたは物件名に「区分」を含む。
2. テーブルに「所在階」が存在し、「階建」を含まない単一階数表記（例: 「3階」）である。
3. テーブルヘッダー「専有面積」「壁芯面積」に **数値としてパース可能な有効面積文字列**（例: 「52.01㎡」）が存在する。

> [!IMPORTANT]
> **専有面積が「不明」と記載されている一棟貸家・アパート物件の防衛**:
> ヘッダーに「専有面積(最小 - 最大)」が存在して値が「不明」となっている場合、これは区分マンションではなく土地・建物面積を持つ一棟投資物件（アパート・貸家等）である。
> 単にヘッダータグが存在するだけで無条件に区分判定してはならず、`converter.parse_menseki` により正の有効数値が抽出できた場合のみ区分判定を発動させ、土地面積（`tochiMenseki`）が意図せず消去されるバグを防止する（Issue #1544）。

### 2.2 項目マッピング表
| 項目名 | DBフィールド名 | 抽出方法・備考 |
|---|---|---|
| **物件名** | `propertyName` | `h1` または `div.mod-bukkenName` |
| **販売価格** | `price` | `converter.parse_price` |
| **土地面積** | `tochiMenseki` | `土地面積`, `敷地面積` から抽出 |
| **建物面積** | `tatemonoMenseki` | `建物面積`, `延床面積` から抽出 |
| **想定利回り** | `grossYield` | `converter.parse_ratio` |
| **想定年収** | `annualRent` | `満室想定年収`, `想定年収` から抽出 |

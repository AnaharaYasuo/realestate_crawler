# サイト構造: 野村不動産 (ノムコム・プロ)

## 概要
- **ベースURL**: `https://www.nomu.com/pro/`
### 抽出ルール
- **厳格な抽出**: 必須項目（物件名、価格、所在地、間取り、面積）が取得できない場合は、空欄をセットする代わりに例外を発生させ、エラーページとして保存する。
- **フォールバックの排除**: 以前使用されていた "-" などの安易なデフォルト値セットを廃止し、データの正確性を優先する。
- **種別**: 投資用 (居住用の `nomu.com` とは別ドメイン)
- **一覧ページ**: `https://www.nomu.com/pro/search/...`
- **詳細ページ**: `https://www.nomu.com/pro/bukken_local_id/...` または `bukken_id`

## 構造分析

### 一覧ページ (List Page)
- **物件項目セレクタ**: `.c_bldg_box.c_bldg_box__horizontal_l`
- **種別の判別**: 
  - `.tag.tag__category` のテキスト内容で判別 (例: "一棟マンション", "一棟アパート", "区分マンション")。
  - 検索条件 (`bldg_kind_ids[]`) で最初から絞り込むことも可能。

### 詳細ページ (Detail Page)
詳細ページの構造は、物件種別（一棟マンション、一棟アパート）にかかわらず一貫しています。
物件詳細情報を表示するために標準的なテーブルレイアウトが使用されています。

#### セレクタ (Selectors)
| 項目 | 取得戦略 (Selector Strategy) | 備考 |
|---|---|---|
| **価格 (Price)** | `.c_bldg_price` または `th:contains("価格") + td` | |
| **利回り (Yield)** | `.c_bldg_yield` または `th:contains("利回り") + td` | "現行利回り", "想定利回り" |
| **所在地 (Address)** | `th:contains("所在地") + td` | |
| **交通 (Traffic)** | `th:contains("交通") + td` | 生テキスト。複数行の場合あり。 |
| **土地面積 (Land Area)** | `th:contains("土地面積") + td` | |
| **建物面積 (Building Area)** | `th:contains("建物面積") + td` | |
| **構造 (Structure)** | `th:contains("構造") + td` | |
| **築年月 (Build Date)** | `th:contains("築年月") + td` | |

## 居住用モデルとの互換性
- **ドメイン**: 完全に異なります (`nomu.com/pro` vs `nomu.com`)。
- **スキーマ**: 価格や所在地などのフィールドは共通ですが、HTML構造は居住用サイトと異なります。データモデル (Pythonクラス) は基底クラス (`NomuraBase`) を継承して整合性を保つことができますが、パーサー (`Parser`) の実装はDOM構造の違いに対応する必要があります。

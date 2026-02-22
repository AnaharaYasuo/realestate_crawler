# サイト構造: 東急リバブル (Livable) - 居住用

## 概要
- **サイト名:** 東急リバブル (livable.co.jp)
- **ベースURL:** `https://www.livable.co.jp`
- **タイプ:** 居住用（中古マンション, 戸建, 土地）

## URLパターン

### 1. 検索結果 (一覧ページ)
- **中古マンション:** `https://www.livable.co.jp/kounyu/mansion/`
- **エリア検索:** `https://www.livable.co.jp/kounyu/mansion/tokyo/` など
- **注意点:** 一覧のレンダリングはクライアントサイド(JavaScript)で行われている可能性が高い。`data-url` 属性を持つ要素から非同期で部分HTMLを取得している挙動が見られる。
    - APIエンドポイント例: `/p0078/?template-name=...`

### 2. 詳細ページ
- **URLパターン (推定):** `https://www.livable.co.jp/kounyu/mansion/[PROPERTY_ID]/` または `/detail/[PROPERTY_ID]/`
    - ID形式: `C` で始まる英数字など (例: `CX820001` - 投資用での例だが居住用も類似と思われる)
    - ※正確なパターンはブラウザでのアクセス確認または動的レンダリング後のリンク取得が必要。

## セレクタ (詳細ページ)

### 共通ヘッダー情報
| 項目 | セレクタ | 備考 |
| :--- | :--- | :--- |
| **物件名** | `h1.title` | |
| **価格** | `.price .num` | |
| **住所** | `.detail-data-list dl` (dt="所在地") | |
| **交通** | `.detail-data-list dl` (dt="交通") | |

### 物件概要セクション
`div.m-status-table__wrapper` 内の `dl` リストを走査し、`dt` (項目名) と `dd` (値) をマッピングする。
### 抽出ルール
- **厳格な抽出**: 必須項目（物件名、価格、所在地、間取り、面積）が取得できない場合は、空欄をセットする代わりに例外を発生させ、エラーページとして保存する。
- **フォールバックの排除**: 以前使用されていた "-" などの安易なデフォルト値セットを廃止し、データの正確性を優先する。
- **セレクタ:** `div.m-status-table__wrapper dl`
- **項目名:** `dt`
- **値:** `dd` (内部のリンクから住所を分割抽出可能)

#### マンション (`TokyuMansion`)
| 項目名 (dt) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **間取り** | `madori` | |
| **専有面積** | `senyuMenseki` | |
| **所在階数** | `kaisu` | 例: 5階 / 地上10階建 |
| **建物構造** | `kouzou` | RC, SRCなど |
| **築年月** | `chikunengetsu` | |
| **バルコニー** | `balconyArea` | |
| **向き** | `saikou` | |
| **総戸数** | `soukosu` | |
| **管理会社** | `kanriKaisya` | |
| **管理方式** | `kanriKeitai` | |
| **管理費** | `kanrihi` | |
| **修繕積立金** | `syuzenTsumitate` | |
| **駐車場** | `tyusyajo` | |
| **分譲会社** | `bunjoKaisya` | |
| **施工会社** | `sekouKaisya` | |

#### 戸建 (`TokyuKodate`)
| 項目名 (dt) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **間取り** | `madori` | |
| **建物面積** | `tatemonoMenseki` | |
| **土地面積** | `tochiMenseki` | |
| **建物構造** | `kouzou` | |
| **築年月** | `chikunengetsu` | |
| **地目** | `chimoku` | |
| **用途地域** | `youtoChiiki` | |
| **接道状況** | `setsudou` | |
| **建ぺい率** | `kenpei` | |
| **容積率** | `youseki` | |
| **都市計画** | `kuiki` | |

#### 土地 (`TokyuTochi`)
| 項目名 (dt) | モデルフィールド | 備考 |
| :--- | :--- | :--- |
| **土地面積** | `tochiMenseki` | |
| **地目** | `chimoku` | |
| **地勢** | `chisei` | |
| **接道状況** | `setsudou` | |
| **建ぺい率** | `kenpei` | |
| **容積率** | `youseki` | |
| **用途地域** | `youtoChiiki` | |
| **都市計画** | `kuiki` | |
| **建築条件** | `kenchikuJoken` | |
| **国土法届出** | `kokudoHou` | |

## 注意点
- **Bot対策:** `429 Too Many Requests` が発生しやすいため、スクレイピング間隔に注意。
- **データ構造:** `dl > dt, dd` のリスト形式が主だが、一部の物件では異なるレイアウトの可能性があるため、`m-status-table__wrapper` を基準に探索することを推奨。

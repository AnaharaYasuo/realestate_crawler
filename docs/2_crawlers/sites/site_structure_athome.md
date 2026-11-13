# サイト構造定義書: アットホーム (athome)

## 1. 概要
- ポータル名: アットホーム (athome.co.jp)
- 対象物件種別: マンション (mansion), 一戸建て (kodate), 土地 (tochi), 投資用 (invest_apartment, invest_kodate, invest_other)
- パーサークラス: `AthomeParser`, `AthomeMansionParser`, `AthomeKodateParser`, `AthomeInvestmentApartmentParser`, `AthomeTochiParser`

## 2. スペック抽出仕様 (パーサー定義)

### 2.1 土地 (AthomeTochiParser)
- **建ぺい率 / 容積率**:
  - `specs` のキーとして「建ぺい率」「容積率」「建蔽率」を参照する。
  - アットホームの区画・土地詳細ページにおいて、`建蔽率/容積率`（または `建ぺい率/容積率` 等）として単一セル（例: ` -/- 60％・200％`）に結合されて表示される場合がある。
  - 単一キーが未抽出またはハイフンのみの場合、複合キー（`建蔽率/容積率` 等）から正規表現 `r'(\d+(?:\.\d+)?)\s*[%％]'` により建ぺい率・容積率を抽出し、`kenpeiStr`, `kenpei`, `yousekiStr`, `youseki` を補完する (Issue #1402)。

### 2.2 マンション (AthomeMansionParser)
- **所在階 / 階建**:
  - `specs` のキー（`階建/階`, `所在階/階建`, `所在階`, `階建` 等）から抽出。
  - スペックテーブルに所在階が存在しない場合、物件名またはタイトルから階数を正規表現マッチングする。
  - タイトル・スペックテーブルいずれにも所在階表記が存在せず、「タウンハウス」「テラスハウス」等の低層連棟住宅（`物件種目` がタウンハウス）である場合は、居住用戸建類似物件として `SkipPropertyException` でスキップし、パースエラー・必須項目欠損アラートの誤検知を防止する (Issue #1402)。

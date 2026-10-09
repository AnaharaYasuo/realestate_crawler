# 残留50課題解消およびデータバリデーション・パーサー適正化 要件定義書 (Issue #794)

## 1. 概要
データベース（`PropertyEvaluation`）に長期間残留している上位50パターンのデータ不整合課題を解消する。
これらには、実サイト側のHTMLレイアウト変更に伴う三井（td.table-header）、東急（dl直下および階数表記）、住友トラスト（旧クロールデータ未更新）の所在階・交通抽出不備、投資物件における利回り未記載物件の自動補正・未記載時（0.0%）の非エラー化、低価格（100万円未満）・超高額（20億円超〜50億円）物件の許容境界判定、明治築古物件の正当性許容、および過去クロール時の中断による未取得・掲載終了物件のクリーンアップが含まれる。

## 2. 目的とスコープ
* **目的**:
  1. 三井・東急・住友トラスト等における最新ページ構造に適合した交通・所在階・スペック抽出の強化。
  2. `data_validator.py` における投資利回り0.0%（未記載）・超高利回り、低価格（10万〜100万円未満）、築古物件（1800年代〜）の妥当性評価ルールの適正化。
  3. 掲載終了（404・募集終了）または旧パーサー取得時の欠損レコードに対する再評価・自己修復の一括実行。
* **スコープ**:
  - `src/crawler/package/parser/baseParser.py`
  - `src/crawler/package/parser/tokyuParser.py`
  - `src/crawler/package/utils/data_validator.py`
  - `src/crawler/tests/unit/test_heal_50_residual_issues_794.py`

## 3. 要件一覧
* **REQ-794-01**: `baseParser._getValueByLabel` において、`<th>`, `<dt>`, `<span>` に加え `<td>`（クラス `table-header` 等）もラベル要素として認識し、三井等の最新テーブル構造から「交通」やその他項目を確実に抽出すること。
* **REQ-794-02**: `tokyuParser._scrape_specs` において、`div.m-status-table__wrapper` や `#propertySummarySection dl` のみならず、詳細ページの全 `<dl>`（`index-module-scss-module__cv1pAa__detail` 配下等）からスペック属性を網羅的に抽出し、階数（`地上X階`）から所在階をフォールバック抽出可能とすること。
* **REQ-794-03**: `data_validator._check_investment_specs` において、`yieldRate` または `grossYield` が 0.0 の場合（サイト上で未記載または価格・賃料から算出不能な場合）は「利回り未記載」として扱い、異常値エラーとしないこと。また、100%超の利回りも投資ポータル（LIFULL HOME'S 等の超低価格ボロ戸建て・高利回り物件）の適正値として許容（上限1000%等）すること。
* **REQ-794-04**: `data_validator._validate_age` において、明治・大正期の古民家・登録有形文化財物件（1800年代〜）が存在するため、1850年以降の築年数を適正範囲として許容すること。
* **REQ-794-05**: `data_validator._check_mansion_specs` において、`floorType_kai`（数値）や `shozaikai`、`kaisu` に加え、`kaisuStr` に含まれる建物総階数（`地上X階`）がある場合、所在階が取得できない一棟・低層マンション物件でも致命的欠損とせず許容すること。
* **REQ-794-06**: 自己修復バッチにより、現在データベースに残存する50件の対象課題パターンを再評価・修復完了とすること。

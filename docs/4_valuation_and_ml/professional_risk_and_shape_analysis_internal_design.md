# プロ買い付け目線リスク・土地形状評価エンジン 内部設計書

## 1. モジュール構成とファイル配置

本機能は、以下のモジュール群により構成されます。

```
src/crawler/
├── package/
│   ├── models/
│   │   ├── evaluation.py            # PropertyEvaluation モデル（27新規カラム、update_from_gemini）
│   │   └── migrations/
│   │       └── 0053_propertyevaluation_bath_type_and_more.py  # スキーマ移行
│   └── utils/
│       ├── image_handler.py         # clean_images(plot_plan対応), analyze_property_images_with_gemini
│       ├── plot_shape_analyzer.py   # calculate_nta_irregular_discount 等の幾何計算エンジン
│       └── text_risk_analyzer.py    # analyze_text_risks (正規表現による決定論的リスク抽出)
├── scripts/
│   └── ops/
│       └── run_bulk_ml_evaluation.py # バルク評価バッチ (テキスト解析と画像解析のオーケストレーション)
└── tests/
    └── unit/
        ├── test_text_risk_analyzer.py # テキストリスク解析の全件単体テスト
        └── test_image_handler.py      # 画像ハンドラーおよびGemini連携テスト
```

---

## 2. クラス・関数詳細仕様

### 2.1 `src/crawler/package/utils/text_risk_analyzer.py`

#### 責務
テキスト情報（タイトル、備考、設備、交通等）から、法規・契約・設備リスクを決定論的に抽出する。

#### 主要関数
- `analyze_text_risks(text: str, chikunengetsu_str: str | None = None, kai: int | None = None, floor_max: int | None = None) -> dict`:
  - 入力テキストを正規化（半角・全角統一、小文字化）し、各リスク判定関数を実行。
- `is_psychological_defect(text: str) -> bool`:
  - 判定正規表現: `(告知事項あり|心理的瑕疵|特別募集|訳あり|事故物件|自殺|他殺|火災|不審死)`
- `is_as_is_condition(text: str) -> bool`:
  - 判定正規表現: `(契約不適合.*免責|現況有姿|現況渡し|現状渡し|瑕疵担保.*免責)`
  - 否定除外: `(免責[：:\s]*(?:なし|無|しない|除外))` がマッチする場合は `False` を返却。
- `is_boundary_unspecified(text: str) -> bool`:
  - 判定正規表現: `(境界非明示|公簿売買|公簿取引|境界確定.*なし|境界非復元)`
- `is_unbuildable(text: str) -> bool`:
  - 判定正規表現: `(再建築不可|建築不可|再建築不適格|連棟.*再建築|テラスハウス|43条但書|43条第2項)`
- `is_urbanization_control_area(text: str) -> bool`:
  - 判定正規表現: `市街化調整区域`
- `has_private_road_burden(text: str) -> bool`:
  - 判定正規表現: `(私道負担あり|私道持分なし|私道持分無|通行掘削承諾なし|私道のみ)`
- `is_sublease(text: str) -> bool`:
  - 判定正規表現: `(サブリース|一括借上|賃料保証|マスターリース)`
- `detect_bath_type(text: str) -> str`:
  - `\bub\b|ユニットバス|バス・トイレ別` ➔ `"unit_bath"`
  - `在来浴室|タイル張り浴室|バランス釜` ➔ `"tile_traditional"`
  - その他 ➔ `"unknown"`
- `detect_gas_type(text: str) -> str`:
  - `オール電化` ➔ `"all_electric"`
  - `都市ガス` ➔ `"city_gas"`
  - `プロパン|個別プロパン|集中プロパン` ➔ `"lpg"`
  - その他 ➔ `"unknown"`
- `detect_sewage_type(text: str) -> str`:
  - `下水|本下水|公共下水` ➔ `"public"`
  - `浄化槽|合併浄化槽|個別浄化槽` ➔ `"purification_tank"`
  - `汲取|汲み取り|くみ取り` ➔ `"cesspool"`
  - その他 ➔ `"unknown"`
- `_extract_elevator_and_stair(text: str, kai: int | None, floor_max: int | None) -> tuple[bool | None, bool | None]`:
  - EVあり/なしのテキスト判定（否定形「エレベーターなし」の優先判定）。
  - 所在階（`kai` または テキストから抽出）が3階以上かつEVなしの場合に `is_stair_only_3f_plus = True`。
- `is_old_earthquake_standard(chikunengetsu_str: str | None) -> bool | None`:
  - 和暦（昭和/平成/令和）および西暦の年月をパース。
  - 1981年5月以前建築（昭和56年5月以前）の場合に `True`、それ以降なら `False`、年月不明なら `None`。

---

### 2.2 `src/crawler/package/utils/image_handler.py`

#### 責務
物件画像群のフィルタリング、カテゴリ分類、優先度ソート、Gemini Vision 2.5 Flash へのプロンプト生成およびレスポンスパース。

#### 主要ロジック
1. **カテゴリ検出 (`_detect_image_category`)**:
   - `PLOT_PLAN_KEYWORDS = ['区画', '敷地配置', '土地図', '公図', '測量図', '実測図', '区画図']`
   - ラベルまたはURLに上記が含まれる場合は `'plot_plan'` を返却。
2. **優先度ソート & 上限選別**:
   - URL重複排除後、`{"plot_plan": 0, "layout": 1, "exterior": 2, "interior": 3}` に従ってソート。
   - 先頭最大5枚を抽出して画像バイト列を取得。
3. **Gemini Vision 2.5 Flash プロンプト**:
   - プロンプトにて、区画図、外観、内装の各観点を指定し、1つの構造化JSONレスポンスを要求。
   - `request_options={"timeout": 30.0}` でAPI無限待機を防止。
4. **レスポンスパース (`_parse_gemini_analysis_response`)**:
   - 正規表現 `\{.*\}` でJSON部を抽出しパース。
   - `shadow_area_ratio` が取得できた場合のみ `calculate_nta_irregular_discount` および `shape_score_100` を計算。未取得時は `None` を保持。
   - `foundation_crack_risk`, `water_leak_risk`, `exposed_pipes_risk` は Gemini レスポンスに存在しない場合は `None`（未判定）を維持し、誤って `False` にフォールバックさせない。

---

### 2.3 `src/crawler/package/models/evaluation.py`

#### 責務
評価結果モデル `PropertyEvaluation` に全27カラムを定義し、DB永続化およびディクショナリ更新を行う。

#### 定義フィールド一覧
- **土地形状**:
  - `shadow_area_ratio` (FloatField, null=True)
  - `passage_width` (FloatField, null=True)
  - `frontage_length_est` (FloatField, null=True)
  - `road_width_est` (FloatField, null=True)
  - `shape_score_100` (FloatField, null=True)
  - `nta_irregular_discount` (FloatField, null=True)
- **外観・造成・構造リスク**:
  - `retaining_wall_risk` (CharField, default='none')
  - `ground_elevation_diff_m` (FloatField, null=True)
  - `demolition_difficulty` (CharField, default='medium')
  - `utility_pole_risk` (CharField, default='none')
  - `foundation_crack_risk` (BooleanField, null=True)
  - `water_leak_risk` (BooleanField, null=True)
- **内装・配管・費用規模**:
  - `stair_steepness` (CharField, default='unknown')
  - `indoor_washing_machine_space` (CharField, default='unknown')
  - `exposed_pipes_risk` (BooleanField, null=True)
  - `renovation_budget_tier` (CharField, default='tier_medium')
- **テキストリスク**:
  - `is_psychological_defect` (BooleanField, default=False)
  - `is_as_is_condition` (BooleanField, default=False)
  - `is_boundary_unspecified` (BooleanField, default=False)
  - `is_unbuildable` (BooleanField, default=False)
  - `is_urbanization_control_area` (BooleanField, default=False)
  - `has_private_road_burden` (BooleanField, default=False)
  - `is_sublease` (BooleanField, default=False)
  - `bath_type` (CharField, default='unknown')
  - `gas_type` (CharField, default='unknown')
  - `sewage_type` (CharField, default='unknown')
  - `has_elevator` (BooleanField, null=True)
  - `is_stair_only_3f_plus` (BooleanField, default=False)
  - `is_old_earthquake_standard` (BooleanField, null=True)

#### `update_from_gemini(gemini_data: dict)`
- キーが存在し値が `None` でない場合のみフィールドを更新。
- 未判定（`None`）の項目が既定の `False` で上書き破壊されないようガード。

---

## 3. オーケストレーション (`run_bulk_ml_evaluation.py`)

1. **ステップ 1: 物件データ取得 & テキストリスク解析**:
   - `PropertyEvaluation` 対象物件の元データ（例: `MitsuiMansion`, `SumifuKodate` 等）を取得。
   - 物件名、備考、設備、現況、交通等を結合し、`analyze_text_risks` を呼び出し。
   - `chikunengetsu`（日付型）または `chikunengetsuStr` を渡して旧耐震判定。
   - 抽出された各テキストリスク項目を `PropertyEvaluation` に設定。
2. **ステップ 2: 画像解析（API上限内 & 画像存在時）**:
   - `check_daily_analysis_limit()` で当日実行枠を確認。
   - 物件画像が存在する場合、`clean_images` ➔ `analyze_property_images_with_gemini` を実行。
   - 結果を `evaluation.update_from_gemini(img_eval)` でモデルへ反映。
3. **ステップ 3: DB永続化 & ML評価継続**:
   - `evaluation.save()` を実行。

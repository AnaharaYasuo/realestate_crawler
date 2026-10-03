# プロ買い付け目線リスク・土地形状評価エンジン 要件定義・外部設計書

## 1. 目的と基本設計原則 (Issue #409)

本仕様は、プロの不動産買い付け業者（買取再販、建売デベロッパー、一棟収益投資家）の実務査定基準をシステムに導入し、物件の「隠れたコスト」「減価要因」「指値材料」を高精度に自動検出・数値化するための設計書です。

### 1.1 スクレイピング優先原則 (Scraping-First Principle)
1. **テキスト解析（ルールベース・コスト0・高速決定論）**:
   - 物件詳細、備考（`biko`）、土地権利（`tochikenri`）、現況（`genkyo`）、交通（`traffic`）、設備情報等から、法規・契約・インフラリスクを決定論的正規表現で高速抽出する。
2. **画像解析（Gemini Vision・お宝候補特化）**:
   - 一次スクリーニング合格物件（割安物件）のみを対象とし、テキストでは取得できない「区画図（かげ地・通路幅）」「外観（擁壁種別・道路高低差・基礎クラック・重機進入性）」「内装（配管露出・リフォーム費用規模）」に特化してGemini構造化JSONで抽出する。
3. **幾何解析エンジン連携**:
   - 抽出された土地形状数値（かげ地割合等）から既存の `plot_shape_analyzer.py` を呼び出し、国税庁不整形地補正率や総合画地スコア（0〜100点）を算出してML特徴量および投資判断データとして永続化する。

---

## 2. 収集・解析パラメータ仕様

### 2.1 テキストスクレイピング抽出項目（ルールベース）

| パラメータ名 | 型 | 説明 / 検知キーワード例 | コスト・リスク影響 |
|---|---|---|---|
| `is_psychological_defect` | Boolean | 心理的瑕疵（「告知事項あり」「心理的瑕疵」「特別募集」「訳あり」等） | 相場30〜50%減価 |
| `is_as_is_condition` | Boolean | 契約不適合責任免責（「契約不適合免責」「現況有姿」「瑕疵担保免責」等） | 買主全リスク負担、指値根拠 |
| `is_boundary_unspecified` | Boolean | 境界非明示・公簿売買（「境界非明示」「公簿売買」「境界確定なし」等） | 測量費用・越境紛争リスク |
| `is_unbuildable` | Boolean | 再建築不可・既存不適格（「再建築不可」「連棟」「テラスハウス」「43条但書」等） | 融資不可、50〜70%減価 |
| `is_urbanization_control_area` | Boolean | 市街化調整区域（「市街化調整区域」） | 一般人建築不可 |
| `has_private_road_burden` | Boolean | 私道負担・持分なし（「私道負担あり」「私道持分なし」「通行掘削承諾なし」等） | 掘削承諾料トラブル |
| `is_sublease` | Boolean | サブリース契約中（「サブリース」「賃料保証」「一括借上」等） | 解約困難、実質利回り低下 |
| `bath_type` | Char(20) | 浴室種別（`unit_bath`: ユニットバス / `tile_traditional`: 在来浴室 / `unknown`） | 在来浴室は土台腐食・シロアリリスク大 |
| `gas_type` | Char(20) | ガス種別（`city_gas`: 都市ガス / `lpg`: プロパン / `all_electric`: オール電化 / `unknown`） | プロパンは配管違約金・光熱費高 |
| `sewage_type` | Char(20) | 下水種別（`public`: 本下水 / `purification_tank`: 浄化槽 / `cesspool`: 汲み取り / `unknown`） | 浄化槽は入れ替え・維持費大 |
| `has_elevator` | Boolean | エレベーター有無（「エレベーター」「EV」有無検知） | 建物共用部利便性 |
| `is_stair_only_3f_plus` | Boolean | 3階以上エレベーターなし階段物件（所在階3階以上×EVなし） | 賃料10〜15%下落、入居敬遠 |
| `is_old_earthquake_standard` | Boolean | 旧耐震基準（1981年5月以前建築） | ローン控除不可、耐震改修要 |

### 2.2 画像解析（Gemini Vision）抽出項目

#### ① 区画図（`plot_plan`）
- `shadow_area_ratio`: かげ地割合（Float 0.0〜1.0）
- `passage_width`: 旗竿地路地状部分・通路幅（Float メートル）
- `frontage_length_est`: 推定間口長（Float メートル）
- `road_width_est`: 推定前面道路幅（Float メートル）
- `shape_score_100`: 総合画地幾何スコア（0〜100点）
- `nta_irregular_discount`: 国税庁不整形地補正率（0.60〜1.00）

#### ② 外観・敷地（`exterior`）
- `retaining_wall_risk`: 擁壁リスク（`none`: なし, `rc_legal`: 適法RC擁壁, `stone_masonry`: 間知石/玉石, `two_tier_illegal`: 二段擁壁/危険）
- `ground_elevation_diff_m`: 道路からの宅地盤高低差（Float メートル）
- `demolition_difficulty`: 重機進入性・解体難易度（`low`: 容易, `medium`: 通常, `high`: 狭小手壊し要）
- `utility_pole_risk`: 敷地内電柱・支線（`none`: なし, `pole`: 電柱あり, `guy_wire`: 黄色支線あり）
- `foundation_crack_risk`: 基礎構造クラック有無（Boolean）
- `water_leak_risk`: 軒天染み・漏水サイン有無（Boolean）

#### ③ 内装・間取り（`interior` / `layout`）
- `stair_steepness`: 階段勾配（`normal`: 通常, `steep`: 急勾配）
- `indoor_washing_machine_space`: 洗濯機置場の位置（`indoor`: 室内, `outdoor`: バルコニー/外置き, `unknown`: 不明）
- `exposed_pipes_risk`: 露出配管・老朽化配管サイン有無（Boolean）
- `renovation_budget_tier`: 想定リフォーム費用規模（`tier_none`: 0円, `tier_light`: 〜100万, `tier_medium`: 〜300万, `tier_heavy`: 〜600万, `tier_full`: 1000万超）

---

## 3. 画像分類（`PropertyImage`）の拡張

`PropertyImage.category` に以下を追加：
- `plot_plan`: 区画図・敷地配置図・公図・土地図面

キーワード判定：
- `PLOT_PLAN_KEYWORDS = ['区画', '敷地配置', '土地図', '公図', '測量図', '実測図', '区画図']`
- `LAYOUT_KEYWORDS` から `区画` を除外し、区画図が間取り図に混入するのを防止。

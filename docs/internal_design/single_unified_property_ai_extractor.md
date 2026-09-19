# 1物件1リクエスト完結型 AI属性抽出・建物マスタ連携 内部設計書
(Single Unified Property AI Extractor & Building Master Specification)

## 1. 背景と課題

不動産詳細ページには、価格推定（ヘドニックモデル・GBDT）の精度を決定づける多数の未取得属性が存在する。
- **建物・共用部**: 旧分譲主ブランド（パークコート、プラウド等）、スーパーゼネコン施工、中間免震、内廊下、エレベーター有無、24時間ゴミ出し、管理体制スコア
- **住戸個別**: 所在階比率（最上階/地下）、角住戸、ディスポーザー・食洗機・床暖房、水回りリノベ深度、心理的瑕疵（告知事項）
- **土地・戸建て**: 実効容積率（前面道路幅員制限による激変）、実質有効宅地面積（私道除外）、接道幅員・方位、私道負担、建築条件なし、更地渡し
- **権利・経済条件**: 所有権 vs 旧法借地権、月額地代（9.5万円等）、借地残存年数、オーナーチェンジ、隠れ月額固定費（CATV・ネット）

これらを個別のAPI呼び出し（「種別判定」「EV判定」「リノベ判定」など）で取得すると、**API呼び出し回数・コスト・ネットワーク遅延が物件数の数倍に膨張**する。
ユーザー指示に基づき、クローリング中および分析パイプラインにおいて**「1物件につき必ず1リクエストで全観点を一括抽出する」**アーキテクチャを確立する。

---

## 2. アーキテクチャ概要

```
[ 物件詳細ページ HTML / Nuxt SSR ]
               │
               ▼
[ 高速テキスト・スペック抽出器 (Parser / Regex) ]
  - title, specs(th/td, dt/dd), features(タグ), appeals(アピール文), nuxt_snippets
               │
               ▼
┌────────────────────────────────────────────────────────┐
│ SingleUnifiedPropertyExtractor (1物件1リクエスト完結)  │
│                                                        │
│  Step 1: ルールベース事前フィルタ                      │
│          - 完全既知データ（既存マスタ合致）はAIスキップ│
│                                                        │
│  Step 2: 単一統合プロンプト (Gemini 3.5 Flash)         │
│          - 1プロンプトに全テキストを集約               │
│          - 1回のリクエストで全カテゴリ一括JSON抽出     │
└──────────────────────────┬─────────────────────────────┘
                           │ 出力: 単一構造化JSON
                           ▼
┌────────────────────────────────────────────────────────┐
│ データ分配・格納・ML特徴量フィード                     │
│                                                        │
│  ├─ カテゴリA (建物共用部) ➔ [ BuildingMaster テーブル ]│
│  │   (同名・同住所の同一棟全物件へスペックを自動伝搬) │
│  │                                                     │
│  └─ カテゴリB〜D (個別・土地) ➔ [ PropertySpec / DB ] │
│      - 所在階比率、設備、リノベ、実効容積率、借地権等 │
│      ➔ LightGBM / CatBoost 特徴量ベクトルへ直結       │
└────────────────────────────────────────────────────────┘
```

---

## 3. 入力フォーマット & 出力JSONスキーマ

### 入力ペイロード（1リクエストに統合）
```text
Title: {propertyName}
Site: {site} / PropertyType: {property_type} / Price: {priceStr}
Specs: {specs_dict}
Features: {feature_tags_list}
Appeals: {appeal_texts_list}
Snippets: {nuxt_extracted_snippets}
```

### 出力JSONスキーマ
```json
{
  "property_overview": {
    "price_man_yen": "int (万円)",
    "property_type": "mansion | kodate | tochi | investment",
    "transaction_type": "string (仲介/売主/代理)",
    "occupancy_status": "空室 | 居住中 | 賃貸中(オーナーチェンジ) | 建築中"
  },
  "building_master": {
    "developer_brand": "string | null (三井パークコート, 野村プラウド等)",
    "developer_tier": "major_reputable | standard | unknown",
    "contractor_name": "string | null (清水建設, 鹿島等)",
    "contractor_tier": "super_general | major | local | unknown",
    "structure_type": "string | null (RC, SRC, S, 木造)",
    "earthquake_resistance": "免震 | 制震 | 耐震 | null",
    "total_units": "int | null",
    "elevator_available": "bool | null",
    "hallway_type": "内廊下 | 外廊下 | null",
    "garbage_disposal_24h": "bool | null",
    "management_type": "全部委託 | 一部委託 | 自主管理 | null",
    "manager_working_style": "常駐 | 日勤 | 巡回 | 管理員なし | null",
    "shared_facilities": ["string"]
  },
  "unit_specs": {
    "floor_number": "int | null",
    "total_floors": "int | null",
    "is_top_floor": "bool | null",
    "is_basement": "bool | null",
    "is_corner_unit": "bool | null",
    "main_orientation": "string | null (南, 東, 南西等)",
    "has_disposer": "bool | null",
    "has_dishwasher": "bool | null",
    "has_floor_heating": "bool | null",
    "has_bath_dryer": "bool | null",
    "has_water_purifier": "bool | null",
    "renovation_status": "未実施 | 一部リフォーム | フルリノベーション | 予定",
    "renovation_year_month": "string | null",
    "renovation_details": ["string"],
    "piping_replaced": "bool | null",
    "private_garden_area_m2": "float | null",
    "roof_balcony_area_m2": "float | null",
    "special_notes_psychological_defect": "bool (告知事項・心理的瑕疵)"
  },
  "land_kodate_specs": {
    "effective_land_area_m2": "float | null (私道除外実効面積)",
    "road_frontage_width_m": "float | null",
    "road_frontage_orientation": "string | null",
    "road_type": "公道 | 私道 | null",
    "road_contact_type": "一方 | 角地 | 両面道路 | 路地状(旗竿地)",
    "setback_required_area_m2": "float | null",
    "private_road_burden_area_m2": "float | null",
    "effective_floor_area_ratio_percent": "float | null (前面道路幅員制限適用後)",
    "building_condition": "無 | 有 | null",
    "land_delivery_condition": "更地渡し | 古家あり現況渡し | 権利床渡し | null",
    "house_builder_type": "注文住宅 | ハウスメーカー | 建売 | null"
  },
  "rights_economic_conditions": {
    "land_rights_type": "所有権 | 旧法借地権 | 普通借地権 | 定期借地権",
    "ground_rent_monthly_yen": "int | null (月額地代)",
    "lease_expiry_year_month": "string | null (借地満了年月)",
    "management_fee_monthly_yen": "int | null",
    "repair_reserve_fund_monthly_yen": "int | null",
    "other_monthly_expenses_yen": "int | null (CATV/ネット等)",
    "other_expenses_breakdown": "string | null"
  }
}
```

---

## 4. コスト・パフォーマンス制約

- **モデル選定**: Gemini 3.5 Flash（入力 $0.075 / 100万トークン、出力 $0.30 / 100万トークン）
- **トークン消費量**: 1物件あたり約800〜1,200入力トークン、約300出力トークン
- **コスト試算**:
  - 1物件あたり: 約 0.015 円
  - 月間10,000物件処理時: 約 150 円
  - 月間100,000物件処理時: 約 1,500 円
- **呼び出し回数制限**: **同一物件に対しては最大1回（1物件1リクエスト）を厳格に保証**。
---

## 6. 画像一括分析観点 ＆ 1物件1リクエスト・マルチモーダル仕様

### 6.1 画像分析の決定打観点（テキストでは分からない価格決定要素）

| 画像種別 | 具体的分析観点 | 価格インパクト | 判定基準・減価/加点 |
| :--- | :--- | :--- | :--- |
| **間取り図 (Layout)** | **柱・梁の食い込み（アウトフレーム度）** | **±5%** | 居室内に柱が張り出していないか、家具配置の有効面積 |
| | **廊下面積比率（デッドスペース）** | **-7%〜+3%** | 廊下が長すぎる「ウナギの寝床」vs センターイン効率間取り |
| | **サービスルーム（納戸）の有無** | **-5%〜-10%** | 採光基準不足による実質2LDK+S（表記上の部屋数乖離） |
| | **収納充足度（WIC, SIC, パントリー）** | **+3%〜+5%** | 大型収納の設置有無 |
| **外観・共用部 (Exterior)** | **外壁仕様・経年劣化度** | **-15%〜+10%** | 高級タイル貼り vs モルタル吹き付け、クラック・雨だれ・チョーキング |
| | **エントランス品格・車寄せ** | **+5%〜+10%** | ホテルライクな2層吹き抜け、重厚な御影石、車寄せの有無 |
| | **高低差・擁壁リスク（土地・戸建）** | **-10%〜-25%** | 道路面とのフラット性、古い大谷石・間知石擁壁の再構築リスク |
| **内装・設備 (Interior)** | **リノベ品質・内装使用感** | **-10%〜+20%** | 新規フルリノベ（建具・床・水回り一新） vs 経年使用感・汚れ・傷 |
| | **水回り設備グレード** | **+3%〜+7%** | 天板（クォーツストーン/人工大理石）、1620大型バス、タンクレストイレ |
| **眺望・日照 (View)** | **前棟被り（お見合い圧迫感） vs 永久眺望**| **-25%〜+20%** | 窓前にビル壁が塞がっているか、パークビュー・抜け感・東京タワー等 |
| | **日当たり・明るさ** | **±5%〜10%** | 自然光の入り具合、昼間の採光性 |

### 6.2 1物件1リクエスト・マルチモーダル統合設計
- **画像選定**: 1物件につき代表画像（間取り図1枚、外観1枚、LDK1枚、水回り1枚、眺望1枚、区画図1枚の**最大5〜6枚**）を自動ピックアップ。
- **1リクエスト完結**:
  選定した画像群を1つのマルチモーダル入力（`[img1, img2, ..., prompt]`）として Gemini 3.5 Flash に1回で送信。
  画像ごとにAPIを分けることは厳禁。
- **出力スキーマ (`visual_features`)**:
  ```json
  {
    "layout_outframe_score": 1.0 to 5.0,
    "layout_efficiency_score": 1.0 to 5.0,
    "has_service_room": bool,
    "exterior_luxury_score": 1.0 to 5.0,
    "exterior_deterioration_risk": bool,
    "interior_grade_score": 1.0 to 5.0,
    "is_fully_renovated_appearance": bool,
    "view_blockage_severity": "none" | "slight" | "severe",
    "view_scenic_premium": bool,
    "retaining_wall_risk": bool,
    "overall_visual_adjustment_percent": float (-30.0 to +25.0)
  }
  ```

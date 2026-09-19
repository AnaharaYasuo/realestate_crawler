# 建物マスタ（BuildingMaster）内部設計書
(Building Master Architecture & Specification)

## 1. 目的と責務

マンション・アパート等の集合住宅において、建物単位のスペック（共用部・構造・分譲主・施工会社・管理体制・EV・ゴミ出し等）は同一棟の全住戸で共通である。
各物件のクローリングごとにこれらを再スクレイピング・再AI判定する重複を排除し、
**一度判定した棟スペックを `BuildingMaster` に集約・永続化し、同名・同住所の全住戸へ自動伝搬（キャッシュ）させる**ことで、
APIコスト削減と推定精度の向上を同時に実現する。

---

## 2. データモデル仕様 (`package.models.building_master.BuildingMaster`)

| カラム名 | 型 | NULL | 説明・用途 |
| :--- | :--- | :--- | :--- |
| `id` | BigAutoField | NO | 主キー |
| `normalized_name` | CharField(255) | NO | 正規化建物名（全角半角統一、余計な階数・号室除去）[INDEX] |
| `raw_name` | TextField | NO | 原本建物名 |
| `normalized_address` | CharField(255) | NO | 都道府県＋市区町村＋町丁目まで正規化した住所 [INDEX] |
| `raw_address` | TextField | NO | 原本所在地 |
| `latitude` | DecimalField(9,6) | YES | 緯度 |
| `longitude` | DecimalField(9,6) | YES | 経度 |
| `developer_brand` | CharField(100) | YES | 旧分譲主・ブランド名（三井パークホームズ、野村プラウド等） |
| `developer_tier` | CharField(30) | YES | デベロッパー格付け (`major_reputable`, `standard`, `unknown`) |
| `contractor_name` | CharField(100) | YES | 施工会社（清水建設、鹿島建設、大林組、竹中工務店、大成建設等） |
| `contractor_tier` | CharField(30) | YES | ゼネコン格付け (`super_general`, `major`, `local`, `unknown`) |
| `structure_type` | CharField(50) | YES | 構造（RC, SRC, S, 木造等） |
| `earthquake_resistance` | CharField(30) | YES | 耐震性能 (`免震`, `制震`, `新耐震`, `旧耐震`) |
| `total_units` | IntegerField | YES | 総戸数（スケールメリット判定） |
| `total_floors` | IntegerField | YES | 地上総階数 |
| `built_year` | IntegerField | YES | 建築年（西暦） |
| `built_month` | IntegerField | YES | 建築月 |
| `elevator_available` | BooleanField | YES | エレベーター設置有無（True/False） |
| `elevator_count` | IntegerField | YES | エレベーター基数 |
| `hallway_type` | CharField(20) | YES | 共用廊下（`内廊下`, `外廊下`） |
| `garbage_disposal_24h` | BooleanField | YES | 24時間ゴミ出し可否 |
| `management_company` | CharField(150) | YES | 管理会社名 |
| `management_type` | CharField(30) | YES | 管理形態（`全部委託`, `一部委託`, `自主管理`） |
| `manager_working_style` | CharField(30) | YES | 管理員勤務形態（`常駐`, `日勤`, `巡回`, `なし`） |
| `repair_reserve_score` | FloatField | YES | 修繕積立金・管理組合健全性スコア |
| `shared_facilities_json` | TextField | YES | 共用施設リスト（宅配ボックス、ゲストルーム、ジム、ラウンジ等）JSON |
| `created_at` | DateTimeField | NO | 作成日時 (auto_now_add=True) |
| `updated_at` | DateTimeField | NO | 更新日時 (auto_now=True) |

### 複合一意制約 (Unique Constraint)
- `('normalized_name', 'normalized_address')`: 同一名かつ同町丁目の建物を一意特定。

---

## 3. 名寄せ・自動伝搬アルゴリズム (Building Resolver)

1. **正規化 (`normalize_building_key`)**:
   - 物件名から「3階」「301号室」「【仲介】」「即入居可」などの部屋番号・広告文言を除去。
   - 英数字・カタカナを正規化（全角英数 ➔ 半角、半角カナ ➔ 全角）。
   - 住所から都道府県・市区町村・町丁目（○丁目まで、番地枝番は柔軟マッチ）を抽出。
2. **マスタ検索 (`get_or_create_building`)**:
   - 既存マスタにヒットした場合:
     - マスタのスペック（EV、内廊下、免震、分譲ブランド、施工、総戸数、管理形態等）を物件モデルへ**即時注入**。
     - AIによる建物共用部の抽出は**完全スキップ（0リクエスト）**。
   - 未ヒットの場合:
     - 1物件1リクエスト抽出器 (`SingleUnifiedPropertyExtractor`) が抽出した `building_master` 辞書を元に新規 `BuildingMaster` レコードを作成。
     - 以降の同一棟物件はすべてこのレコードを参照。

---

## 4. 特徴量生成パイプライン (`features.py`) との統合

`BuildingMaster` の各フィールドをML入力特徴量にエンコード：
- `bm_brand_tier_score`: major_reputable=1.0, standard=0.5, unknown=0.0
- `bm_contractor_tier_score`: super_general=1.0, major=0.6, local=0.3, unknown=0.0
- `bm_is_seismic_isolated`: 免震=1.0, 制震=0.5, その他=0.0
- `bm_has_elevator`: 有=1.0, 無=-1.0, 不明=0.0
- `bm_is_indoor_hallway`: 内廊下=1.0, 外廊下=0.0, 不明=0.0
- `bm_has_24h_garbage`: 24時間ゴミ出し可=1.0, 不可=0.0
- `bm_management_quality_score`: 全部委託+常駐=1.0, 全部委託+日勤=0.7, 巡回=0.3, 自主管理=-0.5

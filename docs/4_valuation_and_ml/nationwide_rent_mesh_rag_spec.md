# 全国賃料・需給メッシュ＆キャップレートデータ収集・ハイブリッド蓄積仕様書 (nationwide_rent_mesh_rag_spec)

## 1. 目的
全国47都道府県の地域メッシュ（都道府県・市区町村・町丁目・駅）における**家賃相場・需給バランス**、ならびに地域・アセットクラスごとの**期待利回り（キャップレート）・実勢表面利回り・空室率・標準運営経費率（OPEX率）**を網羅的に収集する。

収集データは「**テキスト・原本はクラウドストレージ（GCS）に継続保存し、構造化した数値はデータベース（Cloud SQL）のマスタテーブルに保持する**」ハイブリッド二層アーキテクチャで管理する：
1. **Cloud Storage 原本・テキスト層（`GCS_BUCKET_NAME`）**: 生HTMLアーカイブ（`rag/raw/rent_mesh/`）、構造化Markdown/JSONLテキスト（`rag/curated/statistics/`）、取得台帳（`rag/manifest/rent_mesh_sources.jsonl`）を保持し、将来の再パースおよびAI定性評価RAG（`rent_mesh_rag`）の双方に供する。
2. **Cloud SQL 構造化数値マスタ層（`rent_market_potential` / `cap_rate_benchmark_potential`）**: AI（LLM）を一切介さずミリ秒単位・O(1)インメモリキャッシュ（`reference_data.py`）で期待表面/実質利回りおよび10年DCF理論価格を算出するための決定論的数値基盤として保持する。

## 2. 対象データソース選定・既存GCS棚卸し・除外方針

### 2.1 収集対象ソース（取れる限りの公開統計・ポータル・機関投資家指標・自社DB実測値を統合）

#### A. 家賃相場・面積単価データソース（➔ GCS原本/テキスト ＋ `RentMarketPotential`）
1. **SUUMO 家賃相場 (`suumo_soba`)**: 全国47都道府県の市区町村（`/sc_<city>/`）および駅（`/ek_<code>/`）ごとに、建物種別3区分（`ts=1`: 賃貸マンション、`ts=2`: 賃貸アパート、`ts=3`: 一戸建て・その他）× 間取り13区分（ワンルーム〜4LDK以上）の家賃相場を取得。
2. **at home 家賃相場 (`athome_souba`)**: 全国47都道府県の市区町村・主要駅（地方都市・郡部・戸建賃貸含む）の間取り別・建物種別家賃相場を取得。
3. **LIFULL HOME'S 家賃相場 (`homes_price`)**: 全国47都道府県の市区町村・路線・駅別の間取り別家賃相場を取得。
4. **総務省 統計局 e-Stat『住宅・土地統計調査』 (`estat_housing`)**: 全国都道府県・主要都市の構造区分（木造・非木造）別1㎡あたり公的家賃単価ベースラインを同期。
5. **自社DB 収益物件実測集計 (`internal_db`)**: 自社クローラーで収集済みの全社収益物件テーブル（`*InvestmentApartment` / `*InvestmentKodate` / `*Investment`）の年間想定賃料・建物面積・構造・築年から、外れ値除外後の実測月額㎡単価中央値を集計。

#### B. キャップレート（期待/実勢利回り）・空室率・需給データソース（➔ GCS原本/テキスト ＋ `CapRateBenchmarkPotential`）
1. **LIFULL HOME'S『見える！賃貸経営』 (`homes_toushi`)**: 全国都道府県・市区町村（`/owner/<pref>/city<code>/`）・駅（`/owner/<pref>/eki<code>/`）ごとの実勢表面利回り（%）、賃貸用住宅空室率（%）、住宅全般空室率（%）、および入居希望検索回数と掲載物件数の需給バランス指標を取得。
2. **JAPAN-REIT.COM 上場REIT指標 (`japan_reit`)**: 全上場J-REIT銘柄の分配金利回り（%）、NAV倍率、時価総額、用途区分（住宅・オフィス・商業・物流・ホテル・総合）を取得し、アセットクラス別インプライド・キャップレートおよび長期国債スプレッド指標を算出。
3. **日本不動産研究所『不動産投資家調査』基準 (`jrei_survey`)**: 全国主要政令市・都市圏・地方圏 × アセットタイプ（ワンルーム住宅・ファミリー住宅・商業店舗等）別の期待利回り（NCFベース実質利回り）・取引利回り・標準経費率（OPEX率）・10年国債利回りスプレッド基準値を同期。
4. **自社DB 収益物件実測利回り集計 (`internal_db`)**: 自社DB蓄積済みの収益物件データから、市区町村・駅・構造別の実勢表面利回り中央値およびサンプル数を集計。

### 2.2 既存クラウドストレージ棚卸し結果（Issue #1354 監査記録）
- 監査対象バケット：`realestate-images-sumifu-prod` ほかプロジェクト内全4バケット
- 確認結果：
  - `rag/curated/law/*.jsonl`（法令・条例データ 58件）および `rag/danchou_kb_full.jsonl`（定性ブログ記事 2,421件）は存在するが、構造化された地域別家賃相場・キャップレートデータは未格納。
  - `ml_models/mkt_comparison_master.joblib` は売買物件の価格比較辞書であり、賃貸相場・利回り統計ではない。
  - `rag/raw/rent_mesh/`、`rag/curated/statistics/`、`rag/manifest/` はいずれも0件であったため、本仕様に基づき新規収集・蓄積を行う。

### 2.3 除外ソース（コンプライアンス・安定運用ガード）
- **健美家（Kenbiya: `kenbiya.com` / `*.kenbiya.com`）**: アクセス制限（WAF/レート制限・ブロックリスク）が厳格なため収集対象から完全除外し、URL検証時に `KenbiyaBlockedException` を送出してリクエスト自体を遮断する。

## 3. ハイブリッド・ストレージ構成

### 3.1 Cloud Storage 構成（`GCS_BUCKET_NAME` 配下：テキスト・原本の永続化）
既存の `docs/4_valuation_and_ml/rag_knowledge_ingestion_spec.md` に準拠する。

```text
rag/
  ├── raw/rent_mesh/                             # 1. 取得HTML/テキスト原本（全国アーカイブ・再パース用）
  │   └── source=<source_id>/
  │       └── pref=<prefecture>/
  │           └── <yyyymmdd>/
  │               └── <target_slug>.html
  │
  ├── curated/statistics/                        # 2. 構造化Markdown/JSONLテキストチャンク
  │   └── pref=<prefecture>/
  │       └── <chunk_id>.jsonl
  │
  └── manifest/rent_mesh_sources.jsonl           # 3. 取得状況台帳（URL, GCSキー, DB反映件数, 取得日時）
```

### 3.2 Cloud SQL 構造化マスタテーブル構成（高速数理推論・DCF用）
1. **`RentMarketPotential` (`rent_market_potential`)**:
   - キー粒度: `(prefecture, city, station_name, town_name, building_type, layout_type, age_band, source)`
   - 保持指標: 月額家賃相場 `monthly_rent_yen`（円）、基準専有面積 `standard_area_sqm`（㎡）、月額㎡単価 `rent_per_sqm`（円/㎡）、サンプル数 `sample_count`、GCS原本キー `gcs_raw_key`
2. **`CapRateBenchmarkPotential` (`cap_rate_benchmark_potential`)**:
   - キー粒度: `(prefecture, city, station_name, asset_type, source)`
   - 保持指標: 期待/実勢表面利回り `expected_gross_yield`（%）、期待実質利回り `expected_net_cap_rate`（%）、標準経費率 `standard_opex_ratio`（%）、賃貸用空室率 `rental_vacancy_rate`（%）、住宅全般空室率 `total_vacancy_rate`（%）、10年国債スプレッド `jgb_spread_bps`（bps）、需給バランス指数 `demand_supply_score`、GCS原本キー `gcs_raw_key`

## 4. チャンクスキーマ定義（GCS `curated/statistics/` JSONL規格）
各メッシュ単位のテキストチャンク（`.jsonl`）は以下のフィールドを保持する。

| フィールド名 | 型 | 必須 | 説明 |
| :--- | :--- | :---: | :--- |
| `id` | string | ○ | 一意ID（例: `rent_mesh_suumo_soba_a1b2c3d4e5f6_202611`） |
| `source_id` | string | ○ | ソース識別子（`suumo_soba`, `athome_souba`, `homes_price`, `homes_toushi`, `japan_reit`, etc.） |
| `category` | string | ○ | `statistics` 固定 |
| `kind` | string | ○ | `fact` 固定 |
| `title` | string | ○ | チャンクタイトル |
| `target_types` | list[str] | ○ | 対象物件種別 |
| `region` | string | ○ | 地域名称（例: `東京都千代田区東京駅`） |
| `valid_from` | string | ○ | 有効開始日（`YYYY-MM-DD`） |
| `valid_to` | string | ○ | 有効終了日 |
| `url` | string | ○ | 取得元URL |
| `license` | string | ○ | `derived_summary` |
| `summary_only` | bool | ○ | `false` |
| `confidence` | float | ○ | 信頼度スコア（0.9〜1.0） |
| `essence` | string | ○ | 短縮サマリ（最大350文字） |
| `body_text` | string | ○ | 構造化Markdown本文 |
| `metadata` | dict | ○ | 都道府県・市区町村・駅・抽出された数値レコード件数・`gcs_raw_key` 等 |

## 5. 収集・変換・同期パイプラインのアーキテクチャ
1. **安全なフェッチャー＆GCSアーカイバ (`MarketDataCrawler` / `SafeMeshFetcher`)**:
   - 健美家ドメインの事前ブロック（`KenbiyaBlockedException`）、セッション再利用（`requests.Session`）、レート制限（ジッター付きスリープ）を実施。
   - 取得した生HTMLテキストを即座に `rag/raw/rent_mesh/` へ保存し、`RentMeshPipeline` で `rag/curated/statistics/` にもJSONLチャンクを保存。
   - クラウドストレージ上の `rag/raw/rent_mesh/` に保存済みのHTML原本からDBテーブルを再構築する `reingest_from_gcs_raw` 機能も備える。
2. **決定論的テーブルパーサー群 (`package.rag_ingest.market_data_parsers`)**:
   - AI（LLM）を一切使用せず、BeautifulSoupによる純粋DOM解析（1ページあたり純処理時間 `< 1,000ms`）で各サイトの家賃相場・空室率・利回り・REIT指標を数値リストへ変換。
   - 間取り別の標準専有面積換算テーブル（`1R: 18㎡`, `1K: 22㎡`, `1DK: 28㎡`, `1LDK: 40㎡`, `2K: 32㎡`, `2DK: 42㎡`, `2LDK: 55㎡`, `3DK: 55㎡`, `3LDK: 70㎡`, `4LDK+: 85㎡`）により、月額家賃（万円）から一貫した `rent_per_sqm`（円/㎡）を算出。
3. **一括同期ランナー＆インメモリ参照キャッシュ (`sync_rent_and_cap_rate_potentials.py` / `reference_data.py`)**:
   - `ON DUPLICATE KEY UPDATE` / `bulk_create(update_conflicts=True)` により高速・冪等にDBへ一括反映。
   - `reference_records.py` に `@dataclass(slots=True, frozen=True)` の `RentMarketRecord` / `CapRateBenchmarkRecord` を定義し、`reference_data.py` で `駅 ➔ 市区町村 ➔ 都道府県` の階層フォールバック検索API（`query_rent_market_potential` / `query_cap_rate_benchmark`）を提供する。

## 6. 品質・テスト計画 (TDD)
- `test_rent_and_cap_rate_foundation.py`:
  - 各ポータル（SUUMO・at home・HOME'S賃貸・HOME'S見える賃貸経営・JAPAN-REIT.COM）の構造化パース精度検証および純処理時間 `< 1,000ms/件` アサーション。
  - 動的生HTML取得による実サイト疎通・パーススモーク検証。
  - `KenbiyaBlockedException` による健美家URL完全遮断テスト。
  - GCS原本保存＋JSONL保存＋マニフェスト追記およびGCS原本からのDB再構築テスト。
  - `RentMarketRecord` / `CapRateBenchmarkRecord` のインメモリキャッシュ（非Djangoモデル `slots=True` 検証）および `駅 ➔ 市区町村 ➔ 都道府県` カスケード検索テスト。

## 7. AI定性評価（report_generator）および非AI数理DCF（Issue #1349）との連携
- **非AI数理DCF・価格推定（Issue #1349）**: Cloud SQL の `RentMarketPotential` / `CapRateBenchmarkPotential` のみを使用し、AI呼び出しゼロで高速・決定論的に期待利回りおよび10年DCF理論価格を算出する。
- **AI定性レポート（Issue #1323 `report_generator.py`）**: GCS `rag/curated/statistics/` に蓄積されたテキストチャンクを `package.ml.rent_mesh_rag` 経由でプロンプトへ注入し、客付け難易度・需給コメントを補強する。

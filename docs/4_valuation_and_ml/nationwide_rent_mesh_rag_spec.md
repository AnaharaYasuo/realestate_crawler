# 全国賃料・需給メッシュデータ収集・RAG蓄積仕様書 (nationwide_rent_mesh_rag_spec)

## 1. 目的
全国47都道府県の細かい地域メッシュ（市区町村・町丁目・駅・徒歩圏）における賃料相場および需給バランス（間取り別相場、駅徒歩別格差、設備需要、供給傾向等）のまとめページを幅広く収集し、原本アーカイブおよび構造化MarkdownチャンクとしてGoogle Cloud Storage (GCS) に蓄積する。
これにより、既存の RAG ナレッジベース（`danchou_rag`、`rag_knowledge_ingestion_spec.md`）と完全連携し、高精度な地域文脈把握および投資・賃貸査定レビューを可能にする。

## 2. 対象データソース選定と除外方針
- **対象ソース**:
  1. **LIFULL HOME'S**（全国47都道府県、市区町村・町丁目・駅別家賃相場）
  2. **SUUMO**（主要都市〜地方中核都市、駅別相場・専有面積別・人気設備需給）
  3. **at home**（地方都市・郡部まで網羅、一戸建て賃貸相場・流通動向）
  4. **楽待（Rakumachi）**（収益物件の地域別利回り相場）
  5. **国土交通省 不動産情報ライブラリ**（公的成約・地価・将来推計人口メッシュ）
- **除外ソース**:
  - **健美家（Kenbiya）**：アクセス制限（WAF/レート制限・ブロックリスク）が厳格なため、安定運用の観点から収集対象から完全除外する。

## 3. ストレージ構成（GCS: `GCS_BUCKET_NAME` 配下）
既存の `docs/4_valuation_and_ml/rag_knowledge_ingestion_spec.md` に完全準拠する。

```text
rag/
  ├── raw/rent_mesh/                             # 1. 取得HTML/原本（全国アーカイブ）
  │   └── source=<source_id>/
  │       └── pref=<prefecture>/
  │           └── <yyyymmdd>/
  │               └── <city_or_station_id>.html
  │
  ├── curated/statistics/                        # 2. 構造化Markdownチャンク（RAG検索対象）
  │   └── rent_mesh_<prefecture>.jsonl           # 1行1メッシュ（駅/市区町村/町丁目）
  │
  └── manifest/rent_mesh_sources.jsonl           # 3. 取得状況台帳（URL, 最終取得日, 有効期限, 成功フラグ）
```

## 4. チャンクスキーマ定義（既存 RAG 規格準拠）
各メッシュ単位のレコード（JSON Lines: `.jsonl`）は以下のフィールドを保持する。

| フィールド名 | 型 | 必須 | 説明 |
| :--- | :--- | :---: | :--- |
| `id` | string | ○ | 一意ID（例: `rent_mesh_homes_tokyo_meguro_nakameguro_202611`） |
| `source_id` | string | ○ | ソース識別子（`homes_market`, `suumo_market`, `athome_market`, etc.） |
| `category` | string | ○ | `statistics` 固定 |
| `kind` | string | ○ | `fact` 固定 |
| `title` | string | ○ | チャンクタイトル（例: `東京都目黒区中目黒・中目黒駅周辺の賃料相場と需給データ（2026年11月）`） |
| `target_types` | list[str] | ○ | 対象物件種別（`["一棟アパート", "一棟マンション", "区分マンション", "戸建"]`） |
| `region` | string | ○ | 地域名称（例: `東京都目黒区中目黒`） |
| `valid_from` | string | ○ | 有効開始日（`YYYY-MM-DD`） |
| `valid_to` | string | ○ | 有効終了日（鮮度管理用: 取得日から30日〜90日後） |
| `url` | string | ○ | 取得元URL |
| `license` | string | ○ | `derived_summary` 等 |
| `summary_only` | bool | ○ | `false` |
| `confidence` | float | ○ | 信頼度スコア（通常 0.9〜1.0） |
| `essence` | string | ○ | LLMがプロンプトで最優先参照する短縮サマリ（200〜400文字） |
| `body_text` | string | ○ | 構造化Markdown本文（間取り別相場、駅徒歩別相場、需給動向、人気条件） |
| `metadata` | dict | ○ | 検索・フィルタ用構造化データ（都道府県、市区町村、駅、代表間取りの中央値等） |

## 5. 収集・変換パイプラインのアーキテクチャ
1. **シードURLディスパッチャ (`RentMeshSeedDispatcher`)**:
   - 全国47都道府県の市区町村・主要駅の一覧に基づき、各対象サイトの相場・市場動向URLを生成。
2. **安全なフェッチャー (`SafeMeshFetcher`)**:
   - 健美家を除外し、対象サイトへの連続アクセスを防止するレート制限（1〜2秒のジッター付きインターバル）とセッション再利用。
3. **HTML ➔ Markdown/要約抽出エンジン (`MeshHtmlToMarkdownExtractor`)**:
   - 余分なヘッダー・フッター・広告・スクリプトを除去し、相場テーブル（間取り別、徒歩別、築年別）と市況解説文をクリーンなMarkdownテキストおよびJSONメタデータに変換。
4. **GCS同期マネージャー (`RentMeshGcsUploader`)**:
   - 取得原本（HTML）を `rag/raw/rent_mesh/` へ、変換後JSONLを `rag/curated/statistics/` へストリーミング保存。
   - `manifest/rent_mesh_sources.jsonl` を更新。

## 6. 品質・テスト計画 (TDD)
- **単体テスト**:
  - `test_rent_mesh_schema.py`: 生成されたチャンクが `rag_knowledge_ingestion_spec.md` の必須項目をすべて満たしているか検証。
  - `test_mesh_html_extractor.py`: サンプルHTMLからノイズが除去され、相場情報が欠落なくMarkdown化されるかをテスト。
  - `test_kenbiya_exclusion_guard.py`: 健美家のURLやドメインが設定・キューに含まれた場合に自動検出し、例外を発生させてアクセスを拒絶する安全ガードテスト。

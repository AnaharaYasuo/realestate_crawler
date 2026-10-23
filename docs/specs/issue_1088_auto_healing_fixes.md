# Issue 1088 Specification: Auto-Healing Pipeline & Data Quality Fixes

## 1. 概要 (Overview)
クローリング監視レポートおよび自動修復（`/auto-healing`）指示書（`Temp/auto_heal_instruction.json`）において検出された上位の障害・異常事象（三井・アットホーム・大京・大和・トータテ・健美家等における交通・所在階・価格異常・掲載終了物件残存問題）を網羅的かつ根本的に修復する。

## 2. 根本原因と修復仕様 (Root Cause & Solutions)

### 2.1 三井のリハウス（Mitsui）
- **事象**:
  1. `rehouse.co.jp/buy/mansion/bkdetail/` に利回り表記等が存在する場合、`PropertyTypeDetector` により `apartment` と判定され `MitsuiInvestmentApartmentParser` に動的切り替えされるが、三井の投資区分モデルには元々 `traffic` 等の抽出が不足していた、または `MitsuiMansion` とのクロステーブル不整合を起こしていた。
  2. マンションURL (`/buy/mansion/`) でありながら区分マンション（専有部）として提供される物件に対し、利回り文言の単一キーワードヒットのみで `apartment`（一棟アパート扱い）へ誤ルーティングされていた。
- **仕様**:
  - `MansionParserBase` において、`sectional_unit_guard_enabled = True` を三井パーサー (`MitsuiMansionParser`) でも明示的に有効化、または `/buy/mansion/` URLからの区分所有物件は `sectional_unit` ガードにより一棟アパートへの過剰誤切り替えを抑止。
  - `MitsuiInvestmentApartmentParser` / `MitsuiInvestmentKodateParser` の `_parseTrafficLines` や各フィールド抽出を堅牢化し、投資モデル側でも `traffic` を完全抽出。

### 2.2 大京・大和・トータテの所在階未抽出 (Floor Extraction)
- **事象**:
  - `DaikyoMansion`（5,079件）、`DaiwaMansion`（491件）、`TotateMansion`（91件）等で `必須項目欠損 (所在階が未抽出)` が多発。
  - スペック表のキー名（大京: `所在階/建物階数`、大和: `階数/階`、トータテ: `階数` 等）や、`kaisuStr` に入った値（例: `'4階/地上4階'`、`'（地下2階）地上40階建 /8階'`、`'7階'`）から `floorType_kai` へのパースが行われていなかった。
- **仕様**:
  - 各パーサーのスペックキー定義および `_parseFloor` / `_parse_floors` を補正。
  - `baseParser.clean_parsed_item` 内で、`floorType_kai` が None かつ `kaisuStr` が存在する場合、正規表現により所在階（部分階）を自動抽出・補完するセーフティネットを導入。
  - `PropertyDataValidator._has_located_floor` において、`4階/地上4階` や `7階` など明確に所在階を示す文字列を所在階として正当に判定。

### 2.3 アットホーム（Athome）
- **事象**:
  - `/buy_other/` URLが `AthomeTochiParser` にルーティングされ、`tochiMenseki` が None となりパースエラーおよび面積0㎡異常を誘発。
  - 一部物件で価格1万円（`priceStr='1'`）などの異常値がそのまま入っていた。
- **仕様**:
  - `url_router.py`: `buy_other/` は土地ではなく `AthomeInvestmentApartmentParser` / `AthomeInvestmentApartment` に正しくルーティング。
  - `AthomeInvestmentApartmentParser`: `使用部分面積`（34.54m² 等）を `tatemonoMenseki` / `senyuMenseki` に確実にマッピング。

### 2.4 健美家（Kenbiya）および掲載終了物件 (Kenbiya & Lifecycle)
- **事象**:
  - 健美家などの掲載終了・404/403物件において、過去に誤って取得されたヘルプ文（「単位は「万円」。」等）による価格1.0万円・面積1.0㎡の古い `PropertyEvaluation` レコードが `delisted_at` 設定後も `needs_parser_fix=True` のまま残り、オートヒール指示書を汚染。
  - 健美家パーサーの `_is_excluded_spec_container` / `_clean_spec_value` において、ヘルプ・凡例説明文（「を表示。」で終わる文等）をスペック値として採用しないよう強化。
- **仕様**:
  - `api.py` の `_sync_persist_delisted`: 物件が掲載終了（delisted）となった場合、`needs_parser_fix = False` にクリア。
  - `auto_heal_parsers.py`: `is_published=True` の公開中物件のみを修復対象とする原則を厳格化。

## 3. テスト計画 (Verification Plan)
- 単体テスト:
  - 三井、大京、大和、トータテ、アットホーム、健美家のパーサー単体テスト（pytest）。
  - `baseParser` の `floorType_kai` 自動抽出テスト。
  - `PropertyDataValidator` の検証テスト。
- 動的検証:
  - 該当URLでの動的取得・パース実行検証。

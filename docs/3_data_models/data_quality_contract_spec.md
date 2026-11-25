# Issue #1586: クローラー出力〜ML入力間のデータ品質契約（Data Contract）とドリフト監視 仕様書

## 1. 概要 (Overview)
『プロダクト品質管理の実践ガイド』第17章（17.2 データ品質契約とドリフト監視）に基づき、エラーにならずに誤データ（必須項目欠損、過疎・未知駅、価格・面積外れ値、キーワード誤爆）がDBや機械学習パイプラインへ流れ込むサイレント障害を防止する。

## 2. データ品質契約仕様 (Data Contract Specifications)
- `src/crawler/package/validation/data_contract.py`:
  - `validate_record_contract(record: dict)`:
    - 必須フィールド（URL, 価格, 所在地, 物件種別）の存在と型検証（Fill-Rate 100%）。
    - 妥当範囲検証（価格 > 0 かつ価格 < 100億円、面積 > 0 かつ面積 < 10,000㎡等）。
    - 駅情報整合性（未知駅・極小過疎駅の検知）。
- ドリフト・異常データ検知時は例外送出または安全隔離を行い、MLパイプラインの汚染を防ぐ。

## 3. テスト計画 (TDD)
- `src/crawler/tests/test_data_contract.py`:
  - 正常な物件データの契約通過テスト。
  - 欠損値（価格NULL、URL不正）、異常値（負数価格、極大面積）の検知・拒絶テスト。

## 4. `PropertyEvaluation` と実物件テーブル間の参照整合性契約 (Issue #1835)
- **正規モデル固有種別の保持 (`resolve_canonical_eval_property_type`)**:
  - `tag_property_integrity` (`src/crawler/package/utils/data_validator.py`)、`api.py` (`_run_stage1_eval`)、`run_ttl_expired_recrawl.py` (`_apply_eval_entry_mutation`) が `PropertyEvaluation.property_type` を保存・更新する際は、`PropertyTypeDetector` の粗いMLカテゴリ名（例: `apartment`）で上書きせず、実モデルクラス名から `resolve_company_and_type` で決定される一意のモデル固有種別（例: `investmentbuilding` / `investmentapartment`）を保存・維持する。
- **URL一致検証付きモデル解決契約 (`send_recommendations.py` / `recover_sekisan_prices.py`)**:
  - 複数の投資テーブルを持つ会社（例: `KenbiyaInvestmentApartment` と `KenbiyaInvestmentBuilding`）において、単一モデル決め打ちとURL未検証の `property_id` フォールバックを行うと、別テーブルの同一連番 `id` を持つ別物件が誤結合される。
  - すべての候補モデルに対して `pageUrl` 照会を行い、`property_id` フォールバック時は必ず `UrlMatcher.is_same_url(eval_url, prop.pageUrl)` による同一物件URL検証を必須とする。
  - Slack 通知直前 (`_dispatch_single_recommendation`) および積算価格リカバリ (`recover_sekisan_prices.py`) においても同一URL不一致を検知した場合は処理を遮断する。
- **回帰テスト**: `src/crawler/tests/unit/test_issue_1835_property_url_mismatch.py`


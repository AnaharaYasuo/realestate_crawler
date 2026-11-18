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

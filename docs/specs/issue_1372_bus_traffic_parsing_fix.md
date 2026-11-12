# -*- coding: utf-8 -*-
# Issue #1372: バス利用物件の交通パース拡充およびSlack配信表示の正常化 仕様書

## 1. 概要 (Overview)
住友不動産ステップ（URL: `https://www.stepon.co.jp/tochi/detail_16011072/`）において、「高崎線 浦和駅 バス11分 停歩2分」というバス便物件であるにもかかわらず、過去クロール時のパース結果がDBに残っていたことや、他社サイト（アットホーム、東急等）における記法ゆらぎにより、Slack通知にて「高崎線 浦和 徒歩11分」と誤認表示される問題が発生した。
本仕様では、今回の住友不動産の事例に対する回帰テスト（UT）を配備した上で、`ParserBase` および個別パーサーのバス交通パースを安全に拡充し、既存DBレコードを最新パーサーでクレンジングする。

## 2. 変更仕様 (Specifications)

### 2.1 ParserBase の安全なバス抽出正規表現の拡充
- `_apply_bus_fields(cls, item, text: str)`:
  - 従来の `r"バス\s*([0-9０-９]{1,3})\s*分"` に加え、`【バス】10分` や `バス乗車15分` などの一般的な表記ゆらぎに対応する。
  - 正規表現パターン: `r"(?:【?バス(?:乗車)?】?|バス\s*利用可\s*バス)\s*([0-9０-９]{1,3})\s*分"`
  - これによりアットホームの `【バス】10分` やリアリエの `バス乗車15分` 等が共通基底パーサーで自然に抽出可能となる。

### 2.2 個別パーサー（Athome / Tokyu 等）の交通補正
- `AthomeParser`:
  - 交通文字列が `【バス】` 記法を含む場合でも `_apply_athome_access_minutes` が正常に `busUse` / `busWalkMinute` をパースできるよう正規表現を同期。
- `TokyuParser`:
  - 改行なしで連結された複数路線テキスト（例: `...徒歩15分中央線...`）を分割して個別処理。

### 2.3 ユニットテストの配備 (TDD)
- 今回の住友不動産ステップの事例（浦和駅バス11分、稲荷越停歩2分）を対象としたユニットテストを作成:
  - `item.railway1 == "高崎線"`
  - `item.station1 == "浦和"`
  - `item.busUse1 == 1`
  - `item.busWalkMinute1 == 11`
  - `item.busStation1 == "稲荷越"`
  - `item.railwayWalkMinute1 == 2`
  - `is_bus_access_property(item) is True`
  - `_format_single_access(item, 1) == "高崎線 浦和 バス11分(停 稲荷越) 徒歩2分"`
- アットホームの `【バス】10分 停歩10分` に対するテストを作成。

### 2.4 DBクレンジングバッチ
- `src/crawler/scripts/maintenance/cleanse_bus_traffic_data.py`:
  - `traffic` に「バス」が含まれるが `busUse1` が設定されていないレコード（住友不動産ステップ、三井、アットホーム等）に対し、最新パーサーの `_populateTraffic` を再実行して保存。

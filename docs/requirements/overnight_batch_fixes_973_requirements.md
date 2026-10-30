# 夜間バッチ実行エラー（三井/大京/アットホーム/Reguide/DB接続性）恒久修復 要件定義書 (Issue #973)

## 1. 概要
2026-10-17夜〜2026-10-18朝の夜間バッチ実行およびクローリングにおいて検出された以下の実行エラー群を恒久修復する。

## 2. 対象事象と改修要件

### 2.1 大京穴吹不動産（マンション）の非物件ページ（コラム等）取得・バリデーション失敗の解消
* **事象**: `/sumai/detail/<id>/` は物件詳細ではなく「不動産コラム・記事ページ」であり、価格・住所が存在しないため `StrictExtractionFailed: price is invalid or non-positive (0), address is empty` が多発した。
* **要件**:
  - `BaseParser._reject_non_property_url` に `/sumai/detail/` を非物件URLとして登録し、Fast-Skip（`SkipPropertyException`）させる。
  - `DaikyoParser._normalize_detail_url` および `_extract_detail_links` において、`/sumai/detail/` やコラムURLを物件詳細リンクとして収集しないよう除外フィルタリングを適用する。

### 2.2 三井のリハウス（mansion/kodate/tochi/invest_kodate）の交通・土地面積欠損の解消
* **事象**: 三井の交通表記が `\n` 区切りではなくスペース区切りまたは1行結合された場合、および区分マンションのURL（`/buy/mansion/bkdetail/...`）が `mitsui_invest_kodate` の一覧から収集された際に `tochiMenseki` 必須欠損と判定された。
* **要件**:
  - `MitsuiParser._parseTrafficLines` において、改行なしで駅名が連続するパターン（例: `六本木駅徒歩9分広尾駅徒歩13分`）を正規表現で自動分割して複数路線として正しく抽出する。
  - `mitsui_invest_kodate` クローラーの一覧収集において、区分マンションURL (`/buy/mansion/`) が混入した場合は `SkipPropertyException` または `_maybe_switch_parser` にて適切にスキップ/委譲し、戸建て必須の `tochiMenseki` 欠損エラーとならないようにする。

### 2.3 アットホーム（tochi）の土地面積抽出漏れ防止
* **事象**: 一部の土地詳細ページで土地面積が `0.0㎡` または未抽出となり、バリデータで弾かれた。
* **要件**:
  - `AthomeTochiParser` において、テーブルヘッダーの「面積」「敷地面積」「土地面積」「区画面積」および本文内の面積表記を漏れなく探索し、正常な数値を抽出する。

### 2.4 ReguideInvestment モデルのマイグレーション同期と評価堅牢化
* **事象**: バルク価格推定バッチ実行時、`reguide_investment` テーブルが存在せず例外が発生し、1モデルが評価失敗となった。
* **要件**:
  - `0064_reguideinvestment` マイグレーションを本番・開発環境ともに確実に適用する。
  - `runner.py` において、テーブル未作成や推論不可の例外が発生した場合でも、エラーハンドリングとログ記録を行い、他のモデル推論やパイプライン全体に波及させないこと。

### 2.5 DB接続性（host.docker.internalタイムアウト）の環境変数・設定適正化
* **事象**: Dockerコンテナから `host.docker.internal:3307` への接続がタイムアウトし、API呼び出しで500エラーが発生した。
* **要件**:
  - Docker Compose 構成において、内部通信時は `db:3306` をデフォルトとし、ホスト側 ProxySQL VM 接続時のフォールバックおよびヘルスチェックを保証する。

## 3. 受入基準 (Acceptance Criteria)
* [ ] 【基準1】大京穴吹の `/sumai/detail/<id>/` が非物件URLとして即時スキップされ、StrictExtractionFailed が発生しないこと。
* [ ] 【基準2】三井のリハウスの交通（`_parseTrafficLines`）が1行結合文字列でも正しく複数駅に分割抽出されること。
* [ ] 【基準3】アットホーム（土地）の各種表記（面積・敷地面積）から土地面積が抽出されること。
* [ ] 【基準4】ReguideInvestment のバルク推論評価が正常に動作すること。
* [ ] 【基準5】すべての回帰テスト（pytest）が通過すること。

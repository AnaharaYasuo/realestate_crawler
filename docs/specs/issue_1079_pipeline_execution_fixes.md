# 仕様書: Issue #1079 フルパイプライン実行エラー・不整合の総合修復

## 1. 概要
フルパイプライン（`run_pipeline.py`）実行時に検知された、パース・重複排除・バルクML評価・ストレージ接続・プロセス制御における不具合を包括的に修復する。

## 2. 対象課題と改修仕様

### 2.1 重複排除キャッシュにおける未知モデル (`Unknown*`) クラッシュの防止
- **現状**:
  - `eval_rec.company == "unknown"` の場合、`_get_real_property()` が `UnknownKodate` 等の実在しないモデル名を生成し、`App 'package' doesn't have a 'UnknownKodate' model` で例外発生。
- **仕様**:
  - `eval_rec.property_url` をもとに既知のドメイン（asahi-kasei.co.jp -> afr, re-guide.jp -> reguide, tokyu -> tokyu 等）から会社名を逆引き補正する。
  - 会社名が判別できない場合は実在しないモデル名を作らず、安全に `None` を返却する。

### 2.2 バルクML評価時のDB切断（2013 Lost connection / 2006 Server gone away）対策
- **現状**:
  - 大量評価レコード保存時（`bulk_update` / `bulk_create`）に、一時的なMySQL/ProxySQL切断でパイプライン全体が落ちる。
- **仕様**:
  - `bulk_update_evaluation_records` および `bulk_create_evaluation_records` において、`OperationalError`（2006, 2013 等）発生時に `django.db.close_old_connections()` を呼び出し、指数バックオフ付きで最大3回リトライを行う。

### 2.3 MinIO ホスト実行時のエンドポイントフォールバック
- **現状**:
  - `EXECUTION_ENV=host` または非クラウド環境において、`STORAGE_ENDPOINT` のデフォルト値 `http://minio:9000` は名前解決できず、`EndpointConnectionError` となる。
- **仕様**:
  - `ObjectStorageManager` 初期化時、ホスト実行環境（`EXECUTION_ENV == 'host'` または `not IS_CLOUD`）でエンドポイントに `minio:9000` が指定されている場合、自動的に `localhost:9000` または `127.0.0.1:9000` に置換して接続を確立する。

### 2.4 三井投資戸建パーサーおよびAthome土地パーサーにおける区分・土地面積の正規化
- **現状**:
  - 三井で `/buy/mansion/` や区分所有の物件が投資戸建として流れてきた際、委譲先で `tochiMenseki` が設定されず `0.0` のままとなりバリデータでエラー扱いとなる。
  - Athome の `buy_other`（売その他）で土地面積仕様が「－」の場合に `0.0㎡` となりバリデーション落ちする。
- **仕様**:
  - `MitsuiInvestmentKodateParser`: 区分所有・マンション・事務所等の場合は `MitsuiInvestmentApartmentParser` に適切に委譲し、種別を整合させる。
  - `AthomeTochiParser`: 土地面積が欠損または「－」の `buy_other` 物件は適切にスキップ（`SkipPropertyException`）または安全に処理する。
  - `data_validator.py`: 区分所有マンション等の集合住宅形態の場合は土地面積チェックを免除する。

### 2.5 Windows環境でのクローラー並列実行プロセスキル対応
- **現状**:
  - `run_all_crawlers.py` 内で `os.getpgid` / `os.killpg` を無条件に呼び出しており、Windows環境で `AttributeError` が発生する。
- **仕様**:
  - `hasattr(os, "getpgid")` で判定し、Windowsでは `proc.kill()` による直接強制終了を行う。

## 3. テスト計画 (TDD)
- `tests/unit/test_issue_1079_pipeline_execution_fixes.py` を作成し、上記各項目の挙動（重複排除のUnknownモデル回避、MinIOフォールバック、DBバルクリトライロジック、パーサー挙動）を単体テストで検証する。

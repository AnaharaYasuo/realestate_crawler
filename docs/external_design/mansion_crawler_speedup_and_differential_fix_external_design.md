# マンション系クローラー中間ページ並行化・WAF適正緩和および野村差分抽出修復 外部設計書 (Issue #867)

## 1. 外部インターフェースおよび設定変更

### 1.1 中間ページAPI並行度設定 (`package/api/*.py`)
各サイトの中間ページ処理クラスにおける並列制限値（`_getLocalPararellLimit`, `_getCloudPararellLimit`）を変更：
- `package/api/mitsui.py`:
  - `MIDDLE_PARARELL_LIMIT = 3` を新設
  - `ParseMitsuiMansionAreaFuncAsync`, `ParseMitsuiMansionStartAsync` の並行数を 1 ➔ 3
  - （戸建・土地のArea/Startも同様に 3 に適正化）
- `package/api/nomura.py`:
  - `MIDDLE_PARARELL_LIMIT = 3` を新設
  - `ParseNomuraMansionAreaFuncAsync`, `ParseNomuraMansionRegionFuncAsync` の並行数を 1 ➔ 3
- `package/api/sumifu.py`:
  - `MIDDLE_PARARELL_LIMIT = 3` を新設
  - `ParseSumifuMansionAreaFuncAsync`, `ParseSumifuMansionRegionFuncAsync` の並行数を 1 ➔ 3
- `package/api/tokyu.py`:
  - `MIDDLE_PARARELL_LIMIT = 3` を新設
  - `ParseTokyuMansionAreaFuncAsync`, `ParseTokyuMansionStartAsync` の並行数を 1 ➔ 3

### 1.2 WAF保護レートリミットおよび並行キャップ (`package/api/api.py`, `package/api/adaptive_concurrency.py`)
- `AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS`:
  - `"mitsui": 3`（旧: 2）
  - `"nomura": 3`（旧: 2）
- `ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS`:
  - `"mitsui": 0.5`（旧: 1.0）
  - `"nomura": 0.5`（旧: 1.0）

### 1.3 カードコンテナ探索ロジック (`package/parser/baseParser.py`)
- `_find_card_container(link)`:
  - タイトルラッパー（クラス名に `title`, `name`, `heading` を含み、かつ子要素や兄弟要素に価格が存在しない部分要素）をカード本体として誤認識しないようガードを強化。
  - 親コンテナ探索時に、`item_title` 等の部分タイトル要素で停止せず、価格情報セレクター（`.price`, `strong[class*="price"]` 等）を包含する上位コンテナまで探索を継続。

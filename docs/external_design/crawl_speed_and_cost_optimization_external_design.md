# クローリング高速化およびCloud Runコスト最適化 外部設計書 (Issue #851)

## 1. システム構成・インターフェース変更

### 1.1 パーサーインターフェース変更 (`daikyoParser.py`)
- `parseRootPage` および `_crawl_pref_url` の返却型:
  - 従来: `yield str (url)`
  - 変更後: `yield ListItem(url=url, price=price)`
  - 一覧カード要素 (`.object-item`, `.cassette`, `.item-box` 等) から価格文字列（例: `3,580万円`）を取得し、`converter.parse_price` で数値（円）に変換した上で `ListItem` に格納して返却。
- `_crawl_pref_url`:
  - セマフォ（例: `asyncio.Semaphore(6)`）を用いて各都道府県URLを並行取得。
  - ページネーション安全上限: `MAX_PREF_PAGES = 30`。

### 1.2 動的並行度制御 (`adaptive_concurrency.py` & `api.py`)
- `api.py`:
  - `CLOUD_DETAIL_CONCURRENCY` が明示指定されていない場合、または空文字の場合は `AdaptiveConcurrencyController.get_effective_concurrency(company=company)` を自動適用。
  - `AdaptiveConcurrencyController`: デフォルトの基本並行度を最大 15（サイトキャップ尊重）に設定。
- `cloud_run_job.tf`:
  - 環境変数 `CLOUD_DETAIL_CONCURRENCY` の固定値 `"5"` を撤廃、または削除して動的制御を有効化。

### 1.3 タスク分散マッピング変更 (`task_distribution.py`)
- 8タスク分散構成:
  - Task 0: mitsui (mansion, kodate, tochi) + daikyo mansion
  - Task 1: sumifu (mansion, kodate, tochi) + daikyo kodate & tochi
  - Task 2: tokyu, nomura, misawa (居住用)
  - Task 3: 投資用物件 (mitsui, sumifu, tokyu, nomura, misawa, smtrc, sumai1, mizuho, odakyu, sumirin)
  - Task 4: 信託3社居住用 + ハウスメーカー/電鉄系 (daikyo以外)
  - Task 5: homes (全種別)
  - Task 6: athome (mansion)
  - Task 7: athome (その他種別)

### 1.4 インフラリソース定義 (`variables.tf`)
- `crawler_timeout`: `"32400s"` ➔ `"7200s"`
- `crawler_memory`: `"3Gi"` ➔ `"2Gi"`

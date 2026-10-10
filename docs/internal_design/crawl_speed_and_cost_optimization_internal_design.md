# クローリング高速化およびCloud Runコスト最適化 内部設計書 (Issue #851)

## 1. 内部モジュール実装詳細

### 1.1 `daikyoParser.py` の内部変更
- `_extract_detail_links`:
  ```python
  def _extract_detail_items(self, soup: BeautifulSoup, detail_links: set):
      # 物件カード (.result-list__item, .cassette, 等) をループ
      for item_box in soup.select('.result-list__item, .cassette, .object-item, article'):
          a = item_box.select_one('a[href*="detail"]')
          if not a or not a.get("href"):
              continue
          normalized = self._normalize_detail_url(a.get("href"))
          if normalized in detail_links:
              continue
          detail_links.add(normalized)
          
          # 価格抽出
          price_val = None
          price_el = item_box.select_one('.price, .result-list__price, span[class*="price"]')
          if price_el:
              price_val = converter.parse_price(price_el.get_text(strip=True))
          
          yield ListItem(url=normalized, price=price_val)
  ```
- `_crawl_pref_url` の非同期並行化:
  - `parseRootPage` で `pref_urls` を取得後、`asyncio.Semaphore(6)` で並行実行。
  - 各都道府県内で `page_count >= MAX_PAGES_PER_PREF (30)` に達した場合は次ページ遷移を打ち切り。

### 1.2 `api.py` および `adaptive_concurrency.py`
- `api.py`:
  - `CLOUD_DETAIL_CONCURRENCY` が未設定または空文字のとき、自動的に `AdaptiveConcurrencyController.get_effective_concurrency(company=company)` を呼び出す。
- `adaptive_concurrency.py`:
  - 単一ジョブ実行時（アクティブジョブ=1）のベース並行度を最大 `15` に設定（相手先サイトキャップが下位にあればそちらを採用）。

### 1.3 `task_distribution.py`
- `_assign_8_task_index`:
  - `company == "daikyo"` かつ `ptype == "mansion"` ➔ Task 0
  - `company == "daikyo"` かつ `ptype in ("kodate", "tochi")` ➔ Task 1
  - Task 4 の過負荷を解消し、空き時間が多い大手仲介枠に均等分散。

### 1.4 Terraform 設定
- `terraform/cloud_run_job.tf`:
  - `CLOUD_DETAIL_CONCURRENCY` を環境変数一覧から削除、またはデフォルトで動的制御に委ねる。
- `terraform/variables.tf`:
  - `crawler_timeout`: default `"7200s"`（2時間）
  - `crawler_memory`: default `"2Gi"`

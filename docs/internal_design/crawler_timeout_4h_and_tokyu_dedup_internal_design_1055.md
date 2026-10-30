# 内部設計書: クローラー全体タイムアウト4時間化・東急無差別取得是正・DB負荷軽減 (Issue #1055)

## 1. タイムアウトおよび閾値変更
### 1.1 `terraform/variables.tf`
```hcl
variable "crawler_timeout" {
  type        = string
  description = "Maximum execution duration for crawler Cloud Run Job (4h = 14400s)"
  default     = "14400s"
  validation {
    condition     = can(regex("^[0-9]+s$", var.crawler_timeout)) && tonumber(trimsuffix(var.crawler_timeout, "s")) <= 14400
    error_message = "crawler_timeout must be a valid duration string ending with 's' and not exceed 14400s (4 hours)."
  }
}
```

### 1.2 `terraform/cloud_run_job.tf`
```hcl
        env {
          name  = "CRAWLER_HANG_THRESHOLD_SEC"
          value = "180"
        }
```

### 1.3 スクリプト定数
- `src/crawler/scripts/ops/run_pipeline.py`: `DEFAULT_TIMEOUT_SEC = 14400.0`
- `src/crawler/scripts/ops/run_all_crawlers.py`: `timeout_sec = int(os.getenv("CRAWL_TIMEOUT_SEC", "14400"))`
- `src/crawler/scripts/ensure_resources_stopped.py`: `DEFAULT_HUNG_THRESHOLD_SEC = 15000.0`

---

## 2. 東急パーサーの重複排除およびセレクタ厳格化
### 2.1 `TokyuParser.parsePropertyListPage`
```python
async def parsePropertyListPage(self, response):
    seen = set()
    # 1. Next.js JSONデータからの抽出があれば優先
    items = self._extract_nextjs_urls(response)
    if items is not None:
        for item in items:
            url = getattr(item, "url", str(item))
            if url not in seen:
                seen.add(url)
                yield item
        return

    # 2. HTML DOMからの抽出: 代表リンク (物件カード単位または代表セレクタ)
    cards = response.select("[class*='propertyCardContents']")
    if cards:
        for card in cards:
            a = card.find("a", href=True)
            if a:
                href = a["href"]
                dest_url = self.getPropertyListDestUrl(href)
                if dest_url and dest_url not in seen:
                    seen.add(dest_url)
                    price = self._extract_card_price(a)
                    yield ListItem(url=dest_url, price=price)
        return

    # 3. フォールバック
    async for dest_url in self._parsePageCore(response, self.getPropertyListXpath, self.getPropertyListDestUrl):
        url = getattr(dest_url, "url", str(dest_url))
        if url not in seen:
            seen.add(url)
            yield dest_url
```

### 2.2 `TokyuParser.parseRootPage`
- 都道府県リンクの重複排除（`seen_urls = set()`）

### 2.3 `TokyuParser.parseAreaPage`
- 市区町村リンク（`/a\d+/`）の重複排除（`seen_urls = set()`）および `select-town` などの不要リンク除外。

---

## 3. 進捗監視のDBクエリ撤廃
### 3.1 `run_all_crawlers.py`
- `update_watchdog_progress(active_processes, now, count_fn)` において、DBへのフルスキャン `get_count_for_job` は重負荷要因となるため呼び出さない、もしくは軽量なチェックに置き換える。

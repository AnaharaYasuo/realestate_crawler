# 失敗クローラー群接続・リダイレクト・空結果・タイムアウト修復 内部設計 (Issue #959)

## 1. モジュール別実装仕様

### 1.1 `src/crawler/package/parser/reguideParser.py` & `src/crawler/routes/reguide_routes.py`
- `REGUIDE_INVESTMENT_ROOT_URL = "https://www.re-guide.jp/investment/list/"`
- `BASE_URL = "https://www.re-guide.jp"`
- `REGUIDE_DETAIL_URL_PATTERN = re.compile(r"^https://www\.re-guide\.jp/investment/\d+/?$")`
- `_is_valid_reguide_url`: `re-guide.jp` および `www.re-guide.jp` の双方を有効と判定。

### 1.2 `src/crawler/package/parser/smtrcParser.py`
- `_getContent(self, session, url)` の例外ハンドリングを拡張：
```python
except Exception as e:
    err_str = str(e).lower()
    is_waf_or_timeout = any(
        kw in err_str
        for kw in ["403", "forbidden", "timeout", "server down", "timed out", "clienterror"]
    ) or isinstance(e, (asyncio.TimeoutError, ServerDownException, LoadPropertyPageException))
    if is_waf_or_timeout:
        logger.warning("smtrc connection/WAF error (%s) detected for %s, falling back to Playwright stealth...", e, url)
        fb_content = await self._smtrc_fetch_with_playwright(url)
        if len(fb_content) < 1000:
            raise RuntimeError(f"smtrc Playwright fetch failed on fallback: content size too small ({len(fb_content)} bytes) for {url}")
        return fb_content
    raise
```

### 1.3 `src/crawler/package/utils/job_metrics.py` & `run_all_crawlers.py`
- `job_metrics.py`:
  - `_is_empty_result: bool = False` グローバル追跡。
  - `mark_empty_result()` 関数を新設。
  - `export_job_metrics`: `is_empty_result: bool | None = None` を引数に受け、Noneの場合は `_is_empty_result` を採用。JSONに `"is_empty_result": True/False` を書き込み。
  - `read_job_metrics`: `(detail, skip, tot, is_empty_result)` の4要素タプルを返却。
- `run_all_crawlers.py`:
  - `resolve_job_counts` で `detail, skip, tot, is_empty_result, from_file` を解決。
  - `exit_code == 0` かつ `tot == 0` の時、`is_empty_result` が True ならば `ZeroCountFailure` とせず、`✅ 【成功 (掲載0件)】` として Slack 通知し `status = "success"` とする。

### 1.4 `src/crawler/package/parser/tokyuParser.py`
- `TokyuInvestmentKodateParser`:
  - `parsePropertyListPage` において、`_extract_nextjs_urls` で `property_list` は存在する（または正常な一覧ページである）が、戸建て物件が抽出されず `items == []` の場合、`mark_empty_result()` を呼び出して正常空結果をマーク。

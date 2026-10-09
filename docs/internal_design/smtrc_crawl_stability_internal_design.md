# SMTRCクローリング安定化・全物件種別0件取得防止内部設計書 (Issue #827)

## 1. 概要
本設計書は、`src/crawler/package/parser/smtrcParser.py` および関連モジュールにおけるクラス設計、Playwrightステルス初期化パラメータ、フォールバックロジック、およびテスト検証仕様を定義する。

## 2. クラス構造
```
ParserBase
  └── SmtrcParser
        ├── SmtrcMansionParser (MansionParserBase) ➔ SmtrcMansion
        ├── SmtrcKodateParser (KodateParserBase)   ➔ SmtrcKodate
        ├── SmtrcTochiParser (TochiParserBase)     ➔ SmtrcTochi
        └── SmtrcInvestmentParser (InvestmentParserBase) ➔ SmtrcInvestment
```

## 3. 実装詳細

### 3.1 Playwright ステルス起動パラメータ (`_smtrc_fetch_with_playwright`)
```python
_SMTRC_PLAYWRIGHT_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-infobars',
    '--window-position=0,0',
    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
]

_SMTRC_STEALTH_INIT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    window.chrome = { runtime: {} };
"""
```

### 3.2 フォールバックフロー (`_getContent`)
```python
async def _getContent(self, session, url):
    try:
        content = await super()._getContent(session, url)
        if len(content) >= 1000:
            return content
        logger.warning("smtrc small content (%s bytes), fallback to Playwright stealth...", len(content))
        pw_content = await self._smtrc_fetch_with_playwright(url)
        if len(pw_content) >= 1000:
            return pw_content
        # 1回リトライ
        retried = await self._smtrc_fetch_with_playwright(url)
        if len(retried) < 1000:
            raise RuntimeError(...)
        return retried
    except Exception as e:
        if "403" in str(e) or "Forbidden" in str(e):
            fb_content = await self._smtrc_fetch_with_playwright(url)
            if len(fb_content) < 1000:
                raise RuntimeError(...)
            return fb_content
        raise
```

## 4. テスト検証仕様
1. **単体テスト (`test_smtrc_parser.py`)**:
   - `test_smtrc_mansion_parser`: `createEntity()` が `SmtrcMansion` を返すこと。
   - `test_smtrc_kodate_parser`: `createEntity()` が `SmtrcKodate` を返すこと。
   - `test_smtrc_tochi_parser`: `createEntity()` が `SmtrcTochi` を返すこと。
   - `test_smtrc_investment_parser`: `createEntity()` が `SmtrcInvestment` を返すこと。
   - `test_smtrc_get_content_waf_403_fallback`: HTTP 403 時に Playwright ステルス取得へ正常にフォールバックすること。
   - `test_smtrc_get_content_small_content_fallback`: 1000 bytes 未満のレスポンス時に Playwright ステルス取得へフォールバックすること。
2. **統合・ライブ検証 (`test_live_crawl_guarantee.py`)**:
   - `smtrc - mansion`
   - `smtrc - kodate`
   - `smtrc - tochi`
   - `smtrc - investment`
   上記 4 種別のスタート URL 巡回と詳細抽出が正常にパスすること。

# 掲載終了ページ共通ハンドリング内部設計書 (Issue #600)

## 1. モジュール変更仕様

### 1.1 `src/crawler/package/parser/baseParser.py`

#### 定数追加
```python
LISTING_ENDED_TITLE_KEYWORDS: tuple[str, ...] = (
    "掲載終了",
    "掲載が終了",
    "掲載を終了",
    "成約済",
    "ご成約",
    "お探しの物件は見つかりません",
    "お探しのページは見つかりません",
    "物件が見つかりません",
)

LISTING_ENDED_BODY_KEYWORDS: tuple[str, ...] = (
    "掲載が終了したか、成約済みになった可能性があります",
    "お探しの物件は、掲載が終了",
    "掲載を終了いたしました",
    "掲載終了物件",
    "ご指定の物件は掲載を終了",
    "お探しのページは見つかりませんでした",
    "お探しの物件は見つかりませんでした",
    "お探しのページは存在しないか、掲載が終了",
    "現在、掲載を停止しております",
    "この物件は現在掲載されていません",
)
```

#### メソッド改修: `_raise_on_listing_title`
タイトルに加えて、`soup` を引数に取れるよう拡張（または `_raise_if_listing_ended(soup, url)` を新設）。

```python
    @classmethod
    def _raise_if_listing_ended(cls, soup: BeautifulSoup, url: str) -> None:
        """物件詳細ページが掲載終了・非公開状態の場合に ListingEndedException を送出"""
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        if title:
            if "サーバーが混み合っています" in title:
                logging.info(f"Server busy for URL: {url}")
                raise ServerBusyException()
            if any(kw in title for kw in cls.LISTING_ENDED_TITLE_KEYWORDS):
                logging.info(f"Listing ended (title match: '{title}') for URL: {url}")
                raise ListingEndedException(f"Listing ended for URL: {url}")

        # タイトルで判定できなかった場合、見出しや本文特定メッセージの走査
        h1_tag = soup.find("h1")
        h1_text = h1_tag.get_text().strip() if h1_tag else ""
        if h1_text and any(kw in h1_text for kw in cls.LISTING_ENDED_TITLE_KEYWORDS):
            logging.info(f"Listing ended (h1 match: '{h1_text}') for URL: {url}")
            raise ListingEndedException(f"Listing ended for URL: {url}")

        # 本文テキスト走査（エラーメッセージ等の主要フレーズ）
        body_tag = soup.body
        if body_tag:
            # 高速化のため、明示的な not-found / error コンテナがあれば優先チェック
            err_box = body_tag.select_one(".mod-message-end, .not-found, .error-message, .alert-box")
            if err_box:
                err_text = err_box.get_text()
                if any(kw in err_text for kw in cls.LISTING_ENDED_BODY_KEYWORDS):
                    logging.info(f"Listing ended (err_box match) for URL: {url}")
                    raise ListingEndedException(f"Listing ended for URL: {url}")
            
            # 全文走査
            body_text = body_tag.get_text()
            if any(kw in body_text for kw in cls.LISTING_ENDED_BODY_KEYWORDS):
                logging.info(f"Listing ended (body match) for URL: {url}")
                raise ListingEndedException(f"Listing ended for URL: {url}")
```

#### メソッド改修: `parsePropertyDetailPage`
```python
        try:
            item.pageUrl = url
            content = await self._getContent(session, url)
            soup = self._soup_from_content(content, self.getCharset())
            self._raise_if_listing_ended(soup, url)
            ...
```

---

## 2. 各社パーサーの整理

* `athomeParser.py`: `_parsePropertyDetailPage` 内で独自に実施していた `ListingEndedException` の事前チェックを維持しつつ、共通判定と重複しても安全に動作することを保証。
* `tokyuParser.py`: `check_tokyu_listing_ended` は互換性のため維持し、基底クラス側でも包括検知。

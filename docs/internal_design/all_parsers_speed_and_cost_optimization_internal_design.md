# 内部設計書: 残り15サイトの一覧並列化および価格一致スキップ最適化 (Issue #854)

## 1. ListItem返却
各パーサーの `parsePage` で以下のように `ListItem` を構築：
```python
from package.parser.baseParser import ListItem

# 抽出した物件リンクと価格テキストから数値（万円単位 float）を抽出
price_val = self._parse_price_to_man_yen(price_text) # またはヘルパー関数
yield ListItem(url=full_url, price=price_val)
```

## 2. parseRootPageの並列化パターン
`asyncio.Queue` と `asyncio.Semaphore` を用いたストリーミング並列化：
```python
sem = asyncio.Semaphore(10)
async def _fetch_and_expand(url):
    async with sem:
        return await self._fetch_sub_urls(url)
```
結果を順次キューまたはジェネレータで返却し、上流のクローラーエンジンへ即時供給する。

## 3. 下位互換性
`ListItem` は `url` フィールドを保持し、文字列としても比較・処理可能なインターフェースを有するため、従来の一覧処理コードを破壊しない。

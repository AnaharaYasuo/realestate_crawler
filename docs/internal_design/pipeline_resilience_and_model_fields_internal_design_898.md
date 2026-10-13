# 内部設計書: 継続実行時のパース・モデル不整合解消及びサーキットブレイカー誤爆防止 (Issue #898)

## 1. 修正対象モジュール
1. `src/crawler/package/models/sumifu.py`
2. `src/crawler/package/models/mitsui.py`
3. `src/crawler/package/parser/baseParser.py`

## 2. 詳細実装仕様

### 2.1 `src/crawler/package/models/sumifu.py`
```python
class SumifuKodate(SumifuModel):
    ...
    chiikiChiku = models.TextField(blank=True, default="")
    kuiki = models.TextField(blank=True, default="")
    youtoChiiki = models.TextField(blank=True, default="")
    boukaChiiki = models.TextField(blank=True, default="")
    saikenchiku = models.TextField(blank=True, default="")
    sonotaChiiki = models.TextField(blank=True, default="")
    tyusyajo = models.TextField(blank=True, default="")
    kokudoHou = models.TextField(blank=True, default="")
```

### 2.2 `src/crawler/package/models/mitsui.py`
```python
class MitsuiMansion(MitsuiModel):
    ...
    kanrihi = models.IntegerField(null=True, blank=True)
    syuzenTsumitate = models.IntegerField(null=True, blank=True)

class MitsuiInvestmentApartment(MitsuiModel):
    ...
    soukosuStr = models.TextField(blank=True, default="")
    soukosu = models.IntegerField(null=True, blank=True)
```

### 2.3 `src/crawler/package/parser/baseParser.py`
`_getContent` メソッドにおけるタイムアウト制御の整理：
```python
    async def _getContent(self, session: aiohttp.ClientSession, url: str) -> bytes:
        headers = {'User-Agent': 'Mozilla/5.0 ...'}
        max_timeouts = getattr(self, 'MAX_CONSECUTIVE_TIMEOUTS', 3)
        req_timeout = getattr(self, 'REQUEST_TIMEOUT_SEC', 15)
        for attempt in range(max_timeouts):
            try:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=req_timeout, connect=5, sock_read=10)
                ) as response:
                    if response.status == 200:
                        self.consecutive_timeouts = 0
                        return await response.read()
                    self._validate_http_status(response.status, url)
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                if attempt == max_timeouts - 1:
                    # 1つのURLがリトライ上限まで失敗したときにサイト連続失敗としてカウント
                    cur_timeouts = getattr(self, 'consecutive_timeouts', 0) + 1
                    self.consecutive_timeouts = cur_timeouts
                    if cur_timeouts >= max_timeouts:
                        raise ServerDownException(f'Target server is down or timing out repeatedly ({cur_timeouts} times)') from e
                    raise LoadPropertyPageException(f'Timeout after {attempt + 1} attempts for URL: {url}') from e
                await asyncio.sleep(1 * (attempt + 1))
        return b''
```
※ 単一リクエスト内の1回目・2回目のリトライ失敗を即座にグローバル連続タイムアウトとしてカウントせず、同一URLへのリトライが全滅した時点で1回として加算。これにより一時的なジッターでサーキットブレイカーが暴走することを根絶する。


### 健美家（kenbiya）個別スロットル仕様（Issue #1698）
- `KenbiyaParserBase._throttle_before_request` は `KENBIYA_MIN_INTERVAL`（既定 `1.0` 秒）に加え、ランダムジッター `random.uniform(1.5, 2.5)` 秒（期待値 `2.0` 秒）を付与し、平均リクエスト間隔 `3.0` 秒（`2.5〜3.5` 秒）を担保する。

# 失敗クローラー群接続・リダイレクト・空結果・タイムアウト修復 外部設計 (Issue #959)

## 1. 外部インタフェース・動作変更
- **RE-Guide 開始URL・詳細URL**:
  - ルートURL: `https://www.re-guide.jp/investment/list/`
  - 詳細URLパターン: `^https://www\.re-guide\.jp/investment/\d+/?$`
  - `re-guide.jp` への直接リクエスト時の301リダイレクトによる aiohttp タイムアウトを根絶。
- **SMTRC Playwright フォールバック**:
  - `_getContent(url)` において、HTTPステータス 403だけでなく、タイムアウト例外（`asyncio.TimeoutError`）、サーバーダウン例外（`ServerDownException`, `LoadPropertyPageException`）、接続エラー例外（`aiohttp.ClientError`）発生時にも自動的に Playwright ステルス取得へフォールバック。
- **正常空結果（Empty Result）ハンドリング**:
  - `job_metrics.py`: `is_empty_result: bool = False` をメトリクスデータに追加。
  - `export_job_metrics` に `is_empty_result` オプションを新設。
  - `read_job_metrics`: `(detail_cnt, skipped_cnt, total_cnt, is_empty_result)` を返却。
  - `run_all_crawlers.py`: `from_file` で `total_cnt == 0` かつ `is_empty_result is True` の場合、`ZeroCountFailure` ではなく `status = "success"`（`✅ 【成功 (掲載0件)】`）として終了。

# GCSリアルタイム障害テレメトリ・一括オートヒール内部設計書 (Issue #466)

## 1. データ構造仕様

### 1.1 障害メタデータ JSON (`FailureRecord`)
各ジョブが異常検知時に GCS へ出力する構造体スキーマ:

```json
{
  "run_id": "20260926-002926",
  "task_index": 1,
  "task_count": 8,
  "company": "nomura",
  "property_type": "mansion",
  "status": "failed",
  "exit_code": 1,
  "error_type": "SelectorMismatch",
  "error_message": "StrictExtractionFailed: address is empty for URL: https://www.nomu.com/mansion/...",
  "target_url": "https://www.nomu.com/mansion/ensen_tokyo/2172/2172110/",
  "gcs_html_path": "gs://realestate-images-prod/runs/20260926/error_pages/nomura_mansion/d41d8cd98f00b204e9800998ecf8427e.html",
  "parser_file": "src/crawler/package/parser/nomuraParser.py",
  "traceback": "Traceback (most recent call last):\n  File ...",
  "timestamp": "2026-09-26T00:29:46.123456+09:00",
  "duration_seconds": 16
}
```

### 1.2 集約マニフェスト (`DailyFailureManifest`)
`fetch_run_failures.py` が GCS の個別 JSON をワイルドカード取得し、Antigravity へ提供する集約データ:

```json
{
  "date": "2026-09-26",
  "total_failures": 4,
  "failures": [
    { /* FailureRecord 1 (nomura-mansion) */ },
    { /* FailureRecord 2 (mitsui-kodate) */ },
    { /* FailureRecord 3 (sekisui-kodate) */ },
    { /* FailureRecord 4 (mitsui-invest_apartment) */ }
  ]
}
```

---

## 2. モジュール詳細設計

### 2.1 `FailureReporter` (`package.utils.failure_reporter`)
```python
class FailureReporter:
    @classmethod
    def record_job_failure(
        cls,
        company: str,
        property_type: str,
        error_type: str,
        error_message: str,
        target_url: str = "",
        exit_code: int = 1,
        traceback_str: str = "",
        raw_html: Optional[bytes] = None,
        duration_seconds: int = 0,
        task_index: Optional[int] = None,
        task_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """障害メタデータおよび生HTMLをGCSへ即時非同期/同期アップロード"""

    @classmethod
    def fetch_daily_failures(cls, date_str: Optional[str] = None) -> Dict[str, Any]:
        """GCSから対象日付の全タスク障害JSONを取得・集約"""
```

- **GCS クライアント初期化**:
  - `STORAGE_BACKEND=gcs` または `IS_CLOUD=true` の場合は `google.cloud.storage.Client()` を使用。
  - `upload_bytes`, `upload_image_bytes`, `list_files`, `read_text` でネイティブ GCS API を呼び出す。
  - ローカル開発・テスト時は既存の `STORAGE_ENDPOINT`（MinIO / S3互換）へ自動フォールバック。

### 2.2 `api.py` の直接生 HTML 引き渡し
- `_sync_save_error_html_by_url(url, model_name, reason, raw_html=None)`:
  - `raw_html` が与えられた場合は `requests.get` をスキップし、手元の生 HTML をディスクおよび `FailureReporter.record_job_failure` に直接書き込む。
  - `ParseMiddlePageAsyncBase`: パース例外発生時に `raw_html_content = str(response)` を直接渡す。

### 2.3 `ApiRegistry` レガシー GCP パス互換登録
- `package/api/registry.py` または各 API ファイルにおいて、`API_KEY_*_GCP` を正規の API ハンドラクラスと紐付けて登録。
- `_handle_local_execution(api_url, detail_url)` で、`API_KEY_*_GCP` であっても常にローカルインプロセス実行クラスが解決されるようにする。

### 2.4 `converter.py` の Decimal 2 桁丸め
- `parse_menseki` および `parse_ratio`:
  - `Decimal(str_val).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)` を適用し、Django の `DecimalField(decimal_places=2)` 制約に準拠させる。

### 2.2 `ObjectStorageManager` (`package.utils.storage`) (Issue #477)
```python
class ObjectStorageManager:
    def __init__(self):
        self.backend = os.getenv("STORAGE_BACKEND", "minio").lower()
        self.bucket_name = os.getenv("STORAGE_BUCKET", "realestate-images")
        
        if self.backend == "gcs" or (os.getenv("IS_CLOUD") and os.getenv("STORAGE_ENDPOINT") is None):
            from google.cloud import storage as gcs_storage
            self.gcs_client = gcs_storage.Client()
            self.gcs_bucket = self.gcs_client.bucket(self.bucket_name)
            self.is_gcs = True
        else:
            # 既存の boto3 / MinIO 初期化
            self.s3_client = boto3.client('s3', ...)
            self.is_gcs = False

    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/json") -> str:
        if self.is_gcs:
            blob = self.gcs_bucket.blob(key)
            blob.upload_from_string(data, content_type=content_type)
            return f"gs://{self.bucket_name}/{key}"
        # 既存 boto3 実装
        ...

    def list_files(self, prefix: str) -> list[str]:
        if self.is_gcs:
            blobs = self.gcs_client.list_blobs(self.gcs_bucket, prefix=prefix)
            return [b.name for b in blobs]
        # 既存 boto3 実装
        ...

    def read_text(self, key: str) -> str:
        if self.is_gcs:
            blob = self.gcs_bucket.blob(key)
            return blob.download_as_text(encoding="utf-8")
        # 既存 boto3 実装
        ...
```

### 2.3 `api.py` `_sync_save_error_html_by_url` 生 HTML 直接保存 (Issue #477)
```python
def _sync_save_error_html_by_url(
    url: str,
    model_name: str,
    reason: str = "Unknown Error",
    raw_html: Optional[Union[bytes, str]] = None
) -> None:
    # raw_html が渡されている場合は再 requests.get を一切行わず直接保存
    if raw_html is not None:
        html_bytes = raw_html.encode("utf-8") if isinstance(raw_html, str) else raw_html
    else:
        # フォールバック (手元に HTML がない場合のみ再取得試行)
        ...
```

### 2.4 `main.py` CLI 例外処理改修
```python
# Before
except Exception as e:
    logging.exception(f"Error during crawl execution: {e}")
sys.exit(0)

# After
except Exception as e:
    tb = traceback.format_exc()
    logging.exception(f"Error during crawl execution: {e}")
    # 障害レポーターへ記録
    FailureReporter.record_job_failure(
        company=company,
        property_type=prop_type,
        error_type=type(e).__name__,
        error_message=str(e),
        exit_code=1,
        traceback_str=tb
    )
    sys.exit(1)
```

### 2.5 `run_all_crawlers.py` でのリアルタイム監視 & Slack `#dev-agent` トリガー
- `active_processes` のループ内で、`exit_code != 0` または `0 items scraped (Zero count failure)` 検知時に直ちに `FailureReporter.record_job_failure` を呼び出し。
- 全ジョブ終了後、失敗件数が 1 件以上ある場合:
  ```python
  if failed_list:
      trigger_msg = (
          f"[AGY-REQ:AUTO-HEAL] @DevAgent 【クローリング障害自動検知】\n"
          f"本日 ({today_str}) のクローリングで {len(failed_list)} 件の異常を検知しました。\n"
          f"GCSから障害情報を一括取得して自動修復してください。\n"
          f"コマンド: python src/crawler/scripts/debug_tools/fetch_run_failures.py --date {today_str}"
      )
      send_slack_message(channel="#dev-agent", message=trigger_msg)
  ```

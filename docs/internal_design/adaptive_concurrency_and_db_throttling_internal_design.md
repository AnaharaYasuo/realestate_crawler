# コンテナ内並列度最適化・適応型詳細並列度およびDB過負荷制御 内部設計書 (Issue #795)

## 1. モジュール構成と役割

```
src/crawler/
├── package/
│   ├── api/
│   │   ├── api.py                    # _getPararellLimit(), _fetch_detail_item(), _save_item_with_retry() 連携
│   │   └── adaptive_concurrency.py   # [新規] 動的並列度計算 & DBサーキットブレーカー
│   └── utils/
│       └── crawler_scheduler.py      # ジョブ選択と並行度補助
└── scripts/
    └── ops/
        └── run_all_crawlers.py       # デフォルト並行度 9 への引き上げ、稼働中ジョブ数の共有
```

## 2. 詳細クラス・関数設計 (`adaptive_concurrency.py`)

### 2.1 `AdaptiveConcurrencyController`
コンテナ内のアクティブジョブ数やDB負荷状況を監視・管理するシングルトン/ユーティリティクラス。

```python
class AdaptiveConcurrencyController:
    # 状態ファイルパス (コンテナ内共有)
    STATE_FILE = "/tmp/crawler_concurrency_state.json"
    
    @classmethod
    def calculate_detail_concurrency(cls, active_jobs_count: int | None = None) -> int:
        """
        アクティブジョブ数に基づき、1ジョブあたりの適正な詳細並列度を算出する。
        - CLOUD_DETAIL_CONCURRENCY が設定されている場合は優先
        - 1ジョブ: 15
        - 2ジョブ: 12
        - 3〜4ジョブ: 8
        - 5〜6ジョブ: 5
        - 7ジョブ以上: 4 (下限)
        """
        ...

    @classmethod
    def record_db_overload(cls, error_type: str, error_msg: str) -> None:
        """
        DB接続エラー検知時に呼び出され、過負荷フラグとタイムスタンプを記録。
        クールダウン期間（例: 60秒間）は詳細並列度を最小値（2）に強制抑制する。
        """
        ...

    @classmethod
    def is_throttled(cls) -> bool:
        """現在スロットリング中（過負荷発生からクールダウン内）かどうかを判定"""
        ...
```

### 2.2 `api.py` との統合点
1. **`_getPararellLimit(self)`**:
   - `CLOUD_DETAIL_CONCURRENCY` が環境変数にあればそれを尊重。
   - なければ `AdaptiveConcurrencyController.get_current_limit()` を呼び出してセマフォ数を決定。
2. **`_save_item_with_retry(self, item, max_retries=3)`**:
   - `OperationalError` 発生時、`AdaptiveConcurrencyController.is_overload_error(e)` を判定。
   - 該当する場合、`record_db_overload()` をトリガーして即座にスロットリングを開始し、`sleep(attempt * 2 + 2)` でバックオフ。

### 2.3 `run_all_crawlers.py` との統合点
- `default_parallel = 9` に変更。
- 新規プロセス起動時および終了回収時に、アクティブプロセス数（`len(active_processes)`）を状態ファイル等へ記録、または環境変数 `CONTAINER_ACTIVE_JOBS` を子プロセスに渡す。

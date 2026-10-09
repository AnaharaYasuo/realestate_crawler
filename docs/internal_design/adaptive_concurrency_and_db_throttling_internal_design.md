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

### 2.4 WAF防護対象サイトの並行度キャップ・アクセスディレイ設計 (Issue #804, Issue #807)
- **`AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS`**:
  ```python
  SITE_CONCURRENCY_CAPS = {
      "nomura": 2,
      "mitsui": 2,
      "smtrc": 2,
  }
  ```
  - `get_effective_concurrency(company: str | None = None, active_jobs: int | None = None) -> int` で、対象サイト名がキャップ指定されている場合は `min(calculated_concurrency, cap)` を適用する。
- **アクセスディレイ (`api.py`)**:
  - `SITE_DOWNLOAD_DELAYS = {"nomura": 1.0, "mitsui": 1.0, "smtrc": 1.0}` を定義し、`_fetch_detail_item` 内での詳細ページ取得前に `await asyncio.sleep(delay)` を挿入。
- **smtrc WAF 403 対策 (`smtrcParser.py`)**:
  - `smtrc` は Bot判定WAFにより 403 を返却する場合があるため、HTTPヘッダーの適正化および必要に応じた Playwright ステルス取得フォールバックを実装。

### 2.5 パーサー不整合および抽出例外修復設計 (Issue #804)
1. **`TokyuInvestmentApartmentParser`**:
   - `baseParser.py` の `clean_parsed_item()` 内で、`_guard_gross_yield()` を `validate_extracted_fields()` より先に呼び出す。
   - モデル定義（`TokyuInvestmentApartment`）で `grossYield` や `annualRent` が `null=True` の場合、かつ元ページに賃料情報が存在しない場合はバリデーションエラーとして扱わず許容する。
2. **`MitsuiInvestmentApartmentParser`**:
   - `_delegate_shumoku_parser` において、`shumoku` に「土地」が含まれる場合、または `url` に `/tochi/` が含まれる場合は `SkipPropertyException("土地物件のためスキップ")` を発生させる。
3. **`AthomeTochiParser`**:
   - `TochiParserBase.get_tochi_menseki_str()` を呼び出すことで「敷地面積」「区画面積」「面積」のフォールバックを有効化。

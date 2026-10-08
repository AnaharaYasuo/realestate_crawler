# 内部設計書: ログ出力改善・TRACE/DEBUG実装アーキテクチャ (Issue #783)

## 1. `logging_config.py` における TRACE 実装詳細

### 1.1 TRACE レベルの登録
標準ライブラリの `logging` にカスタムレベル `TRACE = 5` を登録する：
```python
TRACE_LEVEL_NUM = 5
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")

def _logging_trace(self, message, *args, **kwargs):
    if self.isEnabledFor(TRACE_LEVEL_NUM):
        self._log(TRACE_LEVEL_NUM, message, args, **kwargs)

def _module_trace(message, *args, **kwargs):
    logging.log(TRACE_LEVEL_NUM, message, *args, **kwargs)

logging.Logger.trace = _logging_trace
logging.trace = _module_trace
```

### 1.2 structlog との連携
- structlog の `add_log_level` プロセッサは、標準ロガーまたはイベント辞書の `level` フィールドを参照する。
- `structlog.BoundLogger` に対しても `trace` メソッドを動的あるいはラッパー経由で認識させる、もしくは `logger.bind().msg(...)` / `logger.log(TRACE_LEVEL_NUM, ...)` をサポートする。
- structlog において直接 `logger.trace(...)` が呼べるよう、`structlog.BoundLogger.trace = ...` を提供する。

### 1.3 GCP Cloud Logging フィールドマッピング
```python
severity_map = {
    "TRACE": "DEBUG",
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARN": "WARNING",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
    "FATAL": "CRITICAL",
    "EXCEPTION": "ERROR",
}
```

## 2. ログ呼び出しの適正化詳細

### 2.1 パーサー系 (`src/crawler/package/parser/`)
- `getPropertyListXpath`, `getPropertyListNextPageUrl` のセレクター出力: `logging.info(...)` ➔ `logging.trace(...)`
- 個別詳細リンク一致 `Match detail link: ...`: `logging.info(...)` ➔ `logging.debug(...)`
- 掲載終了検知 `MSG_LISTING_ENDED_PREFIX`: `logging.info(...)` ➔ `logging.debug(...)`
- 動的種別切り替え `[PropertyTypeSwitch]`: `logging.info(...)` ➔ `logging.debug(...)`

### 2.2 ルート系 (`src/crawler/routes/`)
- `Start mitsuiMansionStart`, `Success ...` などの各エンドポイント入出ログ: `logging.info(...)` ➔ `logging.debug(...)`

### 2.3 APIロガー系 (`src/crawler/package/utils/api_logger.py`)
- `[API Request]`, `[API Response]`: 正常系（2xx）は `logging.debug(...)` へ変更。4xxは `WARNING`、5xxは `ERROR`。

### 2.4 print 文の置換
- `src/crawler/main.py`: `print(f"Received signal {signum}...")` ➔ `logging.info(...)`
- `src/crawler/package/api/api.py`: `print("stop.flag found...")` ➔ `logger.info(...)`

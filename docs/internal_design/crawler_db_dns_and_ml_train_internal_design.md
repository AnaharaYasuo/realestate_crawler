# 内部設計: クローラーDB監視DNS堅牢化 & ML再学習インポート修復 (Issue #892)

## 1. モジュール変更詳細

### 1.1 `src/crawler/scripts/ops/run_all_crawlers.py`
- `resolve_db_endpoint()` の修正:
  - 取得したホスト名 `host` が IP アドレス形式でない場合（例: `db` 等のドメイン/サービス名）、`socket.gethostbyname(host)` を実行して IP アドレスを取得。
  - 名前解決に成功した場合は、監視用ホストとして解決済み IP を返却。
  - 例外発生時は元の `host` をそのまま返却（フォールバック）。
- `DbLivenessMonitor`:
  - `self.target_ip`: 初回解決済み IP または `self.host`。
  - `_probe()` 内のソケット接続では `(self.target_ip, self.port)` を使用し、毎回の不要な DNS クエリを物理排除。

### 1.2 `src/crawler/package/ml/train.py`
- モジュール冒頭に以下を配置:
  ```python
  import os
  import sys

  _cur = os.path.abspath(__file__)
  while True:
      _parent = os.path.dirname(_cur)
      if _parent == _cur:
          break
      if os.path.exists(os.path.join(_parent, "setup_env.py")):
          if _parent not in sys.path:
              sys.path.insert(0, _parent)
          import setup_env  # noqa: F401
          break
      _cur = _parent
  ```
- これにより、プロジェクトルートや `/app` からの直接起動、サブプロセス起動でも常に正しく `package` がロードされる。

### 1.3 `docker-compose.yml`
- `CRAWLER_PARALLEL=${CRAWLER_PARALLEL:-5}` に調整。

# 要件定義書: マシン余剰リソースに応じた動的並列度調整 (Issue #895)

## 1. 背景と課題
- WSL2環境（メモリ制限4GB・Swap 2GB等）やリソース制約のあるマシンにおいて、`run_all_crawlers.py` の既定並列度（`parallel=9`, `playwright_parallel=3`）でジョブを立ち上げると、Chromium プロセスおよび Python プロセス、MySQL コンテナのメモリ消費により WSL2 の仮想メモリ上限に達する。
- メモリ枯渇が発生すると WSL2 のネットワークスタックや Docker デーモンが応答不能（`500 Internal Server Error`, `no route to host`）になり、全体の実行が停止・ハングする。

## 2. 目的
- クローラー起動時にホスト環境・コンテナ環境の利用可能メモリ（cgroup memory limit、またはシステム物理空きメモリ）を動的に判定し、安全な並行プロセス数（`parallel`, `playwright_parallel`）を自動調整する。
- これにより、低スペック・メモリ制約環境では安全上限（例: メモリ制限 4GB 以下なら `parallel=3`, `playwright_parallel=1`）で確実に完遂させ、十分なメモリがある環境や環境変数・CLI引数指定時はその設定を優先する。

## 3. 要件一覧
- **REQ-001: 動的リソース検知**
  - cgroup v2 (`/sys/fs/cgroup/memory.max`)、cgroup v1 (`/sys/fs/cgroup/memory/memory.limit_in_bytes`)、および OS 利用可能メモリ (`os.sysconf` / `/proc/meminfo` / `psutil`) を参照し、実行環境の実質利用可能メモリ（MB）を取得する。
- **REQ-002: 安全並列度の自動算出**
  - 利用可能メモリ `<= 4096MB` (4GB以下):
    - `parallel = 3`
    - `playwright_parallel = 1`
  - 利用可能メモリ `<= 8192MB` (4GB超〜8GB以下):
    - `parallel = 5`
    - `playwright_parallel = 2`
  - 利用可能メモリ `> 8192MB` または制限なし:
    - `parallel = 9` (既定値)
    - `playwright_parallel = 3` (既定値)
- **REQ-003: 設定優先順位**
  - `CLI引数` > `環境変数 (CRAWLER_PARALLEL, CRAWLER_PLAYWRIGHT_PARALLEL)` > `リソース検知に基づく安全並列度`。
- **REQ-004: ロギングと可視性**
  - 起動時に検知した利用可能メモリ量と適用された並列度を INFO レベルで明示ログ出力する。

# CI/PR 監視における無制限 --watch 禁止および有限タイムアウトポーリング強制 内部設計書 (Issue #602)

## 1. モジュール構成
- ファイルパス: `src/crawler/scripts/debug_tools/check_pr_ci_status.py`
- 単体テスト: `src/crawler/tests/unit/test_check_pr_ci_status.py`

## 2. 関数仕様

### 2.1 `parse_pr_checks_output(output: str) -> dict[str, list[dict[str, str]]]`
`gh pr checks <PR_NUM>` のタブ区切りまたはスペース区切りテキスト出力をパースし、カテゴリごとに分類する。

- **戻り値**:
  ```python
  {
      "passed": [{"name": str, "status": str, "url": str, ...}],
      "pending": [{"name": str, "status": str, "url": str, ...}],
      "failed": [{"name": str, "status": str, "url": str, ...}],
      "blocked": [{"name": str, "status": str, "url": str, ...}],
  }
  ```

### 2.2 `fetch_pr_checks(pr_number: int, timeout: float = 10.0) -> tuple[int, str, str]`
`gh pr checks <PR_NUM>` を有限タイムアウト付きで実行する。

- 引数:
  - `pr_number`: 対象PR番号
  - `timeout`: タイムアウト秒（最大10秒、NFR-021上限）
- 戻り値:
  - `(returncode, stdout, stderr)`
- 例外制御:
  - `subprocess.TimeoutExpired`: タイムアウトを検知し、安全にプロセスをkillして例外送出またはエラータプルを返却。

### 2.3 `poll_pr_checks(pr_number: int, max_attempts: int = 20, interval: int = 15, timeout: float = 10.0) -> dict`
指定間隔でポーリングを実行し、全完了または異常検知時に早期終了する。

- 終了条件:
  1. `pending` が 0 かつ `failed` が 0 かつ `blocked` が 0 ➔ SUCCESS (status="SUCCESS")
  2. `failed` > 0 ➔ 即時 FAILURE (status="FAILURE")
  3. `blocked` > 0 ➔ 即時 BLOCKED (status="BLOCKED")
  4. `attempts >= max_attempts` ➔ TIMEOUT (status="TIMEOUT")

## 3. エラーハンドリングとリトライ
- `gh` コマンドが一時的なネットワークエラーで失敗した場合、リトライカウントを消費して次回ループで再試行。
- スタック状態（`action_required` 等）を検知した場合、該当ランIDを抽出してコンソールに診断案内を出力。

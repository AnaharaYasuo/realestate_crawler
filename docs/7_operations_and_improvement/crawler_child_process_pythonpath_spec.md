# クローラー子プロセス実行環境・PYTHONPATH仕様書

## 1. 概要
`run_all_crawlers.py` は、各クローラータスクを独立したプロセス（`main.py`）として並行起動する。
ホスト環境（Windows等）や埋め込みPython環境において、子プロセスが `src/crawler/package` を解決できるよう、パス解決保証の仕様を定義する。

## 2. 仕様定義
1. **`main.py` 内部での動的ルート補正**:
   - `main.py` 起動時に `os.path.dirname(os.path.abspath(__file__))` を `sys.path[0]` に追加し、呼び出し元の実行カレントディレクトリや環境変数に左右されず `package` を import 可能とする。
2. **`run_all_crawlers.py` の子プロセス環境変数伝播**:
   - `subprocess.Popen` 呼び出し時、`env` 引数に `child_env` を明示的に指定。
   - `child_env["PYTHONPATH"]` に `_crawler_dir`（`src/crawler`）が先頭に含まれるよう結合して渡す。

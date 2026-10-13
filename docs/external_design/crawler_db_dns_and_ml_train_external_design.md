# 外部設計: クローラーDB監視DNS堅牢化 & ML再学習インポート修復 (Issue #892)

## 1. 外部インターフェース仕様

### 1.1 DB Liveness 監視の挙動
- **入力**: DB ホスト名（例: `db`, `10.0.0.10`, `127.0.0.1`）、ポート番号（例: `3306`, `6033`）
- **動作仕様**:
  - `resolve_db_endpoint()` 呼び出し時、初期化時にホスト名を IP アドレスに解決（`socket.gethostbyname`）。
  - IP 解決に成功した場合、監視対象エンドポイントとしてその IP アドレスを採用。
  - プローブ時は毎回 DNS 解決を行わず、解決済み IP に対して TCP ソケット接続テストを実施。
  - 外部 DNS が過負荷・一時的にダウンしても、DB コンテナ自体の生存確認には一切影響を与えない。

### 1.2 ML 再学習エントリ (`package/ml/train.py`)
- **起動コマンド**: `python /app/src/crawler/package/ml/train.py`
- **動作仕様**:
  - 実行環境のカレントディレクトリが `/app` やリポジトリルートであっても、冒頭で `setup_env.py` を探索・インポートし、`PYTHONPATH` を補正。
  - `from package.ml.training.pipeline import run_training` が正常に成功し、モデル学習が完走する。

### 1.3 ローカル実行時の並行度環境変数
- `docker-compose.yml` における `CRAWLER_PARALLEL` のデフォルトを 5 に調整し、Docker DNS およびローカルネットワークの過負荷を未然に防止。

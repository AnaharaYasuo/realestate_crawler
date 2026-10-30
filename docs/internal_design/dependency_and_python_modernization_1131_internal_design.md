# 依存ライブラリおよび Python 実行環境の最新化・セキュリティ対策 内部設計書

## 1. 依存ライブラリ更新対象一覧
Dependabot PR #1121 等で検出されたセキュリティパッチおよび最新安定バージョンを反映する：

- `aiohttp`: 3.14.3 -> 3.14.5 (セキュリティ Fix 適用)
- `asgiref`: 3.12.1 -> 3.13.0
- `certifi`: 2026.7.22 -> 2026.10.23 (最新ルート証明書)
- `chardet`: 7.6.0 -> 7.7.0
- `django`: 5.2.17 -> 5.2.18 (セキュリティ・バグ修正)
- `importlib-metadata`: 9.0.1 -> 10.1.0
- `iniconfig`: 2.3.0 -> 2.3.1
- `multidict`: 6.9.1 / 7.1.0 -> 7.2.1
- `newrelic`: 9.10.0 -> 14.1.0
- `pluggy`: 1.6.0 -> 1.7.0
- `pydantic`: 2.13.5 -> 2.14.1
- `pytz`: 2026.4 -> 2026.5
- `tomli`: 2.4.1 -> 2.5.0
- `tzdata`: 2026.4 -> 2026.6
- `zipp`: 4.1.0 -> 4.1.2
- `pillow`: 12.3.0 -> 13.0.0 (画像処理関連のセキュリティ Fix)
- `pandas`: 3.0.6 -> 3.1.0
- `google-genai`: 2.28.0 -> 2.33.0
- `google-cloud-compute`: 1.55.0 -> 1.56.0
- `google-cloud-storage`: 3.16.0 -> 3.17.1
- `boto3`: 1.43.108 -> 1.43.120
- `botocore`: 1.43.108 -> 1.43.120
- `playwright`: 1.63.0 -> 1.64.1
- `brotli`: 1.2.0 -> 1.2.1
- `ruff`: 0.16.10 -> 0.17.3
- `pytest`: 9.1.1 -> 9.2.0
- `pytest-asyncio`: 1.4.0 -> 1.4.1
- `python-dateutil`: 2.9.0.post0 -> 3.0.0
- `narwhals`: 2.26.0 -> 2.28.0
- `pip`: 26.2.1 -> 26.2.2

## 2. Dockerfile 設計
- ベースイメージ: `python:3.11-slim-bookworm` (Debian 12 Bookworm 安定版で最新のセキュリティパッチ `apt-get upgrade -y` を適用)
- `pip install --no-cache-dir --upgrade pip` (26.2.2 へ更新)
- `pip install --no-cache-dir "poetry>=2.0,<3" "poetry-plugin-export>=1.8"`
- `poetry install --no-ansi --no-root`
- `playwright install --with-deps chromium` (1.64.1 互換 Chromium)

## 3. テスト・検証戦略
- `pytest-xdist` をローカル環境に整備
- パーサー単体テスト（主要ポータルパーサー、クローラーユニットテスト）の実行
- requirements.txt と poetry.lock の完全一致検証
- PR 作成後の GitHub Actions（Review Gate, Snyk, CodeQL, Trivy, Semgrep, Checkov, Parser Tests）の全パス確認

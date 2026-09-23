# 標準のPython 3.11 Slimイメージ（Debian Bookworm安定版）を使用
FROM python:3.14-slim-bookworm

# 作業ディレクトリの設定
WORKDIR /app

# 環境変数の設定
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING="utf-8"
ENV LANG="C.UTF-8"
ENV LC_ALL="C.UTF-8"
# Poetry: コンテナ内では venv を作らずシステムサイトへインストール
ENV POETRY_VIRTUALENVS_CREATE=false
ENV POETRY_NO_INTERACTION=1

# 依存定義のみ先にコピー（レイヤーキャッシュ効率化）
COPY src/crawler/pyproject.toml src/crawler/poetry.lock /app/

# システム依存関係のインストール, Poetry経由のPythonパッケージインストール, ビルドツールの削除を一括で実行
# ※ LightGBMの実行に必要な libgomp1 を明示的にインストールし保持します
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    curl \
    wget \
    git \
    procps \
    cron \
    libgomp1 \
    && apt-get upgrade -y \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "poetry>=2.0,<3" \
    && poetry install --no-ansi --no-root \
    && apt-get purge -y --auto-remove build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Playwrightとその依存関係（Chromium用OSライブラリ）のインストール
# ※ ソースコード変更で再実行されないよう、COPY config/src より前に実行してレイヤーキャッシュを保護
RUN playwright install --with-deps chromium

# 設定ファイルおよびソースコードのコピー
COPY config/ /app/config/
COPY src/ /app/src/

# デフォルトのシェルをdashからbashへ変更（disownコマンド等のサポートのため）
RUN ln -sf bash /bin/sh

# ポートの公開
EXPOSE 8000

# アプリケーションの実行
CMD ["python", "src/crawler/main.py"]

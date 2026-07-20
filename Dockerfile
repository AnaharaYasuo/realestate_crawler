# 標準のPython 3.11 Slimイメージ（Debian Bookworm安定版）を使用
FROM python:3.11-slim-bookworm

# 作業ディレクトリの設定
WORKDIR /app

# 環境変数の設定
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 依存ファイルのみコピー
COPY src/crawler/requirements.txt /app/

# システム依存関係のインストール, Pythonパッケージインストール, ビルドツールの削除を一括で実行
# ※ LightGBMの実行に必要な libgomp1 を明示的にインストールし保持します
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    curl \
    wget \
    git \
    procps \
    cron \
    libgomp1 \
    libexpat1 \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --default-timeout=1000 --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ソースコードのコピー
COPY src/ /app/src/

# Playwrightとその依存関係（Chromium用OSライブラリ）のインストール
RUN playwright install --with-deps chromium

# デフォルトのシェルをdashからbashへ変更（disownコマンド等のサポートのため）
RUN ln -sf bash /bin/sh

# ポートの公開
EXPOSE 8000

# アプリケーションの実行
CMD ["python", "src/crawler/main.py"]

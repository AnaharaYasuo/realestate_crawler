# 標準のPython 3.11 Slimイメージを使用
FROM python:3.11-slim

# 作業ディレクトリの設定
WORKDIR /app

# 環境変数の設定
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# システム依存関係のインストール
RUN apt-get update && apt-get install -y \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ソースコードのコピー
COPY src/ /app/src/

# 依存関係のインストール
RUN pip install --default-timeout=1000 --no-cache-dir -r src/crawler/requirements.txt

# Playwrightとその依存関係（Chromium用OSライブラリ）のインストール
RUN playwright install --with-deps chromium

# ポートの公開
EXPOSE 8000

# アプリケーションの実行
CMD ["python", "src/crawler/main.py"]

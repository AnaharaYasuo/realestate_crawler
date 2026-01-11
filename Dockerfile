# 標準のPython 3.10 Slimイメージを使用
FROM python:3.10-slim

# 作業ディレクトリの設定
WORKDIR /app

# 環境変数の設定
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# システム依存関係のインストール
# mysqlclientのビルドに必要なライブラリを含める
RUN apt-get update && apt-get install -y \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ソースコードのコピー
# ディレクトリ構造に合わせて調整 (srcフォルダがあるため)
COPY src/ /app/src/

# 依存関係のインストール
RUN pip install --no-cache-dir -r src/crawler/requirements.txt

# ポートの公開
EXPOSE 8000

# アプリケーションの実行
CMD ["python", "src/crawler/main.py"]

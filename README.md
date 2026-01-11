# Realestate Crawler

このプロジェクトは、主要な不動産サイト（三井のリハウス、住友不動産販売、東急リバブル）から不動産物件情報を自動的に収集（スクレイピング）するためのツールです。

## 概要

ローカルAPIサーバーを構築し、HTTPリクエストを受け取ることで各サイトのクローリング・解析処理を実行します。収集したデータはDBへ保存されます。
本プロジェクトでは [Task](https://taskfile.dev/) と [Docker Compose](https://docs.docker.com/compose/) を使用して環境構築および実行を行います。

## 前提条件

*   [Docker Desktop](https://www.docker.com/products/docker-desktop) がインストールされ、起動していること
*   [Task](https://taskfile.dev/installation/) コマンドがインストールされていること

## セットアップ & 起動

初回実行時や、環境をリセットしてクリーンな状態で開始したい場合は `init` タスクを使用します。

```bash
task init
```
これにより、Dockerイメージのビルド、コンテナの起動、およびデータベースの初期セットアップ（テーブル作成など）が自動的に行われます。

## 使用方法

### 1. サーバーの起動 (通常時)

すでにセットアップが完了しており、サーバーを再起動したい場合は以下のコマンドを使用します。

```bash
task default
```
バックグラウンドでサーバーが起動し、`http://localhost:8000` で待機状態になります。

### 2. クローラーの実行

`task crawl` コマンドでクローラーを起動します。`COMPANY` (対象サイト) と `TYPE` (物件種別) を指定してください。

**実行例:**

```bash
# 三井のリハウス / マンション
task crawl COMPANY=mitsui TYPE=mansion
```

**パラメータ:**

*   **COMPANY**:
    *   `mitsui`: 三井のリハウス
    *   `sumifu`: 住友不動産販売
    *   `tokyu`: 東急リバブル
    *   `nomura`: ノムコム・プロ (投資用)
*   **TYPE**:
    *   `mansion`: 中古マンション
    *   `tochi`: 土地
    *   `kodate`: 戸建て

**対応表:**

| COMPANY | TYPE |
| :--- | :--- |
| `mitsui` | `mansion`, `tochi`, `kodate` |
| `sumifu` | `mansion`, `tochi`, `kodate` |
| `tokyu` | `mansion` |
| `nomura` | `mansion`, `tochi`, `kodate`, `apartment`, `building` |

### 3. ログの確認

アプリケーションのログをリアルタイムで確認するには：

```bash
task logs
```

### 4. サーバーの停止

アプリケーションを停止するには：

```bash
task stop
```

---


## 仕様ドキュメント (Specifications)

詳細な仕様については、以下のドキュメントを参照してください。

*   **[クローラー仕様書 (Crawler Specification)](docs/crawler_spec.md)**
    *   アーキテクチャ概要 (Fire-and-Forget, 並列制御)
    *   エラーハンドリング & リトライロジック
    *   各サイトの詳細な処理フローとエンドポイント
    *   HTML解析ロジック詳細
*   **[データベース定義書 (Database Schema)](docs/database_schema.md)**
    *   テーブル・カラム定義一覧
    *   サイトごとの取得項目対応表 (三井, 住友, 東急)

---

## Task コマンド一覧

`Taskfile.yml` に定義されている主なタスクです。

*   `task default`: アプリケーション起動 (`docker-compose up -d`)
*   `task init`: 初期セットアップ (`docker-compose up -d --build` + DB setup)
*   `task logs`: ログ表示
*   `task stop`: アプリケーション停止
*   `task crawl`: クローラー実行 (Usage: `task crawl COMPANY=... TYPE=...`)
*   `task flask-start`: アプリケーションコンテナのみ起動
*   `task flask-stop`: アプリケーションコンテナのみ停止

## ディレクトリ構成

*   `src/crawler/`: アプリケーションコード
    *   `main.py`: エントリーポイント
    *   `package/`: クローラーロジック
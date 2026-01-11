# Realestate Crawler

[![DeepWiki](https://deepwiki.com/badge-maker?url=https%3A%2F%2Fdeepwiki.com%2FAnaharaYasuo%2Frealestate_crawler)](https://deepwiki.com/AnaharaYasuo/realestate_crawler)

このプロジェクトは、5社の主要な不動産サイトから不動産物件情報を自動的に収集（スクレイピング）し、データベースに保存するためのツールです。

## 概要

### システムの目的

本システムは以下の2つの主要目的を持ちます：

1. **データ収集**: 5社の不動産サイトから非同期HTTPリクエストとHTML解析により物件情報を自動取得
2. **データ永続化**: 正規化されたデータベーススキーマ（16-17テーブル）に変換・保存

### 対応サイトと物件種別

| 会社 | 投資用 | マンション | 戸建て | 土地 | 備考 |
|------|--------|-----------|--------|------|------|
| 三井のリハウス | ✅ | ✅ | ✅ | ✅ | 全種別対応 |
| 住友不動産販売 | ✅ | ✅ | ✅ | ✅ | 全種別対応 |
| 東急リバブル | ✅ | ✅ | ✅ | ✅ | 全種別対応 |
| ミサワホーム不動産 | ✅ | ✅ | ✅ | ✅ | 全種別対応 |
| 野村の仲介+ | ✅ | ✅ | ✅ | ✅ | 全種別対応 |

**合計**: 5社 × 4種別 = 20通りのクローラー設定が可能

### システムの特徴

ローカルAPIサーバーを構築し、HTTPリクエストを受け取ることで各サイトのクローリング・解析処理を実行します。収集したデータはMySQLデータベースへ保存されます。
本プロジェクトでは [Task](https://taskfile.dev/) と [Docker Compose](https://docs.docker.com/compose/) を使用して環境構築および実行を行います。

## 前提条件

*   [Docker Desktop](https://www.docker.com/products/docker-desktop) がインストールされ、起動していること
*   [Task](https://taskfile.dev/installation/) コマンドがインストールされていること

## セットアップ & 起動

### セットアップフロー概要

`task init` コマンドは以下の3ステップを自動実行します：

1. **Dockerイメージビルド**
   - `python:3.10-slim` ベースイメージ使用
   - MySQLクライアントライブラリのインストール
   - Python依存関係のインストール（aiohttp, BeautifulSoup4, Django等）

2. **コンテナ起動**
   - `app` コンテナ: アプリケーションサーバー（ポート8000）
   - `mysql` コンテナ: データベースサーバー（ポート3306）

3. **データベース初期化**
   - `src/crawler/db_setup.py` を実行
   - Djangoマイグレーションにより16-17テーブルを作成

### 初回セットアップ

初回実行時や、環境をリセットしてクリーンな状態で開始したい場合は `init` タスクを使用します。

```bash
task init
```

### 期待される出力

```bash
[+] Building 23.5s (10/10) FINISHED
[+] Running 2/2
 ✔ Container realestate_crawler-mysql-1  Started
 ✔ Container realestate_crawler-app-1    Started
Operations to perform:
  Apply all migrations: package
Running migrations:
  Applying package.0001_initial... OK
```

### 検証方法

コンテナが正常に起動しているか確認：

```bash
docker compose ps
```

両方のコンテナが `Up` 状態であればセットアップ成功です。

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
| `mitsui` | `mansion`, `tochi`, `kodate`, `investment` |
| `sumifu` | `mansion`, `tochi`, `kodate`, `investment` |
| `tokyu` | `mansion`, `tochi`, `kodate`, `investment` |
| `nomura` | `mansion`, `tochi`, `kodate`, `investment` |
| `misawa` | `mansion`, `tochi`, `kodate`, `investment` |

---

## システムアーキテクチャ概要

### Fire-and-Forget パターン

本システムは「Fire-and-Forget」方式の非同期API呼び出しを採用しています。

**特徴:**
- **再帰的呼び出し**: Start → Region → List → Detail の各ステップが次のステップをHTTPリクエストで起動
- **即時レスポンス**: 各APIは処理完了を待たず、即座にHTTP 200を返却
- **タイムアウト許容**: 3秒のタイムアウト設定。接続確立時点で成功とみなす
- **サーバーレス対応**: Google Cloud Functions等での分散実行が可能

**処理フロー:**
```
User → task crawl
  ↓
Start API (HTTP 200即時返却)
  ↓ (非同期POST)
Region API (HTTP 200即時返却)
  ↓ (非同期POST × N地域)
List API (HTTP 200即時返却)
  ↓ (非同期POST × M物件)
Detail API → DB保存
```

### 並列処理設定

| パラメータ | 値 | 説明 |
|-----------|-----|------|
| `FIRE_AND_FORGET_TIMEOUT` | 3.0秒 | 次ステップ起動時のタイムアウト |
| `DEFAULT_PARARELL_LIMIT` | 2 | デフォルト並列数 |
| `DETAIL_PARARELL_LIMIT` | 6 | 詳細ページ取得時の並列数 |
| `TCP_CONNECTOR_LIMIT` | 100 | TCP接続プール上限 |

---

## 技術スタック (Tech Stack)

### コア言語
- **Python 3.10** (`python:3.10-slim` Dockerイメージ)

### HTTP & パース
- **aiohttp**: 非同期HTTPクライアント（JavaScriptレンダリング不要）
  - 役割: 不動産サイトからHTMLを取得
  - ファイル: `src/crawler/package/api/api.py`
- **BeautifulSoup4 (bs4)**: HTML解析・データ抽出
  - 役割: HTMLから物件情報を抽出
  - ファイル: `src/crawler/package/parser/*Parser.py`
- **lxml**: BeautifulSoup4のパーサーエンジン

### データ層
- **Django**: ORM（モデル定義・マイグレーション）
  - 役割: データベーススキーマ管理
  - ファイル: `src/crawler/package/models/`
- **mysqlclient**: MySQLデータベースアダプター
- **MySQL 8.0**: リレーショナルデータベース（Dockerコンテナ）

### インフラ
- **Docker / Docker Compose**: コンテナ化・オーケストレーション
  - 設定: `docker-compose.yml`, `Dockerfile`
- **Task (Taskfile)**: CLIタスク自動化
  - 設定: `Taskfile.yml`

### テスト
- **pytest**: テストフレームワーク
  - テスト: `src/crawler/tests/`

> [!NOTE]
> 以前のバージョンで使用していた Playwright (JavaScriptレンダリング) は、軽量化と安定性向上のため削除されました。
> 現在は `aiohttp` + `BeautifulSoup4` による高速な静的HTML解析を採用しています。

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

## トラブルシューティング

### コンテナ起動失敗

**症状**: `task init` 実行後にコンテナが起動しない

**原因と対処:**
1. **ポート競合**: 8000番または3306番ポートが既に使用されている
   ```bash
   # ポート使用状況確認（Windows）
   netstat -an | findstr "8000"
   netstat -an | findstr "3306"
   ```
   対処: 使用中のプロセスを停止するか、`docker-compose.yml` でポート番号を変更

2. **Docker Desktop未起動**: Docker Desktopが起動していない
   
   対処: Docker Desktopを起動してから再実行

### データベース接続エラー

**症状**: `OperationalError: (2003, "Can't connect to MySQL server")`

**原因と対処:**
1. **MySQLコンテナ未起動**: コンテナが起動していない
   ```bash
   docker compose ps
   # mysql コンテナが Up でない場合
   task default
   ```

2. **接続数上限**: 同時接続数が上限に達している
   
   対処: `task stop` → `task default` で再起動

### クローラー実行後にデータが入らない

**症状**: `task crawl` 実行後、データベースにレコードが追加されない

**確認手順:**
1. **ログ確認**:
   ```bash
   task logs
   ```
   エラーメッセージを確認

2. **パースエラー**: `ReadPropertyNameException` が出力されている場合
   - サイトのHTML構造が変更された可能性
   - 該当パーサーの修正が必要

3. **ネットワークエラー**: `ClientConnectorError` が出力されている場合
   - 一時的なネットワーク障害
   - 自動リトライ（10秒後）が実行される

### パーサーテスト失敗

**症状**: `task test` でテストが失敗する

**対処:**
```bash
# 特定のパーサーのみテスト
docker compose exec -T app pytest src/crawler/tests/unit/test_mitsui_parser.py -v

# 詳細なログ出力
docker compose exec -T app pytest src/crawler/tests/unit/ -v -s
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

## Task コマンド完全リファレンス

| コマンド | 説明 | 内部動作 | 使用例 |
|---------|------|---------|--------|
| `task init` | 初期セットアップ | `docker compose up -d --build` + DB初期化 | 初回セットアップ時 |
| `task default` | サーバー起動 | `docker compose up -d` | 通常の起動 |
| `task stop` | サーバー停止 | `docker compose down` | 作業終了時 |
| `task crawl` | クローラー実行 | `curl POST http://localhost:8000/...` | `task crawl COMPANY=mitsui TYPE=mansion` |
| `task logs` | ログ表示 | `docker compose logs -f app` | デバッグ時 |
| `task test` | テスト実行 | `docker compose exec -T app pytest` | コード変更後 |

### 詳細な使用例

**初回セットアップ:**
```bash
task init
# 出力: Dockerイメージビルド → コンテナ起動 → DB初期化
```

**クローラー実行（複数パターン）:**
```bash
# 三井のリハウス - マンション
task crawl COMPANY=mitsui TYPE=mansion

# 住友不動産販売 - 投資用
task crawl COMPANY=sumifu TYPE=investment

# 東急リバブル - 戸建て
task crawl COMPANY=tokyu TYPE=kodate
```

**ログ監視（リアルタイム）:**
```bash
task logs
# Ctrl+C で終了
```

---

## 次のステップ

初めてのユーザーが次に学ぶべき内容：

### 1. システムの理解を深める
- **[クローラー仕様書](docs/crawler_spec.md)**: Fire-and-Forgetパターン、エラーハンドリング、各社の処理フロー
- **[データベース定義書](docs/database_schema.md)**: 17モデルの構造、Dual Storageパターン、Transportation Fields

### 2. 開発を始める
- **[開発者ガイド](docs/development_guide.md)**: 環境構築、デバッグ方法、新規パーサー追加手順
- **[API構造](docs/api_structure.md)**: APIエンドポイント構造、ルーティング、Fire-and-Forget実装詳細

### 3. より詳しく学ぶ
- **[内部設計](docs/internal_design.md)**: クラス図、シーケンス図、アーキテクチャ詳細
- **[リファクタリング提案](docs/refactoring_suggestions.md)**: コード改善のベストプラクティス

---

## ディレクトリ構成

*   `src/crawler/`: アプリケーションコード
    *   `main.py`: エントリーポイント
    *   `package/`: クローラーロジック
    *   `tests/`: テストコード
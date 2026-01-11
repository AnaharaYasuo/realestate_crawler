# クイックスタートガイド

このガイドでは、Realestate Crawlerを初めて使用する方向けに、環境構築から最初のクローラー実行までの手順を詳しく説明します。

## 前提条件

以下のツールがインストールされていることを確認してください：

### 1. Docker Desktop

**確認方法:**
```bash
docker --version
```

**期待される出力:**
```
Docker version 20.10.x, build xxxxx
```

**インストール:**
- Windows/Mac: [Docker Desktop](https://www.docker.com/products/docker-desktop)
- Linux: [Docker Engine](https://docs.docker.com/engine/install/)

### 2. Task CLI

**確認方法:**
```bash
task --version
```

**期待される出力:**
```
Task version: v3.x.x
```

**インストール:**
- Windows (Chocolatey): `choco install go-task`
- Mac (Homebrew): `brew install go-task/tap/go-task`
- Linux: [公式インストールガイド](https://taskfile.dev/installation/)

---

## ステップ1: プロジェクトのクローン

```bash
git clone https://github.com/AnaharaYasuo/realestate_crawler.git
cd realestate_crawler
```

---

## ステップ2: 初期セットアップ

### 2-1. Docker Desktopの起動確認

Docker Desktopが起動していることを確認してください。

**Windows:** タスクトレイにDockerアイコンが表示されている  
**Mac:** メニューバーにDockerアイコンが表示されている

### 2-2. 初期化コマンドの実行

```bash
task init
```

このコマンドは以下の処理を自動的に実行します：

1. **Dockerイメージのビルド** (約2-3分)
   - Python 3.10環境の構築
   - 必要なライブラリのインストール（aiohttp, BeautifulSoup4, Django等）

2. **コンテナの起動**
   - `app` コンテナ: アプリケーションサーバー（ポート8000）
   - `mysql` コンテナ: データベースサーバー（ポート3306）

3. **データベースの初期化**
   - Djangoマイグレーションの実行
   - 16-17個のテーブル作成

### 2-3. 期待される出力

```bash
[+] Building 23.5s (10/10) FINISHED
 => [internal] load build definition from Dockerfile
 => => transferring dockerfile: 1.23kB
 => [internal] load .dockerignore
 => => transferring context: 2B
 => [internal] load metadata for docker.io/library/python:3.10-slim
 => [1/5] FROM docker.io/library/python:3.10-slim
 => [2/5] RUN apt-get update && apt-get install -y ...
 => [3/5] WORKDIR /app
 => [4/5] COPY requirements.txt .
 => [5/5] RUN pip install --no-cache-dir -r requirements.txt
 => exporting to image
 => => exporting layers
 => => writing image sha256:...
 => => naming to docker.io/library/realestate_crawler-app

[+] Running 2/2
 ✔ Container realestate_crawler-mysql-1  Started    1.2s
 ✔ Container realestate_crawler-app-1    Started    1.5s

Operations to perform:
  Apply all migrations: package
Running migrations:
  Applying package.0001_initial... OK
```

### 2-4. セットアップの検証

コンテナが正常に起動しているか確認：

```bash
docker compose ps
```

**期待される出力:**
```
NAME                            IMAGE                      STATUS
realestate_crawler-app-1        realestate_crawler-app     Up
realestate_crawler-mysql-1      mysql:8.0                  Up
```

両方のコンテナが `Up` 状態であればセットアップ成功です。

---

## ステップ3: 最初のクローラー実行

### 3-1. クローラーの起動

三井のリハウスのマンション情報を取得してみましょう：

```bash
task crawl COMPANY=mitsui TYPE=mansion
```

### 3-2. 実行の確認

コマンド実行後、即座にHTTP 200が返却されます（Fire-and-Forgetパターン）：

```
HTTP/1.1 200 OK
```

これは処理が開始されたことを意味します。実際の処理は非同期で実行されます。

### 3-3. ログの監視

リアルタイムでクローリングの進捗を確認：

```bash
task logs
```

**期待されるログ出力:**
```
realestate_crawler-app-1  | INFO: Start API called for mitsui/mansion
realestate_crawler-app-1  | INFO: Fetching region pages...
realestate_crawler-app-1  | INFO: Found 47 regions
realestate_crawler-app-1  | INFO: Fetching list pages for region: 東京都
realestate_crawler-app-1  | INFO: Found 120 properties
realestate_crawler-app-1  | INFO: Fetching detail page: https://...
realestate_crawler-app-1  | INFO: Saved property: 〇〇マンション
```

ログ監視を終了するには `Ctrl+C` を押してください。

---

## ステップ4: データの確認

### 4-1. MySQLコンテナに接続

```bash
docker compose exec mysql mysql -u root -proot realestate_crawler
```

### 4-2. テーブル一覧の確認

```sql
SHOW TABLES;
```

**期待される出力:**
```
+--------------------------------------+
| Tables_in_realestate_crawler         |
+--------------------------------------+
| crawler_mitsumansion                 |
| crawler_mitsukodate                  |
| crawler_mitsutochi                   |
| crawler_mitsuinvestment              |
| crawler_sumifumansion                |
| ...                                  |
+--------------------------------------+
```

### 4-3. レコード数の確認

```sql
SELECT COUNT(*) FROM crawler_mitsumansion;
```

**期待される出力:**
```
+----------+
| COUNT(*) |
+----------+
|      120 |
+----------+
```

### 4-4. 最新のレコードを確認

```sql
SELECT propertyName, priceStr, address 
FROM crawler_mitsumansion 
ORDER BY inputDateTime DESC 
LIMIT 5;
```

### 4-5. MySQLから退出

```sql
EXIT;
```

---

## ステップ5: 他の会社・物件種別の実行

### 対応している組み合わせ

| 会社 (COMPANY) | 物件種別 (TYPE) |
|---------------|----------------|
| `mitsui` | `mansion`, `kodate`, `tochi`, `investment` |
| `sumifu` | `mansion`, `kodate`, `tochi`, `investment` |
| `tokyu` | `mansion`, `kodate`, `tochi`, `investment` |
| `misawa` | `mansion`, `kodate`, `tochi`, `investment` |
| `nomura` | `mansion`, `kodate`, `tochi`, `investment` |

### 実行例

```bash
# 住友不動産販売 - 投資用物件
task crawl COMPANY=sumifu TYPE=investment

# 東急リバブル - 戸建て
task crawl COMPANY=tokyu TYPE=kodate

# ミサワホーム不動産 - 土地
task crawl COMPANY=misawa TYPE=tochi

# 野村の仲介+ - マンション
task crawl COMPANY=nomura TYPE=mansion
```

---

## ステップ6: システムの停止

作業が終了したら、システムを停止します：

```bash
task stop
```

**期待される出力:**
```
[+] Running 2/2
 ✔ Container realestate_crawler-app-1    Removed    0.5s
 ✔ Container realestate_crawler-mysql-1  Removed    1.2s
```

---

## よくある失敗パターンと対処

### パターン1: ポート競合エラー

**症状:**
```
Error response from daemon: Ports are not available: exposing port TCP 0.0.0.0:8000 -> 0.0.0.0:0: listen tcp 0.0.0.0:8000: bind: address already in use
```

**対処:**
1. 使用中のプロセスを確認:
   ```bash
   # Windows
   netstat -an | findstr "8000"
   
   # Mac/Linux
   lsof -i :8000
   ```

2. プロセスを停止するか、`docker-compose.yml` でポート番号を変更

### パターン2: Docker Desktop未起動

**症状:**
```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

**対処:**
Docker Desktopを起動してから再実行

### パターン3: データが保存されない

**症状:**
クローラー実行後、`SELECT COUNT(*)` が 0 を返す

**対処:**
1. ログを確認:
   ```bash
   task logs
   ```

2. エラーメッセージを確認し、[トラブルシューティングガイド](troubleshooting.md) を参照

---

## 次のステップ

クイックスタートが完了したら、以下のドキュメントで理解を深めましょう：

### システムの理解
- **[README.md](../README.md)**: システム全体の概要とアーキテクチャ
- **[クローラー仕様書](crawler_spec.md)**: Fire-and-Forgetパターン、エラーハンドリング
- **[データベース定義書](database_schema.md)**: 17モデルの構造、Dual Storageパターン

### 開発を始める
- **[開発者ガイド](development_guide.md)**: 環境構築、デバッグ方法、新規パーサー追加
- **[API構造](api_structure.md)**: APIエンドポイント構造、ルーティング

### トラブル対応
- **[トラブルシューティング](troubleshooting.md)**: よくある問題と解決方法

---

## サポート

質問や問題が発生した場合は、[トラブルシューティングガイド](troubleshooting.md) を参照するか、GitHubのIssueで報告してください。

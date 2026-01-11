# トラブルシューティングガイド

本ドキュメントでは、Realestate Crawlerの使用中に発生する可能性のある問題と、その解決方法を説明します。

## 目次

1. [環境構築時の問題](#環境構築時の問題)
2. [クローラー実行時の問題](#クローラー実行時の問題)
3. [データベース関連の問題](#データベース関連の問題)
4. [テスト関連の問題](#テスト関連の問題)
5. [よくある質問 (FAQ)](#よくある質問-faq)

---

## 環境構築時の問題

### コンテナが起動しない

**症状:**
```
task init` 実行後、コンテナが起動しない、または `docker compose ps` で `Exit` 状態になっている
```

**原因と対処:**

#### 1. ポート競合

**確認方法（Windows）:**
```bash
netstat -an | findstr "8000"
netstat -an | findstr "3306"
```

**確認方法（Mac/Linux）:**
```bash
lsof -i :8000
lsof -i :3306
```

**対処:**
- 使用中のプロセスを停止する
- または `docker-compose.yml` でポート番号を変更:
  ```yaml
  services:
    app:
      ports:
        - "8001:8000"  # 8000 → 8001に変更
    mysql:
      ports:
        - "3307:3306"  # 3306 → 3307に変更
  ```

#### 2. Docker Desktop未起動

**確認方法:**
- Windows: タスクトレイにDockerアイコンがあるか確認
- Mac: メニューバーにDockerアイコンがあるか確認

**対処:**
Docker Desktopを起動してから `task init` を再実行

#### 3. Dockerイメージビルド失敗

**症状:**
```
ERROR [internal] load metadata for docker.io/library/python:3.10-slim
```

**対処:**
1. インターネット接続を確認
2. Dockerのプロキシ設定を確認（企業ネットワーク内の場合）
3. Docker Desktopを再起動

---

## クローラー実行時の問題

### データが保存されない

**症状:**
`task crawl` 実行後、データベースにレコードが追加されない

**診断フロー:**

#### ステップ1: ログを確認

```bash
task logs
```

#### ステップ2: エラーメッセージを特定

##### A. `ReadPropertyNameException` が出力されている場合

**原因:** サイトのHTML構造が変更された

**対処:**
1. 該当するパーサーファイルを特定
   - 例: `src/crawler/package/parser/mitsuiParser.py`
2. HTML構造を確認
3. セレクターを修正
4. テストを実行して動作確認:
   ```bash
   docker compose exec -T app pytest src/crawler/tests/unit/test_mitsui_parser.py -v
   ```

##### B. `ClientConnectorError` が出力されている場合

**原因:** 一時的なネットワーク障害、またはサイトがダウンしている

**対処:**
- 自動リトライ（10秒後）が実行されるため、通常は待機
- 継続的にエラーが発生する場合は、対象サイトのステータスを確認

##### C. `OperationalError` (DB接続エラー) が出力されている場合

**原因:** データベース接続の問題

**対処:** [データベース関連の問題](#データベース関連の問題) を参照

##### D. `TimeoutError` が出力されている場合

**原因:** サイトの応答が遅い（Fire-and-Forgetパターンでは正常）

**対処:**
- Fire-and-Forgetパターンでは、タイムアウトは成功とみなされる
- ログに `TimeoutError` が出力されていても、処理は継続される
- データが保存されているか確認:
  ```bash
  docker compose exec mysql mysql -u root -proot realestate_crawler -e "SELECT COUNT(*) FROM crawler_mitsumansion;"
  ```

### クローラーが途中で停止する

**症状:**
クローラー実行中に処理が停止し、新しいログが出力されなくなる

**原因と対処:**

#### 1. メモリ不足

**確認方法:**
```bash
docker stats
```

**対処:**
Docker Desktopのメモリ割り当てを増やす（Settings → Resources → Memory）

#### 2. 並列処理数が多すぎる

**対処:**
`src/crawler/package/api/api.py` の並列処理設定を調整:
```python
DEFAULT_PARARELL_LIMIT = 1  # 2 → 1に変更
DETAIL_PARARELL_LIMIT = 3   # 6 → 3に変更
```

---

## データベース関連の問題

### MySQLコンテナに接続できない

**症状:**
```
OperationalError: (2003, "Can't connect to MySQL server on 'mysql' (111)")
```

**診断フロー:**

#### ステップ1: コンテナの状態を確認

```bash
docker compose ps
```

**期待される出力:**
```
NAME                            STATUS
realestate_crawler-app-1        Up
realestate_crawler-mysql-1      Up
```

#### ステップ2: MySQLコンテナが起動していない場合

**対処:**
```bash
task default
```

#### ステップ3: MySQLコンテナが起動しているのに接続できない場合

**原因:** MySQLの初期化が完了していない

**対処:**
```bash
# MySQLのログを確認
docker compose logs mysql

# "ready for connections" が表示されるまで待機（通常30秒程度）
```

### テーブルが存在しない

**症状:**
```
OperationalError: (1146, "Table 'realestate_crawler.crawler_mitsumansion' doesn't exist")
```

**対処:**

#### 方法1: マイグレーションを再実行

```bash
docker compose exec app python src/crawler/manage.py migrate
```

#### 方法2: データベースを初期化

```bash
task stop
task init
```

### 接続数上限エラー

**症状:**
```
OperationalError: (1040, 'Too many connections')
```

**対処:**

#### 方法1: コンテナを再起動

```bash
task stop
task default
```

#### 方法2: MySQL設定を変更

`docker-compose.yml` に以下を追加:
```yaml
services:
  mysql:
    command: --max_connections=200
```

---

## テスト関連の問題

### テストが失敗する

**症状:**
```bash
task test
# FAILED src/crawler/tests/unit/test_mitsui_parser.py::TestMitsuiParser::test_parse_mansion_detail
```

**診断フロー:**

#### ステップ1: 特定のテストのみ実行

```bash
docker compose exec -T app pytest src/crawler/tests/unit/test_mitsui_parser.py::TestMitsuiParser::test_parse_mansion_detail -v
```

#### ステップ2: 詳細なログを確認

```bash
docker compose exec -T app pytest src/crawler/tests/unit/test_mitsui_parser.py -v -s --log-cli-level=DEBUG
```

#### ステップ3: テストデータを確認

**原因:** テストで使用するHTMLスナップショットが古い

**対処:**
1. 最新のHTMLを取得してスナップショットを更新
2. パーサーロジックを修正
3. テストを再実行

### テストが遅い

**症状:**
テスト実行に時間がかかる（5分以上）

**対処:**

#### 方法1: 特定のテストのみ実行

```bash
# 特定のパーサーのみ
docker compose exec -T app pytest src/crawler/tests/unit/test_mitsui_parser.py -v

# 特定のテストメソッドのみ
docker compose exec -T app pytest src/crawler/tests/unit/test_mitsui_parser.py::TestMitsuiParser::test_parse_mansion_detail -v
```

#### 方法2: 並列実行

```bash
docker compose exec -T app pytest src/crawler/tests/unit/ -n auto
```

---

## よくある質問 (FAQ)

### Q1: クローラーは何回でも実行できますか？

**A:** はい、何回でも実行可能です。ただし、同じ物件が重複して保存される可能性があります。`pageUrl` フィールドにインデックスが付与されているため、同一URLの物件は識別可能です。

### Q2: クローラー実行中にPCをスリープさせても大丈夫ですか？

**A:** 推奨しません。Fire-and-Forgetパターンでは、各APIが次のステップを起動するため、PCがスリープすると処理が中断されます。

### Q3: 特定の会社のみクローラーを実行したい

**A:** `task crawl` コマンドで会社と物件種別を指定できます:
```bash
task crawl COMPANY=mitsui TYPE=mansion
```

### Q4: データベースの中身を確認したい

**A:** MySQLコンテナに接続して確認できます:
```bash
docker compose exec mysql mysql -u root -proot realestate_crawler

# テーブル一覧
SHOW TABLES;

# レコード数確認
SELECT COUNT(*) FROM crawler_mitsumansion;

# 最新のレコードを確認
SELECT * FROM crawler_mitsumansion ORDER BY inputDateTime DESC LIMIT 5;
```

### Q5: エラーログはどこに保存されますか？

**A:** エラーログはコンテナ内に保存されます。`task logs` コマンドで確認できます。永続化したい場合は、`docker-compose.yml` でボリュームマウントを設定してください。

### Q6: クローラーの実行頻度はどのくらいが適切ですか？

**A:** サイトへの負荷を考慮し、1日1回程度を推奨します。頻繁に実行すると、IPアドレスがブロックされる可能性があります。

### Q7: 新しい会社のパーサーを追加したい

**A:** [開発者ガイド](development_guide.md) の「新しい会社のパーサーを追加」セクションを参照してください。

---

## サポート

上記の対処法で解決しない場合は、以下の情報を添えてIssueを作成してください：

1. エラーメッセージ全文
2. `docker compose ps` の出力
3. `task logs` の出力（最新100行程度）
4. 実行したコマンド
5. 環境情報（OS、Dockerバージョン等）

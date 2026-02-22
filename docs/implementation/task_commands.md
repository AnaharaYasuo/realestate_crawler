# Taskコマンド完全リファレンス

本ドキュメントでは、`Taskfile.yml` に定義されている全てのコマンドの詳細な説明、内部動作、使用例を提供します。

## 目次

1. [コマンド一覧](#コマンド一覧)
2. [詳細リファレンス](#詳細リファレンス)
3. [コマンドの組み合わせパターン](#コマンドの組み合わせパターン)
4. [トラブルシューティング](#トラブルシューティング)

---

## コマンド一覧

| コマンド | 説明 | 頻度 | 重要度 |
|---------|------|------|--------|
| `task init` | 初期セットアップ | 初回のみ | ⭐⭐⭐ |
| `task default` | サーバー起動 | 毎回 | ⭐⭐⭐ |
| `task stop` | サーバー停止 | 毎回 | ⭐⭐⭐ |
| `task crawl` | クローラー実行 | 必要時 | ⭐⭐⭐ |
| `task logs` | ログ表示 | デバッグ時 | ⭐⭐ |
| `task test` | テスト実行 | 開発時 | ⭐⭐ |

---

## 詳細リファレンス

### task init

**説明:**  
初回セットアップまたは環境の完全リセットを行います。

**内部動作:**
```yaml
cmds:
  - docker compose up -d --build
  - docker compose exec app python src/crawler/db_setup.py
```

**実行内容:**
1. Dockerイメージのビルド（`--build` フラグ）
2. コンテナの起動（`-d` でデタッチモード）
3. データベースマイグレーションの実行

**使用例:**
```bash
# 初回セットアップ
task init

# 環境をクリーンな状態にリセット
task stop
task init
```

**実行時間:** 約2-3分（初回ビルド時）

**注意事項:**
- 既存のデータベースデータは保持されます
- イメージを再ビルドするため、時間がかかります
- ネットワーク接続が必要です

---

### task default

**説明:**  
アプリケーションサーバーとデータベースを起動します。

**内部動作:**
```yaml
cmds:
  - docker compose up -d
```

**実行内容:**
1. 既存のDockerイメージを使用してコンテナを起動
2. バックグラウンドで実行（`-d` フラグ）

**使用例:**
```bash
# 通常の起動
task default

# 起動後にログを確認
task default && task logs
```

**実行時間:** 約5-10秒

**注意事項:**
- イメージが存在しない場合は、先に `task init` を実行してください
- ポート8000と3306が使用可能である必要があります

---

### task stop

**説明:**  
実行中のコンテナを停止し、削除します。

**内部動作:**
```yaml
cmds:
  - docker compose down
```

**実行内容:**
1. 実行中のコンテナを停止
2. コンテナを削除
3. ネットワークを削除

**使用例:**
```bash
# 通常の停止
task stop

# 停止後に再起動
task stop && task default
```

**実行時間:** 約2-3秒

**注意事項:**
- データベースのデータは保持されます（ボリュームは削除されません）
- 実行中のクローラー処理は中断されます

---

### task crawl

**説明:**  
指定した会社と物件種別のクローラーを実行します。

**内部動作:**
```yaml
cmds:
  - curl -X POST http://localhost:8000/{{.COMPANY}}/{{.TYPE}}/start
```

**パラメータ:**
- `COMPANY`: 対象会社（`mitsui`, `sumifu`, `tokyu`, `misawa`, `nomura`）
- `TYPE`: 物件種別（`mansion`, `kodate`, `tochi`, `investment`）

**使用例:**
```bash
# 三井のリハウス - マンション
task crawl COMPANY=mitsui TYPE=mansion

# 住友不動産販売 - 投資用
task crawl COMPANY=sumifu TYPE=investment

# 東急リバブル - 戸建て
task crawl COMPANY=tokyu TYPE=kodate

# ミサワホーム不動産 - 土地
task crawl COMPANY=misawa TYPE=tochi

# 野村の仲介+ - マンション
task crawl COMPANY=nomura TYPE=mansion
```

**実行時間:** 即座（Fire-and-Forgetパターン）

**注意事項:**
- コマンド実行後、即座にHTTP 200が返却されます
- 実際の処理は非同期で実行されます
- ログで進捗を確認してください（`task logs`）

---

### task logs

**説明:**  
アプリケーションコンテナのログをリアルタイムで表示します。

**内部動作:**
```yaml
cmds:
  - docker compose logs -f app
```

**実行内容:**
1. `app` コンテナのログを表示
2. リアルタイムで新しいログを追跡（`-f` フラグ）

**使用例:**
```bash
# ログをリアルタイムで表示
task logs

# 最新100行のみ表示
docker compose logs --tail=100 app

# 特定の時刻以降のログを表示
docker compose logs --since="2024-01-01T00:00:00" app
```

**終了方法:** `Ctrl+C`

**注意事項:**
- ログは大量に出力される可能性があります
- 必要に応じて `--tail` オプションで行数を制限してください

---

### task test

**説明:**  
全ての単体テストを実行します。

**内部動作:**
```yaml
cmds:
  - docker compose exec -T app pytest src/crawler/tests/unit/ -v
```

**実行内容:**
1. `app` コンテナ内で pytest を実行
2. `src/crawler/tests/unit/` 配下の全テストを実行
3. 詳細モード（`-v` フラグ）で結果を表示

**使用例:**
```bash
# 全テストを実行
task test

# 特定のパーサーのみテスト
docker compose exec -T app pytest src/crawler/tests/unit/test_mitsui_parser.py -v

# 特定のテストメソッドのみ実行
docker compose exec -T app pytest src/crawler/tests/unit/test_mitsui_parser.py::TestMitsuiParser::test_parse_mansion_detail -v

# 詳細なログ付きで実行
docker compose exec -T app pytest src/crawler/tests/unit/ -v -s

# カバレッジレポート付きで実行
docker compose exec -T app pytest src/crawler/tests/unit/ --cov=src/crawler/package --cov-report=html
```

**実行時間:** 約30秒-2分

**注意事項:**
- テスト実行前にコンテナが起動している必要があります
- テスト失敗時は、詳細なエラーメッセージが表示されます

---

## コマンドの組み合わせパターン

### パターン1: 初回セットアップから実行まで

```bash
# 1. 初期セットアップ
task init

# 2. クローラー実行
task crawl COMPANY=mitsui TYPE=mansion

# 3. ログ確認
task logs

# 4. 停止
task stop
```

### パターン2: 日常的な使用

```bash
# 1. 起動
task default

# 2. クローラー実行
task crawl COMPANY=sumifu TYPE=investment

# 3. データ確認
docker compose exec mysql mysql -u root -proot realestate_crawler -e "SELECT COUNT(*) FROM crawler_sumifuinvestment;"

# 4. 停止
task stop
```

### パターン3: 開発・デバッグ

```bash
# 1. 起動
task default

# 2. テスト実行
task test

# 3. コード修正

# 4. 特定のテストのみ再実行
docker compose exec -T app pytest src/crawler/tests/unit/test_mitsui_parser.py -v

# 5. クローラーで動作確認
task crawl COMPANY=mitsui TYPE=mansion

# 6. ログ確認
task logs

# 7. 停止
task stop
```

### パターン4: 複数会社のクローラーを連続実行

```bash
# 起動
task default

# 三井のリハウス - 全種別
task crawl COMPANY=mitsui TYPE=mansion
task crawl COMPANY=mitsui TYPE=kodate
task crawl COMPANY=mitsui TYPE=tochi
task crawl COMPANY=mitsui TYPE=investment

# 住友不動産販売 - 全種別
task crawl COMPANY=sumifu TYPE=mansion
task crawl COMPANY=sumifu TYPE=kodate
task crawl COMPANY=sumifu TYPE=tochi
task crawl COMPANY=sumifu TYPE=investment

# ログ監視
task logs

# 停止
task stop
```

### パターン5: 環境のクリーンリセット

```bash
# 1. 停止
task stop

# 2. ボリュームも含めて完全削除
docker compose down -v

# 3. 再初期化
task init

# 4. テスト実行
task test
```

---

## トラブルシューティング

### コマンドが見つからない

**症状:**
```
task: command not found
```

**対処:**
Taskがインストールされていません。[インストールガイド](https://taskfile.dev/installation/) を参照してください。

### Taskfile.ymlが見つからない

**症状:**
```
task: Taskfile.yml not found
```

**対処:**
プロジェクトのルートディレクトリで実行してください

# 開発者ガイド (Development Guide)

本プロジェクトのセットアップ、日常のデバッグ、および新機能（新しい会社の追加など）の実装手順について説明します。

## 1. 環境構築 (Setup)

### 必須ツール
- Docker / Docker Compose
- Task (Taskfile)

### 初期化
```bash
task init
```
このコマンドは以下を実行します：
1. `docker compose build`: イメージの作成
2. `docker compose up -d`: コンテナの起動
3. DBマイグレーションの実行

---

## 2. クローラーの実行 (Execution)

### 個別実行
```bash
task crawl COMPANY={company} TYPE={type}
```
主要なサイトのエンドポイントは `src/crawler/main.py` に定義されています。

### ログの監視
リアルタイムでクローリングの進捗やエラーを確認する場合：
```bash
task logs
```

---

## 3. 開発・拡張手順 (Extension Guide)

本プロジェクトの開発は **「GitHub Issue起票 ➔ 仕様ドキュメント先行定義 (SDD) ➔ テスト作成 (TDD) ➔ 実装」** の原則に従います。
新規機能追加や不具合修正時は、まず GitHub Issues にてユーザーストーリーおよび受入基準（アクセプタンスクライテリア）を定義・合意してから着手してください。

### 新しいサイト (Company) を追加するフロー
1. **GitHub Issue起票**: ユーザーストーリー・受入基準を記載したIssueを作成・合意。
2. **仕様ドキュメント更新**: `docs/requirements/` および `docs/internal_design/`（DBスキーマ等）を更新。
3. **テストコード作成 (TDD)**: 受入基準を満たす単体テスト・パース検証テストを作成。
4. **モデルの作成**: `src/crawler/package/models/{company}.py` を作成。
5. **マイグレーション**: 
   ```bash
   docker compose exec app python src/crawler/manage.py makemigrations
   docker compose exec app python src/crawler/manage.py migrate
   ```
6. **パーサーの実装**: `src/crawler/package/parser/{company}Parser.py` を作成し、種別Baseパーサーを継承。
7. **APIクラスの実装**: `src/crawler/package/api/{company}.py` を作成。
8. **ルート登録**: `src/crawler/main.py` にAPIエンドポイントを追加。
9. **テスト＆検証**: `task test` および二段階検証で受入基準の充足を確認。

---

## 4. トラブルシューティング (Troubleshooting)

### DB接続エラー (`OperationalError`)
- **原因**: MySQLコンテナが起動していない、または同時接続数が上限に達している。
- **対策**: `task restart` を試すか、`src/crawler/package/api/api.py` の `sleep(30)` によるリトライログを確認。

### パースエラー (`ReadPropertyNameException`)
- **原因**: ターゲットサイトのHTML構造が変化した。
- **対策**: `task logs` で失敗したURLを確認し、`BeautifulSoup` のセレクター (`select_one`) を修正。

### コンテナが起動しない
- **原因**: `8000` ポートや `3306` ポートがホスト側で既に使用されている。
- **対策**: ホスト側のポート競合を解消するか、`docker-compose.yml` のポートマッピングを変更。

---

## 5. テスト手法 (Testing)

### 全体テスト
```bash
task test
```

### 特定のパーサーの単体テスト
`src/crawler/tests/` 配下の各テストファイルを個別に実行することで、特定のサイトのパースロジックのみを抽出してデバッグ可能です。

---

## 6. 関連ドキュメント

- [クイックスタートガイド](quick_start.md): 初めての方向けの詳細なセットアップガイド
- [Taskコマンドリファレンス](task_commands.md): 全Taskコマンドの詳細解説

---
**作成日**: 2026年1月17日  
**バージョン**: 1.0 (内部設計書として分離)

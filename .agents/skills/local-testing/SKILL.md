---
name: local-testing
description: スクリプトの実行やクローラーの稼働、ローカルテストの実行を安全かつ適切に行うためのスキルです。PythonコマンドのDockerコンテナ内実行や、Gitコミット前の必須テスト、デバッグ作業時のトラブルシューティングプロセス（Tempフォルダの利用を含む）などを強制したい場合に使用します。
---

# Local Testing and Docker Execution

ローカル環境での開発、テスト、およびGitによるバージョン管理における標準実行プロトコルです。

## 上位ポリシー
- [環境制御およびヘッドレス運用ポリシー](../../policies/environment_control_policy.md)
- [品質保証・テスト・検証ポリシー](../../policies/quality_and_testing_policy.md)

## 下位ランブック
- [Docker デーモン制御手順](../../../docs/runbooks/docker_daemon_management.md)

---

## 実行プロトコル

### 1. Docker 環境準備とコンテナ内実行
- Python を動かすコード（スクリプト実行・クローラー実行など）を実施する場合は、必ず Docker を起動し、そのコンテナ内で実行すること。
- Docker が停止している場合は、GUI（`Docker Desktop.exe`）を起動せず、ヘッドレスにデーモンを立ち上げること（[docker_daemon_management.md](../../../docs/runbooks/docker_daemon_management.md) 参照）。
- 実行例: `docker-compose exec -T app python ...`

### 2. ローカルテストと GitHub プッシュ制約
- コードを修正したら **必ずローカルでテストを実行し、全て成功** することを確認する。
- テストや実行結果が全て成功するまで、絶対に GitHub にプッシュしないこと。

### 3. フィーチャーブランチのマージ後処理
- Git での変更が GitHub にマージされたら、その作業用ワークツリー・ブランチはクリーンアップ（`git worktree remove`）すること。
- メインリポジトリの `master` を最新化し、ローカルの変更を最新に保つこと。

### 4. トラブルシューティングとログ収集
- 問題解決時には「仮説構築 → 裏付けの確認 → 原因対処」を徹底すること。
- デバッグや検証用に一時的に使用する作業用のコード（スクリプト等）を作成する場合は、必ず `Temp` フォルダに出力すること。

### 5. DB 操作の安全性
- データベースのテーブル削除や全データの削除といったクリティカルな操作を伴う場合は、必ず事前に確認を実施すること。

# CodeGraph 運用組み込み 基本設計書

## 1. 全体アーキテクチャ概要
本設計では、CodeGraph（SQLite ベースの AST / 呼出関係ナレッジグラフ）を開発日常ワークフローの3層（Gitライフサイクル層、タスク自動化層、AIエージェント行動規範層）に結合する。

```
+-------------------------------------------------------------------+
|                        開発者 / AI エージェント                    |
+-------------------------------------------------------------------+
       |                                   |
       | git pull / checkout               | コード調査 / Blast Radius 測定
       v                                   v
+-----------------------+          +--------------------------------+
| Git Hooks             |          | MCP Tools / CLI                |
| - .githooks/post-merge|          | - codegraph_explore (MCP)      |
| - .githooks/post-check|          | - codegraph callers / impact   |
+-----------------------+          +--------------------------------+
       |                                   |
       | 非同期 / フェイルセーフ実行       | ワンショット AST 照会
       +-----------------+-----------------+
                         v
          +-----------------------------+
          | CodeGraph Index (.codegraph)|
          | - codegraph.db (SQLite WAL) |
          +-----------------------------+
```

## 2. コンポーネント設計

### 2.1 Git フック機構 (`.githooks/`)
- **`post-merge`**: リモートからの `git pull` やブランチのマージ完了直後に発火。変更されたソースコードのインデックスを即座に増分同期。
- **`post-checkout`**: ブランチ切り替え完了直後に発火。ブランチ間の差分ファイルを検知してインデックスを同期。
- **実行防御ポリシー**:
  - `codegraph` コマンドが存在しない環境では警告のみ出力して exit 0 で終了。
  - バックグラウンド実行または高速実行により、Git 操作のレスポンスを犠牲にしない。

### 2.2 Taskfile 機構 (`Taskfile.yml`)
- `codegraph:sync`: `codegraph sync` を呼び出す標準タスクを提供。
- `codegraph:status`: インデックスの健全性・ノード数・言語別ファイル統計を出力。

### 2.3 AI エージェント規範 (`.agents/AGENTS.md`)
- **CodeGraph ファースト調査原則**:
  - クラス・関数・API・バグの調査において、広範囲 grep や全文 Read を先行させず、必ず `codegraph_explore` を呼ぶことを明文化。
- **Pre-Flight 同期義務への追加**:
  - `git checkout master && git pull origin master` の実行後、インデックスを最新化する手順を明記。
- **Worktree 運用との調和**:
  - Worktree 環境で `codegraph` を実行する際の親インデックス参照ルールを規定。

# CodeGraph 運用組み込み 内部設計書

## 1. Git フックスクリプト仕様

### 1.1 `.githooks/post-merge`
- **種別**: Shell script (`#!/bin/sh`)
- **目的**: `git pull` や `git merge` 完了後にインデックスを更新。
- **処理ロジック**:
  1. `codegraph` CLI の存在確認（`command -v codegraph` または `cmd.exe /c where codegraph`）。
  2. Windows 環境では PowerShell 実行ポリシー回避のため `cmd.exe /c codegraph sync` を優先実行。
  3. バックグラウンドまたは有限時間での実行とし、失敗時も exit 0 を返す。

### 1.2 `.githooks/post-checkout`
- **引数**:
  - `$1`: 直前の HEAD のコミットハッシュ
  - `$2`: 新しい HEAD のコミットハッシュ
  - `$3`: フラグ（`1` = ブランチ切り替え, `0` = ファイルチェックアウト）
- **処理ロジック**:
  - `$3` が `1`（ブランチ切り替え）の場合のみ `codegraph sync` を発火。
  - 同様に exit 0 を保証。

## 2. Taskfile タスク定義

```yaml
  codegraph:sync:
    desc: Synchronize CodeGraph index with latest codebase changes
    cmds:
      - cmd /c codegraph sync || codegraph sync || true

  codegraph:status:
    desc: Display current CodeGraph index status and statistics
    cmds:
      - cmd /c codegraph status || codegraph status || true
```

## 3. 開発ルール統合（`.agents/AGENTS.md`）
- `AGENTS.md` の「作業着手前の最新 master 同期義務原則 (Pre-Flight Master Sync)」に `codegraph sync` を追記。
- 「【プロジェクト普遍ルール】常時 git worktree 運用原則」に CodeGraph インデックス同期および `codegraph_explore` 呼び出し時の `projectPath` 取扱いを追記。
- 「【プロジェクト普遍ルール】CodeGraph ファースト調査・影響範囲分析原則」セクションを新設。

## 4. 自動テスト仕様 (`src/crawler/tests/unit/test_codegraph_hooks.py`)
- フックスクリプト（`post-merge`, `post-checkout`）の存在および実行可能パーミッションを検証。
- フックスクリプト内に `codegraph sync` 呼び出しおよび安全な終了処理が含まれることをアサート。
- `Taskfile.yml` に `codegraph:sync` タスクが正しく定義されていることを検証。

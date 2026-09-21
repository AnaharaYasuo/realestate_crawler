---
name: git-push-workflow
description: 開発作業が完了した後に、新しいブランチを作成し、変更をコミットしてリモートリポジトリにプッシュする一連のGit操作を行うためのスキル（ワークフロー）です。作業の区切りやコードの共有・バックアップを行う際に使用します。
---

# Git Push Workflow

コードの変更や機能追加が完了した際に、安全に変更をリモートリポジトリへ反映させるための標準的なGitワークフローです。

## 手順

1. **変更状況の確認**
   - `git status` コマンドを実行し、変更されたファイル、新規追加されたファイル、未追跡のファイルを確認する。
   - 変更内容を `git diff` で確認し、意図しない変更（一時ファイルや認証情報など）が含まれていないかチェックする。

2. **作業ブランチの作成と切り替え**
   - 現在の作業内容を適切に表す名前で新しいブランチを作成し、切り替える。
   - `git checkout -b <branch-name>`
   - 命名規則の例: `feature/add-new-parser`, `fix/login-bug`, `docs/update-readme`, `refactor/models`

3. **変更のステージング**
   - 必要なファイルをステージングエリアに追加する。
   - 特定のファイルのみ追加する場合: `git add <file1> <file2>`
   - 全ての変更を追加する場合: `git add .` （※不要なファイルが含まれていないか事前に確認済みであること）

4. **コミットの作成**
   - どのような変更を行ったか、簡潔かつ分かりやすいコミットメッセージをつけてコミットする。
   - `git commit -m "<変更内容を説明するメッセージ>"`

5. **リモートリポジトリへのプッシュ**
   - 作成したブランチをリモートリポジトリにプッシュする。
   - `git push origin <branch-name>`

6. **二段階PRマージの実施（Production Gate 遵守）**
   - 本リポジトリでは `production` への直接 push および作業ブランチからの直接 PR は GitHub Actions (`production-gate.yml`) でブロックされる。
   - **Step 1: 作業ブランチ ➔ `master` への PR & マージ**
     - `gh pr create --base master --head <branch-name> --title "[#<issue_num>] ..." --body "Closes #<issue_num>\n..."`
     - CI チェック通過後、`master` にマージ (`gh pr merge <PR_NUMBER> --squash --delete-branch`)。
   - **Step 2: `master` ➔ `production` への リリース PR & マージ**
     - ローカルの `master` を最新化: `git checkout master && git pull origin master`
     - `gh pr create --base production --head master --title "release: ..." --body "..."`
     - CI チェック確認後、`production` にマージ (`gh pr merge <PR_NUMBER> --merge`)。

7. **GitHub Issue のステータス完了確認 ＆ 閉じ漏れ是正**
   - マージ後または作業完了後、`gh issue list --state open` を実行して該当 Issue が正常にクローズ（Closed）されたか確認する。
   - 自動クローズされずにオープン状態のまま残存している場合（閉じ漏れ）は、完了理由を添えて直ちに `gh issue close <issue_num> --comment "..."` を実行してステータスを完了状態へ進めること。



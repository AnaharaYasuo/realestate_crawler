# Common Rules Index

開発・運用に関する共通ルールは、AIエージェントが自律的に実行可能な「スキル（ワークフロー）」として定義・移行されました。
各ルールの詳細は以下のスキル定義ファイルを参照してください。

## ワークフロースキル一覧

1. **ドキュメント更新管理スキル** (`/document-updater`)
   - ドキュメントやDBスキーマの更新義務、日本語出力の指定などに関するルール
   - 参照先: `.agents/skills/document-updater/SKILL.md`

2. **パーサー実装プロセス・品質保証スキル** (`/parser-implementation`)
   - パーサーの実装（ラベル起点抽出等）、検証プロセスに関するルール
   - 参照先: `.agents/skills/parser-implementation/SKILL.md`

3. **フィールド名統一・モデル設計スキル** (`/field-name-unifier`)
   - サイト間での同一情報のフィールド名統一（`field_naming_standards.md`の遵守）に関するルール
   - 参照先: `.agents/skills/field-name-unifier/SKILL.md`

4. **ローカルテスト・Docker実行・Gitフロー管理スキル** (`/local-testing`)
   - Dockerコンテナ内実行、ローカルテスト必須化、Gitブランチ管理に関するルール
   - 参照先: `.agents/skills/local-testing/SKILL.md`

5. **トラブルシューティング＆原因究明スキル** (`/troubleshooting-and-logging`)
   - 仮説からの裏付け確認の徹底、ログ拡充、一時作業ファイル(`Temp`フォルダ)等のルール
   - ユーザーからの指摘や解決策のルール化の規定
   - 参照先: `.agents/skills/troubleshooting-and-logging/SKILL.md`

6. **Gitプッシュワークフロースキル** (`/git-push-workflow`)
   - 開発完了時のブランチ作成、変更のコミット、リモートリポジトリへのプッシュといった一連のGit操作手順
   - 参照先: `.agents/skills/git-push-workflow/SKILL.md`

7. **仕様駆動開発スキル** (`/spec-driven-development`)
   - **GitHub Issue起票 ➔ 仕様定義 ➔ テスト ➔ コード実装** のトップダウン開発プロセス
   - 今後修正・追加する内容はすべて Issue 単位で GitHub Issues に起票し、ユーザーストーリーおよび受入基準（アクセプタンスクライテリア）に合意の上で実装
   - 仕様マークダウンの構図（要件 ➔ 設計）の維持と、README.md インデックスとの完全同期
   - 参照先: `.agents/skills/spec-driven-development/SKILL.md` / `.agents/AGENTS.md`

8. **自律バグ修復スキル** (`/auto-healing`)
   - クローリング監視やアラートから自動的にパースエラー等を調査・修復するワークフロー
   - 参照先: `.agents/skills/auto-healing/SKILL.md`

9. **共通品質・リグレッション検証スキル** (`/regression-testing`)
   - Snyk/Sonar走査、動的アクティブ生HTML検証、単体テスト100%成功を裏付ける検証フロー
   - 参照先: `.agents/skills/regression-testing/SKILL.md`

10. **コード修正後テスト義務化 ＆ 物件公開終了アラート除外ルール**
   - コード修正後は必ずテストを実行し成功するまで修正を繰り返すプロジェクト不変ルール
   - 物件公開終了（HTTP 404/掲載終了）エラーは Slack アラート通知から除外するルール
   - 参照先: `.agents/AGENTS.md`

※ 上記スキルはエージェントが自律的にワークフローを強制するためのものです。またユーザーから明示的な指示がなくとも、関連するコンテキスト内で自動的に呼び出されます。


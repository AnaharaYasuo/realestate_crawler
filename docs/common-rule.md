# Common Rules Index

開発・運用に関する共通ルールは、AIエージェントが自律的に実行可能な「スキル（ワークフロー）」として定義・移行されました。
各ルールの詳細は以下のスキル定義ファイルを参照してください。

## ワークフロースキル一覧

1. **ドキュメント更新管理スキル** (`/document-updater`)
   - ドキュメントやDBスキーマの更新義務、日本語出力の指定などに関するルール
   - 参照先: `.agent/skills/document-updater/SKILL.md`

2. **パーサー実装プロセス・品質保証スキル** (`/parser-implementation`)
   - パーサーの実装（ラベル起点抽出等）、検証プロセスに関するルール
   - 参照先: `.agent/skills/parser-implementation/SKILL.md`

3. **フィールド名統一・モデル設計スキル** (`/field-name-unifier`)
   - サイト間での同一情報のフィールド名統一（`field_naming_standards.md`の遵守）に関するルール
   - 参照先: `.agent/skills/field-name-unifier/SKILL.md`

4. **ローカルテスト・Docker実行・Gitフロー管理スキル** (`/local-testing`)
   - Dockerコンテナ内実行、ローカルテスト必須化、Gitブランチ管理に関するルール
   - 参照先: `.agent/skills/local-testing/SKILL.md`

5. **トラブルシューティング＆原因究明スキル** (`/troubleshooting-and-logging`)
   - 仮説からの裏付け確認の徹底、ログ拡充、一時作業ファイル(`Temp`フォルダ)等のルール
   - ユーザーからの指摘や解決策のルール化の規定
   - 参照先: `.agent/skills/troubleshooting-and-logging/SKILL.md`

6. **Gitプッシュワークフロースキル** (`/git-push-workflow`)
   - 開発完了時のブランチ作成、変更のコミット、リモートリポジトリへのプッシュといった一連のGit操作手順
   - 参照先: `.agent/skills/git-push-workflow/SKILL.md`

※ 上記スキルはエージェントが自律的にワークフローを強制するためのものです。またユーザーから明示的な指示がなくとも、関連するコンテキスト内で自動的に呼び出されます。

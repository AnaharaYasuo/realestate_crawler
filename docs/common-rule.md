# Common Rules Index

開発・運用に関する共通ルールは、AIエージェントが自律的に実行可能な「スキル（`.agents/skills/*/SKILL.md`）」「階層別ルール（`AGENTS.md`）」「ライフサイクルフック（`.agents/hooks.json`）」として定義・統合されています。

## ワークフロースキル一覧

1. **仕様駆動開発・ドキュメントSSOT管理スキル** (`/spec-driven-development`)
   - **GitHub Issue起票 ➔ 7大ドメイン仕様定義(SDD) ➔ テスト(TDD) ➔ コード実装 ➔ ハーネス検証** のトップダウン開発プロセス
   - ドキュメントやDBスキーマの更新義務、同名ファイル重複禁止（SSOT）、`README.md` インデックスとの完全同期
   - 参照先: [`.agents/skills/spec-driven-development/SKILL.md`](../.agents/skills/spec-driven-development/SKILL.md) / [`.agents/AGENTS.md`](../.agents/AGENTS.md)

2. **パーサー実装プロセス・品質保証スキル** (`/parser-implementation`)
   - パーサーの実装（1項目1メソッド、ラベル起点抽出、4層物件種別防衛等）、検証プロセスに関するルール
   - 参照先: [`.agents/skills/parser-implementation/SKILL.md`](../.agents/skills/parser-implementation/SKILL.md) / [`src/crawler/package/parser/AGENTS.md`](../src/crawler/package/parser/AGENTS.md)

3. **フィールド名統一・モデル設計スキル** (`/field-name-unifier`)
   - サイト間での同一情報のフィールド名・データ型統一（4基底モデル継承、[`field_naming_standards.md`](3_data_models/field_naming_standards.md) の遵守）に関するルール
   - 参照先: [`.agents/skills/field-name-unifier/SKILL.md`](../.agents/skills/field-name-unifier/SKILL.md) / [`src/crawler/package/models/AGENTS.md`](../src/crawler/package/models/AGENTS.md)

4. **新規サイト完全自律オンボーディングスキル** (`/onboard-new-site`)
   - 不動産サイトURL/名称から `SiteRegistry` 登録、Model/Parser/API 実装、ML 価格推定・お宝判定連携、タスク分散配線までを一気通貫で自動構築・検証するスキル
   - 参照先: [`.agents/skills/onboard-new-site/SKILL.md`](../.agents/skills/onboard-new-site/SKILL.md)

5. **ローカルテスト・実行環境・Gitフロー管理スキル** (`/local-testing`)
   - ホスト/Docker実行一貫性、ローカルテスト必須化、Git Worktree管理に関するルール
   - 参照先: [`.agents/skills/local-testing/SKILL.md`](../.agents/skills/local-testing/SKILL.md)

6. **トラブルシューティング＆原因究明スキル** (`/troubleshooting-and-logging`)
   - 仮説からの裏付け確認の徹底、ログ拡充、一時作業ファイル(`Temp`フォルダ)等のルール
   - 参照先: [`.agents/skills/troubleshooting-and-logging/SKILL.md`](../.agents/skills/troubleshooting-and-logging/SKILL.md)

7. **Gitプッシュ＆二段階リリースワークフロースキル** (`/git-push-workflow`)
   - Worktreeでのコミット、`pre_pr_check.py` 事前検証、`master` ➔ `production` 二段階マージ手順
   - 参照先: [`.agents/skills/git-push-workflow/SKILL.md`](../.agents/skills/git-push-workflow/SKILL.md)

8. **自律バグ修復スキル** (`/auto-healing`)
   - クローリング監視・マルチ障害テレメトリ・フィールド充填率ドリフトから自動的にパースエラー等を調査・修復するワークフロー
   - 参照先: [`.agents/skills/auto-healing/SKILL.md`](../.agents/skills/auto-healing/SKILL.md)

9. **共通品質・リグレッション検証スキル** (`/regression-testing`)
   - Snyk/Sonar走査、動的アクティブ生HTML検証、Architectural Fitness Functions (`test_architecture_harness.py`)、単体テスト100%成功を裏付ける検証フロー
   - 参照先: [`.agents/skills/regression-testing/SKILL.md`](../.agents/skills/regression-testing/SKILL.md)

10. **エンドツーエンド全パイプライン実行スキル** (`/full-pipeline-execution`)
    - インフラ接続確認から全件クローリング、ML再学習、バルク価格推定、お宝通知、Auto-Healingまでを一貫実行するスキル
    - 参照先: [`.agents/skills/full-pipeline-execution/SKILL.md`](../.agents/skills/full-pipeline-execution/SKILL.md)

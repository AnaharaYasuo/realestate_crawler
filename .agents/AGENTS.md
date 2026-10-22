# プロジェクト憲法・行動原則 (AGENTS.md)

本ドキュメントは、プロジェクト全体の開発・運用・意思決定における最上位プリンシプル（憲法）です。すべてのエージェントおよび開発者は、いかなる作業においても本プリンシプルを最優先で遵守しなければなりません。

---

## 1. ドキュメント体系ピラミッド (Documentation Pyramid)

本プロジェクトのルール・設計・手順は、以下の4層ピラミッド構造で管理されています。下層に向かうにつれて情報の具体度が高くなります。

```
                     ▲
                    / \          【Layer 1: 最上位プリンシプル】
                   / L1\         .agents/AGENTS.md (憲法・基本哲学・行動原則)
                  /-----\
                 /  L2   \       【Layer 2: 領域別ポリシー・規範】
                /  Policy \      .agents/policies/*.md (判断基準・境界・品質要件)
               /-----------\
              /     L3      \    【Layer 3: 実行プロトコル・スキル】
             /    Skills     \   .agents/skills/*/SKILL.md (標準手順・ワークフロー)
            /-----------------\
           /        L4         \ 【Layer 4: 基底・具象手順 (ランブック/設定)】
          / Concrete Runbooks   \ docs/runbooks/*.md (具体的コマンド・設定)
         -------------------------
```

### 領域別ポリシー（Layer 2 ナビゲーション）
- [環境制御およびヘッドレス運用ポリシー](policies/environment_control_policy.md): 自律準備、完全ヘッドレス、共有インフラ保護
- [品質保証・テスト・検証ポリシー](policies/quality_and_testing_policy.md): TDD、動的生HTML検証、ミューテーションテスト、Pre-Pushゲート
- [ブランチ運用およびリリース完了ポリシー](policies/branch_and_release_policy.md): 常時Worktree、二段階マージ、Production Done定義
- [クローラーおよびパーサー設計ポリシー](policies/crawler_and_parser_policy.md): 1物件1AI、種別Base継承、Smallest-Site-First

---

## 2. コア・プリンシプル (Fundamental Principles)

### 原則 1: 環境自律準備 ＆ 完全ヘッドレス原則 (Autonomous Headless Environment)
- **自律準備の義務**: 必要なランタイム（Docker等）が停止していても、ユーザーに作業を丸投げせず自律的に起動・準備すること。
- **完全ヘッドレスの厳守**: エージェントは CLI・デーモンとしてのみ環境を制御する。ユーザーのデスクトップに GUI ウィンドウ（`Docker Desktop.exe` 等）をポップアップさせる行為は全面禁止。
- 具象ランブック: [docker_daemon_management.md](../docs/runbooks/docker_daemon_management.md)

### 原則 1.1: ローカル本番実行・インフラ接続厳守原則 (Local Production Execution & Infrastructure)
- **ローカル本番実行の定義**:
  - 本番データベース（Google Cloud SQL）へ接続した状態でクローラーやML推定等のパイプラインを実行することを指す。
  - **Docker不要（ホスト実行許可）**: .env の設定（EXECUTION_ENV=host）に従い、ホスト上のPython（PYTHON_PATH）での直接実行が明示的に許可されている。Dockerコンテナ起動に無駄に固執してはならない。
  - **本番IAPトンネル・ProxySQL起動の事前義務**: 実行前に必ず GCE インスタンス proxysql-instance-prod（zone:  asia-northeast1-a）が RUNNING であることを確認し、gcloud compute start-iap-tunnel により 127.0.0.1:6033 へのトンネルを開設してDB疎通（SELECT 1）を確認すること。
  - **DB未接続・エラー放置の絶対厳禁**: DB接続エラー（OperationalError: 2002 や接続拒否等）が発生している状態を「正常待機中」と誤認して放置・空転させてはならない。即座にプロセスを停止し、トンネルと接続を復旧した上で再実行すること。

### 原則 2: CodeGraph ファースト調査・影響範囲分析原則 (CodeGraph First)
- 広範囲 grep や推測によるファイル全体の連続 Read を禁止する。
- 必ず CodeGraph MCP ツール `codegraph_explore` をファーストコールし、ソースコード、Callers/Callees、Blast Radius（影響範囲）を 1 回で把握すること。

### 原則 3: 常時 git worktree 運用原則 (Always Worktree)
- メイン作業ツリーでの直接変更を厳禁とする。
- 必ず `.worktrees/<branch-name>` 配下の独立ワークツリーで作業・検証・コミット・プッシュを行うこと。

### 原則 4: SDD（仕様駆動開発）× TDD（テスト駆動開発）統合原則
- 開発ライフサイクルは不可逆とする：
  **GitHub Issue 起票 ➔ 仕様ドキュメント先行更新 (SDD) ➔ テストコード作成 (TDD) ➔ 最小コード実装**
- 緊急修復等で実装が先行した場合も、直ちに Issue・テスト・ドキュメントを逆引き補正すること。

### 原則 5: 能動的自律完遂 ＆ 放置禁止原則 (No Passive Waiting)
- 非同期タスクやバックグラウンド処理を発行した際、「待機中」としてユーザーにボールを返却・放置することを厳禁とする。
- `schedule` タイマーによる能動的ポーリングで進捗を追跡し、完了時はユーザーの催促を待たずに即座に次ステップへ自律前進すること。
- 不要となったバックグラウンドタスクは直ちに `manage_task(kill)` で完全クリーンアップすること。

### 原則 6: 本番マージ完了の定義原則 (Production Merge Definition of Done)
- **「プロダクション（`production` ブランチ）へのマージ完了」をもって初めてタスク完了とする。**
- `master` へのマージ完了時点で作業を終了とみなしてはならず、必ず `production` へのリリース PR 作成、CI（Production Gate）通過、および `production` へのマージ完了（本番デプロイ起動）まで一貫して遂行・監視すること。

# プロジェクト憲法・行動原則 (AGENTS.md)

本ドキュメントは、プロジェクト全体の開発・運用・意思決定における最上位プリンシプル（憲法）です。すべてのエージェントおよび開発者は、いかなる作業においても本プリンシプルを最優先で遵守しなければなりません。

---

## 1. ドキュメント体系ピラミッド ＆ 3層エンジニアリング・ハーネス

本プロジェクトのルール・設計・手順は、以下の4層ピラミッド構造と **Antigravity 3層エンジニアリング・ハーネス** により常時機械的に強制されます。

```
                     ▲
                    / \          【Layer 1: 最上位プリンシプル & 階層別AGENTS.md】
                   / L1\         .agents/AGENTS.md + 各層ディレクトリ AGENTS.md
                  /-----\
                 /  L2   \       【Layer 2: 領域別ポリシー ＆ 機械的ゲート】
                /  Policy \      .agents/policies/*.md + .agents/hooks.json + test_architecture_harness.py
               /-----------\
              /     L3      \    【Layer 3: 実行プロトコル・スキル (Progressive Disclosure)】
             /    Skills     \   .agents/skills/*/SKILL.md (+ scripts/ & examples/)
            /-----------------\
           /        L4         \ 【Layer 4: 基底・具象手順 (ランブック/7大ドメイン設計書)】
          / Concrete Runbooks   \ docs/1_architecture/〜docs/7_operations_and_improvement/, docs/runbooks/*.md
         -------------------------
```

### 領域別ポリシー（Layer 2 ナビゲーション）
- [環境制御およびヘッドレス運用ポリシー](policies/environment_control_policy.md): 自律準備、完全ヘッドレス、共有インフラ保護、ホスト/コンテナ実行一貫性
- [品質保証・テスト・検証ポリシー](policies/quality_and_testing_policy.md): TDD、動的生HTML検証、ミューテーションテスト、Architectural Fitness Functions、Pre-Pushゲート
- [ブランチ運用およびリリース完了ポリシー](policies/branch_and_release_policy.md): 常時Worktree、二段階マージ、Production Done定義
- [クローラーおよびパーサー設計ポリシー](policies/crawler_and_parser_policy.md): 1物件1AI、種別Base継承、4層種別判定防衛、Unified SiteRegistry、Smallest-Site-First

### ディレクトリ階層別ルール（Hierarchical Scoped `AGENTS.md`）
Antigravity の自動ディスカバリ機能により、各サブディレクトリ配下のファイルを操作する際は以下の階層別 `AGENTS.md` が自動適用されます：
- [`src/crawler/package/models/AGENTS.md`](../src/crawler/package/models/AGENTS.md): 4基底モデル継承・標準フィールド型統一規約
- [`src/crawler/package/parser/AGENTS.md`](../src/crawler/package/parser/AGENTS.md): 1項目1メソッド・抽象強制・4層物件種別防衛・禁止構文規約
- [`src/crawler/package/ml/AGENTS.md`](../src/crawler/package/ml/AGENTS.md): `GroupKFold` リーク防止・サンプル重み一貫適用・下限予測値 $P_{10}$ お宝判定規約
- [`docs/AGENTS.md`](../docs/AGENTS.md): ドキュメント SSOT・重複ファイル名禁止・リンク整合性規約

---

## 2. コア・プリンシプル (Fundamental Principles)

### 原則 1: 環境自律準備 ＆ 完全ヘッドレス原則 (Autonomous Headless Environment)
- **自律準備の義務**: 必要なランタイム（Docker等）が停止していても、ユーザーに作業を丸投げせず自律的に起動・準備すること。
- **完全ヘッドレスの厳守**: エージェントは CLI・デーモンとしてのみ環境を制御する。ユーザーのデスクトップに GUI ウィンドウ（`Docker Desktop.exe` 等）をポップアップさせる行為は全面禁止（`.agents/hooks.json` により機械的に Deny される）。
- 具象ランブック: [docker_daemon_management.md](../docs/runbooks/docker_daemon_management.md)

### 原則 1.1: ローカル本番実行・インフラ接続厳守原則 (Local Production Execution & Infrastructure)
- **ローカル本番実行の定義**:
  - 本番データベース（Google Cloud SQL）へ接続した状態でクローラーやML推定等のパイプラインを実行することを指す。
  - **Docker不要（ホスト実行許可）**: `.env` の設定（`EXECUTION_ENV=host`）に従い、ホスト上のPython（`PYTHON_PATH`）での直接実行が明示的に許可されている。Dockerコンテナ起動に無駄に固執してはならない。
  - **本番IAPトンネル・ProxySQL起動の事前義務**: 実行前に必ず GCE インスタンス `proxysql-instance-prod`（zone: `asia-northeast1-a`）が `RUNNING` であることを確認し、`gcloud compute start-iap-tunnel` により `127.0.0.1:6033` へのトンネルを開設してDB疎通（`SELECT 1`）を確認すること。
  - **DB未接続・エラー放置の絶対厳禁**: DB接続エラー（`OperationalError: 2002` や接続拒否等）が発生している状態を「正常待機中」と誤認して放置・空転させてはならない。即座にプロセスを停止し、トンネルと接続を復旧した上で再実行すること。

### 原則 2: CodeGraph ファースト調査・影響範囲分析原則 (CodeGraph First)
- 広範囲 grep や推測によるファイル全体の連続 Read を禁止する。
- 必ず CodeGraph MCP ツール `codegraph_explore` をファーストコールし、ソースコード、Callers/Callees、Blast Radius（影響範囲）を 1 回で把握すること。

### 原則 3: 常時 git worktree 運用原則 (Always Worktree)
- メイン作業ツリーでの直接変更を厳禁とする（`.agents/hooks.json` によりメインツリーでの編集・コミットは機械的にブロックされる）。
- 必ず `.worktrees/<branch-name>` 配下の独立ワークツリーで作業・検証・コミット・プッシュを行うこと。

### 原則 4: SDD（仕様駆動開発）× TDD（テスト駆動開発）× 6軸評価ハーネス統合原則
- 開発ライフサイクルは不可逆とする：
  **GitHub Issue 起票 ➔ 仕様ドキュメント先行更新 (SDD) ➔ テストコード作成 (TDD) ➔ 最小コード実装 ➔ アーキテクチャ・ハーネス検証 (`test_architecture_harness.py`)**
- すべての変更は以下の **6軸評価尺度** を満たさなければならない：
  1. **ソフトウェア品質特性 (ISO/IEC 25010)**: 機能適合性、性能効率性（`ClientSession` 再利用等）、信頼性、保守性。
  2. **設計原則・プロジェクト規約**: SOLID、DRY、1項目1メソッド、1物件1AIリクエスト。
  3. **リファレンス実装準拠**: 4基底モデル継承、種別 `*ParserBase` 抽象強制、標準コンバータ利用。
  4. **ドキュメント SSOT**: `docs/` 内のファイル名重複ゼロ、リンク切れゼロ、コードとの完全同期。
  5. **データエンジニアリング & MLOps**: スキーマ型統一、物件種別4層防衛（誤判定0%）、`GroupKFold` によるリーク防止、下限予測値 $P_{10}$ によるリスク調整後お宝判定。
  6. **クラウドネイティブ運用 & 完全自律性**: `SiteRegistry` による10箇所一元配線、マルチエラー保持・フィールド充填率（Fill-Rate）可観測性。

### 原則 5: 能動的自律完遂 ＆ 放置禁止原則 (No Passive Waiting)
- 非同期タスクやバックグラウンド処理を発行した際、「待機中」としてユーザーにボールを返却・放置することを厳禁とする。
- `schedule` タイマーによる能動的ポーリングで進捗を追跡し、完了時はユーザーの催促を待たずに即座に次ステップへ自律前進すること。
- 不要となったバックグラウンドタスクは直ちに `manage_task(kill)` で完全クリーンアップすること。

### 原則 6: 本番マージ完了の定義原則 (Production Merge Definition of Done)
- **「プロダクション（`production` ブランチ）へのマージ完了」をもって初めてタスク完了とする。**
- `master` へのマージ完了時点で作業を終了とみなしてはならず、必ず `production` へのリリース PR 作成、CI（Production Gate）通過、および `production` へのマージ完了（本番デプロイ起動）まで一貫して遂行・監視すること。

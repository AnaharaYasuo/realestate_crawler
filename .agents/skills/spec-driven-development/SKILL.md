---
name: spec-driven-development
description: "仕様駆動開発(SDD: Specification-Driven Development)に基づき、ユーザーの指示・要求があった際、まず要件定義/外部設計/内部設計のドキュメント階層をトップダウンで変更し、その仕様に従ってコード実装・検証を行うためのスキルです。"
---

# SDD（仕様駆動開発）× TDD（テスト駆動開発）統合開発スキル

本スキルは、課題の起票・受入基準定義から仕様・ドキュメント策定、テスト、実装に至る **「GitHub Issue起票 ➔ 仕様定義 ➔ テスト ➔ 実装 ➔ アーキテクチャ・ハーネス検証」** という一貫したトップダウンライフサイクルを強制・同期させるガイドラインです。

---

## 実行ステップ

### Step 0: GitHub Issues による課題・要求の起票 ＆ 受入基準策定 (Issue-Driven)
機能追加や不具合修正に着手する前に、**修正内容を Issue の単位で GitHub Issues に起票**します。
- 作業ブランチ名には必ず Issue 番号を含めます（例: `feat/1151-add-feature`, `fix/1152-fix-parser`）。
- 必ず `.worktrees/<branch-name>` 配下の独立ワークツリーで作業します。

### Step 1: 7大ドメイン正本ドキュメントのトップダウン更新 (SDD / SSOT)
コードを触る前に、`docs/` 配下の7大ドメイン正本ディレクトリ（Single Source of Truth）を先行更新します（※同名の `.md` ファイルを複数ディレクトリに重複作成することは厳禁）：
1. **`docs/1_architecture/`**: 全体要件定義（[`requirements_master.md`](../../../docs/1_architecture/requirements_master.md)）、基本設計（[`basic_design_master.md`](../../../docs/1_architecture/basic_design_master.md)）、詳細設計（[`detailed_design_master.md`](../../../docs/1_architecture/detailed_design_master.md)）
2. **`docs/2_crawlers/`**: クローラー標準仕様（`_standards/`）およびサイト別構造定義（`sites/`）
3. **`docs/3_data_models/`**: フィールド命名標準（[`field_naming_standards.md`](../../../docs/3_data_models/field_naming_standards.md)）、正規化・名寄せ仕様
4. **`docs/4_valuation_and_ml/`**: MLモデル仕様（[`ml_model_specifications.md`](../../../docs/4_valuation_and_ml/ml_model_specifications.md)）、土地評価、AI属性抽出仕様
5. **`docs/5_alert_and_delivery/`**: Slack通知・配信・エージェント仕様
6. **`docs/6_platform_and_release/`**: GCPインフラ、Terraform、CI/CD、Pre-PR Check仕様
7. **`docs/7_operations_and_improvement/`**: 障害テレメトリ（[`gcs_failure_telemetry_internal_design.md`](../../../docs/7_operations_and_improvement/gcs_failure_telemetry_internal_design.md)）、New Relic監視、Auto-Heal仕様

### Step 2: 受入基準（Issue）＆ ドキュメント仕様に基づくテストコード作成 (TDD)
Issue に定義された「アクセプタンスクライテリア (受入基準)」および先行更新されたドキュメントの仕様を満たしているかを客観的に検証するため、コード実装前に `pytest` のテストコードを先に記述します。

### Step 3: 受入基準 ＆ ドキュメント ＆ リファレンス実装に適合する最小コード実装
各ディレクトリの `AGENTS.md`（`models/AGENTS.md`, `parser/AGENTS.md`, `ml/AGENTS.md`）に規定されたリファレンス実装・不変条件に従い、テストが通過する最小限のコードを実装します。

### Step 4: アーキテクチャ・ハーネス検証 ＆ README.md 完全同期
1. `pytest src/crawler/tests/unit/test_architecture_harness.py` を実行し、6軸評価尺度に基づく4大ゲート（Doc SSOT Gate / Model & Parser Reference Gate / SiteRegistry Completeness Gate / PropertyType & ML Invariant Gate）がすべて PASS することを確認します。
2. `docs/` 配下に新規作成・変更・移動があった場合、[README.md](../../../README.md) の目次リンクと解説文を同期更新します。
3. GitHub Issue に記載されたアクセプタンスクライテリアのチェックボックスがすべて `[x]` に更新されていることを確認します。

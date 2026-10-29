# ドキュメント階層ルール (docs/AGENTS.md)

本ディレクトリ（`docs/`）配下のファイルを追加・編集・移動する際は、以下の SSOT（Single Source of Truth）不変条件を厳守すること。

## 1. ドメイン別正本ディレクトリ構造（SSOT原則）
中核ドキュメントは以下の7大ドメインディレクトリに配置・更新すること：
- `docs/1_architecture/`: 全体要件定義（`requirements_master.md`）、基本設計（`basic_design_master.md`）、詳細設計（`detailed_design_master.md`）、ドキュメント規約
- `docs/2_crawlers/`: クローラー標準規約（`_standards/`）およびサイト別構造仕様（`sites/`）
- `docs/3_data_models/`: フィールド命名標準（`field_naming_standards.md`）、データ正規化、重複名寄せ規約
- `docs/4_valuation_and_ml/`: MLモデル仕様（`ml_model_specifications.md`）、土地評価、1物件1AI抽出仕様、予測精度診断ポリシー
- `docs/5_alert_and_delivery/`: Slack通知・配信・常駐エージェント仕様
- `docs/6_platform_and_release/`: GCPインフラ、Terraform仕様、CI/CD、Pre-PR Check仕様
- `docs/7_operations_and_improvement/`: 障害テレメトリ（`gcs_failure_telemetry_internal_design.md`）、New Relic監視、Auto-Heal仕様、運用マニュアル

## 2. 絶対禁止事項（Automated Fitness Gate 検証対象）
1. **同名マークダウンファイルの重複作成禁止**: `docs/` 配下のいかなるサブディレクトリ間であっても、同一ファイル名（basename）の `.md` ファイルを重複存在させてはならない（Split-Brain 防止）。
2. **廃止ディレクトリの再作成禁止**: 削除済みの `docs/operation/` 等を再作成してはならない。
3. **リンク切れの禁止**: ドキュメントの追加・リネーム時は必ず `README.md` および関連ドキュメントの相対リンクを同期更新すること。

# セキュリティ自動スキャンワークフロー 要件定義書 (Security Scan Workflow Requirements)

## 1. 概要 / 目的
本システム（realestate_crawler）における継続的インテグレーション（CI）およびクラウドセキュリティポスチャ管理（CSPM）の一環として、GitHub Actions 上で IaC（Terraform）、Python アプリケーション（コードSASTおよび依存関係SCA）、ならびに Google Cloud 設定状況に対する監査（Checkov & Prowler）を自動実行し、設定不備や脆弱性を未然に検知・防止する。

## 2. ユーザーストーリー
- **ユーザーとして**: 開発者およびクラウドセキュリティ管理者
- **行いたいこと**:
  1. master ブランチ宛ての Pull Request 作成・更新時に、Trivy、Semgrep、Checkov を並列実行して脆弱性と IaC/GCP 設定ミスを自動検知し、GitHub Security タブ（Code scanning）へ集約したい。
  2. 定期または手動実行にて、Prowler を用いて Google Cloud 本番環境のライブ設定状況（CIS Google Cloud Foundations Benchmark 等）を自動監査し、レポートを出力したい。
- **なぜなら**: Snyk を一時除外した環境下でも、IaC、アプリケーション、クラウドインフラ全体の安全性を客観的に担保するため。

## 3. 機能要件 (Functional Requirements)

### FR-SEC-001: ワークフロートリガー要件
- master ブランチへの Pull Request（opened, synchronize, reopened）および master ブランチへの push をトリガーとしてセキュリティスキャンが自動起動すること。
- Prowler GCP 監査は定期スケジュール（週次）および手動起動（`workflow_dispatch`）をサポートすること。

### FR-SEC-002: Trivy による SCA & IaC 一括スキャン
- Python 依存関係（`src/crawler/requirements.txt` 等）の CVE 脆弱性と Terraform（`terraform/`）の設定ミスを単一ジョブでまとめて走査すること。
- `.trivyignore` を尊重し、HIGH および CRITICAL 検出時に CI を終了コード 1 で落とすこと。

### FR-SEC-003: Semgrep による Python SAST スキャン
- Python ソースコード（`src/` 配下）に対する静的アプリケーションセキュリティテスト（SAST）を実行すること。
- ルールセット（`p/python`, `p/owasp-top-ten`, `p/security-audit`）を適用し、重大度 ERROR（High/Critical 相当）検出時に終了コード 1 で落とすこと。

### FR-SEC-004: Checkov による IaC / Google Cloud 設定監査
- Checkov を用い、`terraform/` ディレクトリ内の Google Cloud リソース定義（Cloud Storage, Cloud SQL, IAM, Cloud Run, Cloud Tasks, KMS, VPC 等）が CIS GCP Benchmark およびセキュリティベストプラクティスに準拠しているかを静的解析すること。
- SARIF レポートを出力し、GitHub Code Scanning に連携すること。

### FR-SEC-005: Prowler による Google Cloud ライブ設定状況監査 (CSPM)
- Prowler を用い、実稼働中の Google Cloud プロジェクト設定（IAM 権限、サービスアカウントキー運用、Cloud Audit Logs、VPCファイアウォール、バケット公開設定、暗号化状況など）を包括的に監査すること。
- GCP Workload Identity Federation を使用してセキュアに認証すること。
- 監査結果（HTML/CSV/JSON/SARIF）を GitHub Artifacts および Code scanning に連携すること。

### FR-SEC-006: SARIF 出力および GitHub Code Scanning 連携
- Trivy, Semgrep, Checkov の各ツールから SARIF 形式で結果を出力し、`upload-sarif` アクションにより GitHub の「Security > Code scanning alerts」へ自動アップロードすること（カテゴリ別管理）。

### FR-SEC-007: Snyk の一時除外・無効化
- `.github/workflows/snyk.yml` 内の Snyk 関連スキャンを一時無効化（コメントアウト）すること。

### FR-SEC-008: Dependabot 連携
- リポジトリ内の主要エコシステム（Python/pip, Terraform, npm, GitHub Actions, Docker）に対する `.github/dependabot.yml` を配置すること。

### FR-SEC-009: GitHub CodeQL ネイティブコードスキャン連携
- GitHub ネイティブ SAST エンジン（CodeQL）ワークフロー `.github/workflows/codeql.yml` を配備し、PRおよびmasterプッシュ時に自動実行して Code scanning alerts に直接統合すること。

### FR-SEC-010: SonarCloud Quality Gate による PR ブロック強制
- `.github/workflows/sonar.yml` において `-Dsonar.qualitygate.wait=true` を指定し、新設・変更コードに脆弱性や未解決セキュリティ問題が存在する場合に PR マージを確実にブロックすること。

### FR-SEC-011: 既存 Code Scanning 警告 (21件) の完全解消
- 過去の SonarCloud / GitHub Code Scanning に残存する全21件の警告（S8707 パスインジェクション、S4830/S5527/S5547 SSL/TLS設定、S4036 PATH解決、S2077 動的SQL、S2245 PRNG乱数、S1313 ハードコードIP、S4502 CSRF、S5443 一時ディレクトリ）を完全解消すること。

### FR-SEC-012: GitHub Code Scanning アラート (30件) の完全解消
- 現在 GitHub Code Scanning に残存する全30件のアラート（CodeQL: 20件、Checkov: 10件）を完全解消すること。
  1. `py/stack-trace-exposure`: HTTP 500 エラーハンドラーで例外の生文字列（`str(e)`）を返却せず汎用エラーメッセージに置換。
  2. `py/reflective-xss`: ユーザー入力パラメータの `html.escape()` サニタイズおよび明示的 `jsonify()` 返却。
  3. `py/bad-tag-filter`: `<script>` タグ正規表現に大文字小文字無視（`re.IGNORECASE`）を付与。
  4. `py/incomplete-url-substring-sanitization`: ドメイン誤認を招く `in` 部分一致の判定表現を是正。
  5. `actions/missing-workflow-permissions`: 各ワークフローに最小限の `permissions:`（`contents: read` 等）を明記。
  6. Checkov IaC 検出項目: ProxySQL Shielded VM / SSHキー設定、Cloud SQL PITR 有効化、および設計上許容される項目（Google管理AES暗号化、VPC内プライベートIP通信等）のスキップ定義整備。

### FR-SEC-013: PR 時の Code Scanning & Security Scan 自動検証・ブロック機構
- `security-scan.yml` の Checkov から `soft_fail: true` を撤廃し、未承認の誤設定検知時に CI を確実に失敗させること。
- PR レビューゲート（`review-gate.yml`）において、セキュリティスキャン（CodeQL, Trivy, Semgrep, Checkov）の成否および未解消 Code Scanning アラートを自動検証し、違反が存在する PR のマージ判定を確実にブロックすること。

### FR-SEC-014: `.checkov.yaml` によるポリシー・除外項目の一元管理
- CI およびローカルスキャンにおいて共通の Checkov 設定ファイル（`.checkov.yaml`）を配備し、インフラセキュリティ監査基準を統一・再現可能にすること。

## 4. 非機能要件
- **並列性 (Concurrency)**: PR 時の Trivy, Semgrep, Checkov, CodeQL を独立した並列ジョブとして構成すること。
- **権限最小化 (Least Privilege)**: ワークフローに必要な権限（`security-events: write`, `contents: read`, `id-token: write`）のみを付与すること。

# セキュリティ自動スキャンワークフロー 基本設計書 (Security Scan Workflow Basic Design)

## 1. システム構成・アーキテクチャ

### 1.1 多層防御アーキテクチャ
本システムは、コード変更時（Shift-Left 静的解析）と稼働中クラウド環境（CSPM 動的監査）の 2 系統のワークフローにより Google Cloud およびアプリケーションの安全性を担保する。

```text
【CI: PR / Push 契機】
.github/workflows/security-scan.yml
 ├── trivy-scan    (SCA: requirements.txt + IaC: terraform/) ──> SARIF ──> GitHub Security
 ├── semgrep-scan  (SAST: src/ Python コード)                ──> SARIF ──> GitHub Security
 └── checkov-scan  (IaC: terraform/ Google Cloud 設定監査)  ──> SARIF ──> GitHub Security

.github/workflows/codeql.yml
 └── codeql-scan   (GitHub Native SAST: Python & Actions)   ──> CodeQL ──> GitHub Security

.github/workflows/sonar.yml
 └── sonarcloud    (SonarCloud Scan + Quality Gate wait)    ──> Quality Gate 判定 (FAIL時PRブロック)

【CSPM: 定期 / 手動 契機】
.github/workflows/prowler-gcp-audit.yml
 └── prowler-gcp-scan (GCP ライブ設定監査 / Workload Identity) ──> HTML/CSV/SARIF
                                                               ├──> GitHub Artifacts
                                                               └──> GitHub Security
```

### 1.2 ツール役割・選定方針

| ツール | 対象 | スキャン種別 | 特徴・監査内容 | 実行タイミング |
| :--- | :--- | :--- | :--- | :--- |
| **Trivy** | `src/crawler/requirements.txt`, `terraform/` | SCA + IaC | 既知 CVE 脆弱性、Terraform 構成ミス検出 | PR作成・更新時 (CI) |
| **Semgrep** | `src/` (Python ソースコード) | SAST | OWASP Top 10、SQLi、認証認可、安全でない関数呼び出し | PR作成・更新時 (CI) |
| **Checkov** | `terraform/` | IaC / GCP設定監査 | CIS GCP Foundation Benchmark、GCP ポリシー違反の事前検知 | PR作成・更新時 (CI) |
| **Prowler** | Google Cloud 本番環境 | CSPM / ライブ監査 | IAM 過剰権限、KMS 暗号化、Cloud SQL 監査、ログ集約等の実環境監査 | 定期（週次）/ 手動 |
| **Dependabot** | pip, terraform, npm, actions, docker | 依存関係自動更新 | パッケージの定期最新化・セキュリティパッチ自動 PR 起票 | 定期 |

---

## 2. ワークフロー定義仕様

### 2.1 セキュリティスキャンワークフロー (`.github/workflows/security-scan.yml`)
- **トリガー**:
  - `pull_request`: `branches: [master, main]`, `types: [opened, synchronize, reopened]`
  - `push`: `branches: [master, main]`
- **パーミッション**:
  - `contents: read`
  - `security-events: write`
  - `actions: read`
- **並列性**:
  - `trivy-scan`, `semgrep-scan`, `checkov-scan` は独立して並列実行され、総実行時間を短縮。

### 2.2 Prowler GCP 監査ワークフロー (`.github/workflows/prowler-gcp-audit.yml`)
- **トリガー**:
  - `schedule`: 毎週月曜 09:00 JST (`cron: '0 0 * * 1'`)
  - `workflow_dispatch`: 手動実行（Severity、サービスフィルタ等）
- **認証**:
  - Google Cloud Workload Identity Federation:
    - Provider: `${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}`
    - Service Account: `${{ secrets.GCP_SERVICE_ACCOUNT }}`
- **出力成果物**:
  - HTML, CSV, JSON レポートを GitHub Artifacts へ保存
  - SARIF ファイルを GitHub Code Scanning へアップロード

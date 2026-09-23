# セキュリティ自動スキャンワークフロー 内部設計書 (Security Scan Workflow Internal Design)

## 1. ワークフロー実装詳細 (`.github/workflows/security-scan.yml`)

### 1.1 ジョブ構成
```yaml
name: Security Scan (Trivy, Semgrep, Checkov)

on:
  push:
    branches:
      - master
      - main
  pull_request:
    branches:
      - master
      - main
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  security-events: write
  actions: read

jobs:
  trivy-scan:
    ...
  semgrep-scan:
    ...
  checkov-scan:
    ...
```

### 1.2 `trivy-scan` ジョブ詳細
- **Runner**: `ubuntu-latest`
- **ステップ**:
  1. `actions/checkout@v4.2.2`
  2. `aquasecurity/trivy-action@master`:
     - `scan-type: 'fs'`
     - `scan-ref: '.'`
     - `scanners: 'vuln,misconfig'`
     - `severity: 'HIGH,CRITICAL'`
     - `format: 'sarif'`
     - `output: 'trivy-results.sarif'`
     - `trivyignores: '.trivyignore'`
     - `exit-code: '1'`
  3. `github/codeql-action/upload-sarif@v3`:
     - `if: (success() || failure()) && hashFiles('trivy-results.sarif') != ''`
     - `sarif_file: 'trivy-results.sarif'`
     - `category: 'trivy'`

### 1.3 `semgrep-scan` ジョブ詳細
- **Runner**: `ubuntu-latest`
- **ステップ**:
  1. `actions/checkout@v4.2.2`
  2. Semgrep SAST 実行:
     ```bash
     docker run --rm -v "${{ github.workspace }}:/src" semgrep/semgrep semgrep scan \
       --config "p/python" \
       --config "p/owasp-top-ten" \
       --config "p/security-audit" \
       --severity ERROR \
       --sarif \
       --output /src/semgrep.sarif \
       --error \
       src/
     ```
  3. `github/codeql-action/upload-sarif@v3`:
     - `if: (success() || failure()) && hashFiles('semgrep.sarif') != ''`
     - `sarif_file: 'semgrep.sarif'`
     - `category: 'semgrep'`

### 1.4 `checkov-scan` ジョブ詳細
- **Runner**: `ubuntu-latest`
- **ステップ**:
  1. `actions/checkout@v4.2.2`
  2. `bridgecrewio/checkov-action@v12`:
     - `directory: 'terraform'`
     - `framework: 'terraform'`
     - `output_format: 'cli,sarif'`
     - `output_file_path: 'console,results.sarif'`
     - `config_file: '.checkov.yaml'`
     - `soft_fail: false` # 誤設定検知時に CI を失敗させてブロック
  3. `github/codeql-action/upload-sarif@v3`:
     - `if: (success() || failure()) && hashFiles('results.sarif') != ''`
     - `sarif_file: 'results.sarif'`
     - `category: 'checkov'`

### 1.5 レビューゲート統合 (`.github/workflows/review-gate.yml`)
- **検査内容**:
  - `CodeQL Scan (python/actions)`, `Trivy Security Scan`, `Semgrep SAST Scan`, `Checkov IaC` ジョブの完了・成功状態を検証。
  - 未開始／実行中は必須 status `Verify All Review Conversations Resolved` を **pending**（failure にしない）。スキャン **failure** および未解消 Code Scanning アラートのみ **failure**。
  - 報告は `pr.head.sha` への単一 commit status に一本化（ジョブ名は `review-gate-runner`）。
  - GitHub Code Scanning API はまず `ref=refs/pull/{prNumber}/merge` を照会し、API エラー時のみ `ref=refs/heads/{head_ref}` にフォールバックする。未解消アラートがある場合は必須 status を **failure** としてマージをブロックする。

---

## 2. Prowler GCP 監査ワークフロー (`.github/workflows/prowler-gcp-audit.yml`)

### 2.1 構成概要
```yaml
name: Prowler GCP Security Posture Audit

on:
  schedule:
    - cron: '0 0 * * 1'  # 毎週月曜 09:00 JST / 00:00 UTC
  workflow_dispatch:
    inputs:
      severity:
        description: 'Severity filter (e.g. critical,high or all)'
        required: false
        default: 'critical,high'

permissions:
  contents: read
  id-token: write
  security-events: write

jobs:
  prowler-gcp:
    name: Prowler GCP Audit
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4.2.2

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Prowler
        run: pip install prowler

      - name: Run Prowler GCP Audit
        run: |
          mkdir -p prowler_output
          prowler gcp --severity ${{ inputs.severity || 'critical,high' }} --output-modes html,csv,json,sarif --output-directory prowler_output || true

      - name: Upload Prowler Artifacts
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: prowler-gcp-reports
          path: prowler_output/

      - name: Upload Prowler SARIF report
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: prowler_output/
          category: 'prowler-gcp'
```

---

## 3. Dependabot 設定詳細 (`.github/dependabot.yml`)
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/src/crawler"
    schedule:
      interval: "daily"
    open-pull-requests-limit: 10

  - package-ecosystem: "terraform"
    directory: "/terraform"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5

  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5

  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5

---

## 4. CodeQL ネイティブコードスキャン詳細 (`.github/workflows/codeql.yml`)
- **トリガー**: `push` (master/main), `pull_request` (master/main), `schedule` (週次日曜日)
- **対象言語**: `python`, `actions`
- **アクション構成**:
  - `github/codeql-action/init@v3`
  - `github/codeql-action/analyze@v3` (カテゴリ別アップロード: `/language:${{matrix.language}}`)

## 5. 既存 Code Scanning 警告 (21件) の恒久修正方針
1. **S8707 (Path Injection)**:
   - 対象: `sync_mlit_land_prices.py`, `sync_estat_municipalities.py`, `import_mlit_land_prices.py`, `import_mlit_stations.py`
   - 対応: `safe_path(path)` による `os.path.realpath` カノニカル検証を実施。
2. **S4830 / S5527 / S5547 (SSL/TLS & Cipher)**:
   - 対象: `debug_misawa_urls.py`, `package/api/api.py`
   - 対応: `check_hostname = False`, `CERT_NONE`, 脆弱暗号スイート指定を撤廃し、セキュアな `ssl.create_default_context()` に統一。
3. **S4036 (PATH Resolution)**:
   - 対象: `slack_agent_host.js`
   - 対応: `process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe'` により絶対パス解決。
4. **S2077 (Dynamic SQL Formatting)**:
   - 対象: `count_new_items.py`
   - 対応: raw SQL 文字列フォーマットを Django ORM (`apps.get_models()`) に置換。
5. **S2245 (Pseudorandom Number Generators)**:
   - 対象: `athomeParser.py`, `verify_parsers_random.py`
   - 対応: `random` を暗号学的安全な `secrets.SystemRandom()` に置換。
6. **S1313 (Hardcoded IP)**:
   - 対象: `realestateSettings.py`
   - 対応: ハードコードIP `'10.128.0.17'` を `os.getenv('DB_HOST', 'localhost')` に置換。
7. **S4502 (CSRF Protections)**:
   - 対象: `main.py`
   - 対応: ステートレスREST API用途明記の `# NOSONAR` を付与。
8. **S5443 (Publicly Writable Directory)**:
   - 対象: `package/api/__init__.py`
   - 対応: `/tmp` をプロジェクトルート配下の `logs/` 相対パスに変更。

# CI/CD パイプライン最適化内部設計書 (Issue #456)

## 1. ワークフロー変更一覧

### 1.1 `.github/workflows/test.yml`
- **変更前**:
  ```yaml
  on:
    pull_request:
      branches: [ main, master ]
    push:
      branches: [ main, master, production ]
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches: [ main, master ]
    push:
      branches: [ production ]
  ```
  ※ `push: [main, master]` を削除。本番デプロイ時の検証用として `production` のみ維持。

### 1.2 `.github/workflows/security-scan.yml`
- **変更前**:
  ```yaml
  on:
    push:
      branches:
        - master
        - main
    pull_request:
      branches:
        - master
        - main
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches:
        - master
        - main
  ```

### 1.3 `.github/workflows/codeql.yml`
- **変更前**:
  ```yaml
  on:
    push:
      branches:
        - master
        - main
    pull_request:
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches:
        - master
        - main
    schedule:
      - cron: '0 18 * * 0'
  ```

### 1.4 `.github/workflows/sonar.yml`
- **変更前**:
  ```yaml
  on:
    push:
      branches:
        - master
        - main
    pull_request:
      branches: [ main, master ]
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches: [ main, master ]
  ```

### 1.5 `.github/workflows/snyk.yml`
- **変更前**:
  ```yaml
  on:
    push:
      branches:
        - master
        - main
    pull_request:
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
  ```

### 1.6 `.github/workflows/swagger-generate.yml`
- **変更前**:
  ```yaml
  on:
    pull_request:
      branches: [ master, main, production ]
    push:
      branches: [ master, main ]
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches: [ master, main, production ]
  ```

### 1.7 `.github/workflows/review-gate.yml`
- **変更前**:
  ```yaml
  on:
    pull_request:
      branches:
        - master
        - production
  ```
- **変更後**:
  ```yaml
  on:
    pull_request:
      branches:
        - master
  ```

## 2. GitHub ブランチ保護ルールの更新設計
- **対象ブランチ**: `production`
- **Required Status Checks**:
  - `["Verify Source Branch is master"]` (`production-gate.yml`)
- **理由**: `production-gate.yml` は `master` からの PR かどうかのみを高速（数秒）で判定するため、Release PR のボトルネックを完全解消する。

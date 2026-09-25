# CI/CD パイプライン最適化要件定義書 (Issue #456)

## 1. 概要
本要件は、GitHub Actions における `master` push 時の重複ジョブを廃止し、PR（Pull Request）提出時のチェック網へ一本化することで、CIリソース浪費の根絶およびプロダクションへの Release PR（`master -> production`）のチェック通過・マージ時間を大幅短縮（10分超 ➔ 10秒以内）することを目的とする。

## 2. 背景と課題
1. **二重実行の無駄**:
   - feature/fix ブランチから `master` への PR 提出時に、全テスト（Parser Tests: 5並列）、SAST/SCA/IaCスキャン（CodeQL, Trivy, Semgrep, Checkov, Snyk）、および SonarCloud の全検査が実行され、100% 成功している。
   - PR マージ直後に `push: branches: [master]` により全く同一のコードに対して同一の全CIが再起動しており、リソース消費が倍増していた。
2. **Production Release PR の待機遅延**:
   - `auto-release-pr.yml` によりマージ直後に作成される Release PR が、`push: master` で走り始めた重いテストや SonarCloud（Pending 滞留）の完了を待たされ、マージまでに 10〜15 分以上拘束されていた。
3. **Review Conversation Gate の形骸化**:
   - `review-gate.yml` が `production` 宛て PR を検知して Bypass ログを書き込むためだけに不要起動していた。

## 3. 機能要件 (FR)
- **FR-001 (PR提出時チェックへの一本化)**:
  - `test.yml`, `security-scan.yml`, `codeql.yml`, `sonar.yml`, `snyk.yml`, `swagger-generate.yml` において、`push: branches: [master, main]` トリガーを削除し、PR（`pull_request`）提出時のチェックに一本化する。
- **FR-002 (Review Gate の production 除外)**:
  - `review-gate.yml` の監視対象ブランチから `production` を除外する。
- **FR-003 (Production ブランチ保護ルールの最速化)**:
  - `production` ブランチの Required Status Checks を `Verify Source Branch is master` (`production-gate.yml`) に設定し、`master` からの正当な PR であれば数秒〜10秒でパスさせる。

## 4. 非機能要件 (NFR)
- **NFR-001 (品質保証網の 100% 維持)**:
  - `master` に取り込まれるすべてのコードは、PR 提出時のゲート（テスト、セキュリティスキャン、レビュー解決）によって完全に保護され、品質基準が低下しないこと。
- **NFR-002 (Release PR 完了速度)**:
  - `master` マージ後の Release PR の CI 通過時間が 15 秒以内であること。

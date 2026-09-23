# 要件定義書: Prodマージ高速化・CIトリガー最適化・Dependabot集約の一貫改善 (Issue #376)

## 1. 背景と課題

現在、フィーチャーブランチから `master` にマージされた後、本番環境（`production` ブランチ）への反映までに数時間〜最長6時間超の待機・滞留時間（Lead Time to Production）が発生している。
直近PR（#250〜#373）の分析により、以下の4大ボトルネックが判明した：

1. **ProductionリリースPRの手動起票・放置**:
   - `master` へのマージ完了後、人間が手動で `production` 向けのPRを作成する運用となっており、マージ完了に気づくまで数時間放置される（PR #298 で 6.8時間、PR #321 で 6.4時間）。
2. **CodeRabbit による Production PR での重複レビュー・誤指摘ブロック**:
   - `.coderabbit.yaml` の `base_branches` に `"production"` が含まれており、`master` で検証済みのコードに対し、リリースPRで再度AIレビューが走り、誤指摘や未解決会話としてブロック・手動解除待ちが発生する（PR #372 で3件指摘発生）。
3. **`test.yml`（Parser Tests）の Production PR 重複実行**:
   - `master` の先端コミットは既にテスト全件パス済みであるにもかかわらず、`production` 向けPRで同一コミットに対してユニット・ミューテーションテストが再実行され、CI時間を消費する。
4. **Dependabot PR 乱発による CI キュー枯渇**:
   - 単体パッケージごとに最大30件のPRが同時起票され、全CIが並列走査されてGitHub Actions runnerを枯渇させ、手動でクローズ・集約する無駄な運用が発生している。
5. **Review Gate の過剰発火**:
   - コメント追加等のイベントごとにReview Gateが再起動し、大量のキャンセルとキュー待ちを招いている。

## 2. 目的とスコープ

* **目的**: `master` から `production` へのリリースPRマージ処理を自動化・高速化し、本番反映までの待ち時間を数時間から「数分以内」へ短縮するとともに、CIリソースの無駄な消費を削減する。
* **スコープ**:
  - `.coderabbit.yaml` のレビュー対象ブランチ最適化
  - `.github/workflows/test.yml` のPRトリガー最適化
  - `.github/workflows/review-gate.yml` のProduction fast-passおよびイベント抑制
  - `.github/workflows/auto-release-pr.yml` による自動Release PR起票・Auto-merge連携
  - `.github/dependabot.yml` のグループ化（Grouped Version Updates）

## 3. 機能要件 (Functional Requirements)

* **FR-01 (CodeRabbitのProduction除外)**: `.coderabbit.yaml` の `base_branches` は `["master"]` のみとし、`production` へのPRで自動レビューを実行しないこと。
* **FR-02 (テスト重複実行の防止)**: `test.yml` の `pull_request` トリガーから `production` を除外すること（`push` トリガーは維持）。
* **FR-03 (Review Gate の Production Fast-Pass)**: `review-gate.yml` は、PRのターゲットブランチが `production` である場合、重い走査をスキップして即座に `success` ステータスを返却すること。
* **FR-04 (Release PR の自動作成・同期)**: `master` へのプッシュ時に、`production` 向けのオープンなPRが存在しない場合は自動作成し、タイトル・コミット差分サマリー・Issue番号を記載すること。既存PRがある場合は自動で追従・更新されること。
* **FR-05 (Auto-merge 自動設定)**: 自動作成されたRelease PRに対して GitHub Auto-merge を有効化し、必要なチェックが通過次第自動マージすること。
* **FR-06 (Dependabot のグループ集約)**: 各パッケージエコシステム（pip, github-actions, terraform, docker）で `groups` を設定し、単体パッケージ別PRの乱発を週1回の集約PRに統合すること。

## 4. 非機能要件 (Non-Functional Requirements)

* **NFR-01 (速度と効率性)**: `master` マージから `production` マージ完了までの所要時間を 2分以内（Terraform Plan等の必要最小限のチェックのみ実行）に短縮すること。
* **NFR-02 (安全性とトレーサビリティ)**: `production-gate.yml`（`head_ref` が `master` であることの厳格な検証）は維持し、作業ブランチからの直接マージ防止ルールを堅持すること。
* **NFR-03 (リソース保全)**: Dependabot によるCI並列実行数を90%削減し、開発作業時のGitHub Actionsキュー詰まりを防止すること。

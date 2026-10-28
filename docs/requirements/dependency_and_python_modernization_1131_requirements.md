# 依存ライブラリおよび Python 実行環境の最新化・セキュリティ対策 要件定義書

## 1. 概要 / ユーザーストーリー
* **ユーザーとして**: 開発者およびセキュリティ運用担当者
* **実施内容**: 利用している Python 依存ライブラリ（Dependabot PR 提案分含む）および Python 実行基盤（Dockerfile / ローカル実行環境）を最新の安定版へ更新し、既知の脆弱性を解消する。
* **なぜなら**: セキュリティ対策として最新のパッチ適用と安定した実行環境を維持し、潜在的な脆弱性リスクや非互換リスクを未然に排除するため。

## 2. アクセプタンスクライテリア (受入基準)
* [x] `src/crawler/pyproject.toml` の下限指定および制約が、Dependabot 更新（40+ packages）および最新安定版に合わせて更新されていること
* [x] `poetry lock` および `poetry export --without-hashes -f requirements.txt` により `src/crawler/requirements.txt` が `poetry.lock` と整合していること
* [x] `Dockerfile` におけるベースイメージ（`python:3.11-slim-bookworm`）およびシステムパッケージの更新（`apt-get upgrade -y`、pip、poetry最新版インストール）が正常に維持されていること
* [x] ローカルホスト実行環境（`python311`）の主要パッケージ（boto3, botocore, certifi, pandas, ruff, pytest 等）が最新化されていること
* [x] ユニットテストおよびリグレッションテストがパスすること
* [x] GitHub Issue #1131 に関連づけられた Pull Request が作成され、Review Gate / Parser Tests 等の CI チェックが通過すること

## 3. 対象外
* Python メジャーバージョン 3.12/3.13 への一括破壊的移行（現行の本番アーキテクチャは 3.11 系 Debian Bookworm 安定版で固定されており、広範な C 拡張互換性検証を要するため別 Issue で段階的に実施）
* 破壊的変更を伴う `protobuf` メジャー 6.x（`google-genai` 等との依存整合上制限）

## 4. 関連 Issue
* GitHub Issue #1131
* Dependabot PR #1121, #1096, #1086, #1032

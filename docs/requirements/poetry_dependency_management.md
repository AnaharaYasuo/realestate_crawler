# 依存管理（Poetry 移行）

## 1. 概要 / ユーザーストーリー
* **ユーザーとして**、開発者
* **Dependabot 散在 PR を一本化し、`src/crawler` の依存を Poetry（`pyproject.toml` / `poetry.lock`）へ移行して最新化**したい
* **なぜなら**、個別 PR のレビュー負荷を下げ、ロックファイルで再現可能な依存管理へ移すため

## 2. アクセプタンスクライテリア (受入基準)
* [ ] `src/crawler` の依存管理が Poetry（`pyproject.toml` / `poetry.lock`）であること
* [ ] 旧 `requirements.txt` 由来パッケージが Poetry に取り込まれ、`poetry update` で最新化されていること
* [ ] Dockerfile / CI / Dependabot / 関連ドキュメントが Poetry 前提であること
* [ ] オープン中 Dependabot PR（pip / GitHub Actions / npm）の内容が集約 PR に含まれ、個別 PR がクローズされていること
* [ ] Docker イメージが Poetry 経由で依存インストールできること

## 3. 関連 Issue
* GitHub Issue #339

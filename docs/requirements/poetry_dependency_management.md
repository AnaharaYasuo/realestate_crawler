# 依存管理（Poetry）運用

## 1. 概要 / ユーザーストーリー
* **ユーザーとして**、開発者
* **`poetry update` / lock / export で制約内の上限まで依存を揃え、対応可能な GitHub Actions（Dependabot #350–#352）を一本化**したい
* **なぜなら**、依存の正を `poetry.lock` に保ちつつ、制約外のメジャー更新ノイズを避けて安全に更新するため

## 2. アクセプタンスクライテリア (受入基準)
* [x] `poetry update --lock` により `src/crawler/poetry.lock` が制約内上限へ更新されていること
* [x] `poetry export` により `src/crawler/requirements.txt` が lock と同期されていること
* [x] `github/codeql-action` が v4 に更新されていること（#350）
* [x] `google-github-actions/setup-gcloud` が v3 に更新されていること（#351）
* [x] `actions/github-script` が v9 に更新されていること（#352）
* [x] 対応不要な Dependabot PR（#347/#348/#349/#353/#354/#355/#356/#357）がクローズされていること
* [x] 本変更を含む一本化 PR が作成されていること

## 3. 対象外
* Python Docker 3.14、および `google-generativeai` 制約（`protobuf<6`）により到達できない Google/protobuf/pydantic-core 単独更新

## 4. 関連 Issue
* GitHub Issue #358
* 先行: #339 / PR #344

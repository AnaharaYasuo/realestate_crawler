# 依存管理（Poetry）— 内部設計

## 1. Docker インストール手順
1. `pyproject.toml` / `poetry.lock` をコピー
2. `pip install "poetry>=2.0,<3"`（ビルド段階・Dockerfile と一致）
3. `poetry config virtualenvs.create false`
4. `poetry install --no-interaction --no-ansi --only main`（または groups なしの既定）
5. ビルド用 apt パッケージを purge

## 2. requirements.txt の扱い
- ソース・オブ・トゥルースは Poetry
- 移行後も Trivy / ローカル Snyk 互換のため、`poetry export -f requirements.txt --without-hashes -o requirements.txt` で生成・コミットする
- Poetry 2.x の `poetry export` は `poetry-plugin-export` 依存。`src/crawler/pyproject.toml` に次を固定し、CI・開発環境でプラグインが自動要求されること:

```toml
[tool.poetry.requires-plugins]
poetry-plugin-export = ">=1.8"
```

- 手動環境では代替として `poetry self add poetry-plugin-export` でも可（バージョンは上記下限以上）

## 3. 定期更新手順
1. `cd src/crawler && poetry update --lock`
2. （プラグイン未導入時）`poetry self add poetry-plugin-export` または `requires-plugins` により導入を保証
3. `poetry install --no-interaction --no-ansi --only main`
4. `poetry export -f requirements.txt --without-hashes -o requirements.txt`
5. 差分レビュー（版が上がらない場合は制約天井に到達済み）
6. GitHub Actions 等の非 pip 更新は別途ワークフローを更新し、対応 Dependabot PR を一本化クローズ

## 4. Dependabot
- `package-ecosystem: pip` / `directory: /src/crawler`（Poetry 検出）
- pip の単独 PR が Poetry 上限を超える場合はクローズ（制約外）
- 対応可能な GitHub Actions PR は集約ブランチへ取り込み

## 5. 検証
- `docker compose build app` が成功すること
- 単体テストがコンテナ内で通過すること

# 依存管理（Poetry）— 内部設計

## 1. Docker インストール手順
1. `pyproject.toml` / `poetry.lock` をコピー
2. `pip install poetry`（ビルド段階）
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

## 3. Dependabot
- `package-ecosystem: pip` / `directory: /src/crawler` のまま（Poetry 検出）
- GitHub Actions / npm 更新は本 Issue の集約ブランチへ `git merge` で取り込む

## 4. 検証
- `docker compose build app` が成功すること
- 単体テストがコンテナ内で通過すること

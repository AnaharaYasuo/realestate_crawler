# 依存管理（Poetry）— 外部設計

## 1. 目的
`src/crawler` の Python 依存を Poetry に一本化し、Dependabot の散在更新を単一 PR で吸収する。

## 2. 構成

| 成果物 | 役割 |
|---|---|
| `src/crawler/pyproject.toml` | 直接依存の宣言 |
| `src/crawler/poetry.lock` | 解決結果の固定（再現性） |
| `Dockerfile` | `poetry install` でランタイム依存を導入 |
| `.github/dependabot.yml` | `pip` ecosystem は Poetry プロジェクト（同ディレクトリ）を監視 |

## 3. 更新方針
1. `poetry update --lock` で **依存グラフ全体が許す上限**まで更新する（直依存・推移依存のピンが天井）
2. `poetry install --no-interaction --no-ansi --only main` で lock を検証インストールする（export 前）
3. `poetry export -f requirements.txt --without-hashes -o requirements.txt` で互換用 `requirements.txt` を lock と同期する（`poetry-plugin-export` 必須）
4. Dependabot の単独版提案が Poetry 上限より高い場合は、制約衝突（例: `google-generativeai` → `protobuf<6`）であり、SDK 移行など別作業なしでは取り込まない
5. Poetry 2.x の `poetry export` は `poetry-plugin-export` 必須（`tool.poetry.requires-plugins` で下限 `>=1.8` を要求）

## 4. 非機能
- イメージビルドは Poetry 経由であること
- CI の SCA（Trivy fs）は `poetry.lock` を含むリポジトリ走査で継続可能であること
- `poetry export` 利用時は `poetry-plugin-export` が利用可能であること（`src/crawler/pyproject.toml` の `tool.poetry.requires-plugins` で固定）

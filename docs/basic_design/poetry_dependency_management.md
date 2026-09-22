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

## 3. 移行方針
1. 既存 `requirements.txt` の制約を `poetry add` で取り込む（Python 3.11 で不要な backports は除外）
2. `poetry update` で最新互換へ更新
3. 互換ツール向けに `poetry export` で `requirements.txt` を再生成してもよい（ロックと同期）。Poetry 2.x では `poetry export` は `poetry-plugin-export` が提供するため、**CI・開発環境の双方で当該プラグインを明示導入またはピン留め**すること（未導入だと export 失敗し `poetry.lock` と同期できない）

## 4. 非機能
- イメージビルドは Poetry 経由であること
- CI の SCA（Trivy fs）は `poetry.lock` を含むリポジトリ走査で継続可能であること
- `poetry export` 利用時は `poetry-plugin-export` が利用可能であること（`src/crawler/pyproject.toml` の `tool.poetry.requires-plugins` で固定）

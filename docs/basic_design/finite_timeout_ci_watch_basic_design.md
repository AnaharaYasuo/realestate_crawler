# CI/PR 監視における無制限 --watch 禁止および有限タイムアウトポーリング強制 基本設計書 (Issue #602)

## 1. システム構成と監視アーキテクチャ
CI/PR監視における無限ハングを排除するため、従来の同期ブロック（`--watch`）方式を廃止し、有限タイムアウトによる非同期ポーリング＋即時診断アーキテクチャに刷新する。

```
[開発者 / AIエージェント]
       │
       ▼ (有限タイムアウト: timeout=10s)
[check_pr_ci_status.py] ──(GitHub CLI / REST API)──▶ [GitHub Actions]
       │                                                    │
       ├─ 全ジョブ pass ────────▶ マージ可能判定 (Exit 0)   │
       ├─ fail / action_required ─▶ 即座に診断情報出力 (Exit 1)
       └─ pending 継続 ─────────▶ interval秒待機後再確認 (max_attempts超過でExit 2)
```

## 2. 監視ステータス定義
GitHub Actions の各ジョブ結果を以下のカテゴリに分類する：

| カテゴリ | 判定条件 | 振る舞い |
|---|---|---|
| **PASS** | `pass`, `success`, `skipping` | 正常完了。全ジョブが該当すれば合格。 |
| **PENDING** | `pending`, `in_progress`, `queued` | 実行中。最大試行回数までインターバル待機。 |
| **BLOCKED** | `action_required`, `cancelled` | 手動承認または再実行待ち。即時検知してジョブ詳細取得・報告。 |
| **FAIL** | `fail`, `failure` | テスト・スキャン失敗。即時検知してエラーログ特定・終了。 |

## 3. CLI インターフェース設計
スクリプト名: `src/crawler/scripts/debug_tools/check_pr_ci_status.py`

### コマンドライン引数
- `--pr <PR_NUMBER>`: 監視対象のPull Request番号（必須、正の整数）。
- `--max-attempts <INT>`: 最大ポーリング回数（デフォルト: 20、正の整数）。
- `--interval <INT>`: ポーリング間隔（秒）（デフォルト: 15、正の整数）。
- `--cli-timeout <FLOAT>`: 1回のghコマンド/API実行タイムアウト秒数（デフォルト: 10.0、上限10.0秒）。
- `--json`: 結果をJSON形式で出力。

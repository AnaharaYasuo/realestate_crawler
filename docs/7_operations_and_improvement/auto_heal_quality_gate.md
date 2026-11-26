# オートヒール品質ゲート＆データ完全性保証仕様 (Auto-Heal Quality Gate & Data Integrity)

## 1. 概要と背景
パースエラー検知時にAI（Gemini/サブエージェント）が自律的にセレクタや正規表現を修正するオートヒール（Auto-Heal）機構において、**「テストは通過するが、実際には空文字や誤ったデータが抽出され続け、DBやML学習データがサイレント汚染される（見せかけの修復）」** という重大リスクを排除する。

---

## 2. オートヒール完了判定の3大必須ゲート

AIサブエージェントが修正コードをコミット・PR作成する前に、以下の3つの検証ゲートをすべてパスしなければ修復完了と認定してはならない。

```
[ AI によるセレクタ / コード修正 ]
   ↓
[ Gate 1: 単体テスト実行 (pytest) ] ➔ PASS
   ↓
[ Gate 2: 動的生HTML二段階検証 (3件 ➔ 20件) ] ➔ PASS
   ↓
[ Gate 3: データ完全性・非空率アサーション (Data Integrity Assertion) ] ➔ PASS
   ↓
[ 修復完了・PR作成 ]
```

---

## 3. Gate 3: データ完全性・非空率アサーション仕様

修正前後のパース結果を比較し、抽出できたフィールドの充実度が過去実績を下回らないことを検証する。

### 3.1 必須フィールドの抽出成功率（非空率）基準
生HTML 20件の拡張検証において、以下の非空率（Non-Empty Rate）を下回った場合は **見せかけの修復（Mock Fix）** と判定してリジェクトする。

| フィールド群 | 対象項目 | 許容最低非空率 | 判定基準 |
| :--- | :--- | :--- | :--- |
| **最重要必須属性** | 物件名 (`property_name`), 価格 (`price`), 所在地 (`address`) | **100% (20/20件)** | 1件でも空文字または取得失敗があれば即FAIL |
| **重要スペック属性** | 専有面積/土地面積, 間取り, 築年月 | **95% 以上 (19/20件)** | 過去正常時の抽出率と同等を義務付け |
| **付帯スペック属性** | 階数, 構造, 接道幅員, 管理費, 修繕積立金 | **80% 以上 (16/20件)** | セレクタを広げすぎて他セルのゴミテキストが入っていないこと |

### 3.2 異常値・サニティチェック (Sanity Check)
- **価格サニティ**: `price < 1,000,000`（100万円未満）または `price > 10,000,000,000`（100億円超）の物件が全体の 10% 以上を占める場合は、セレクタによる取得箇所誤りと判定。
- **面積サニティ**: `exclusive_area < 5.0`（5㎡未満）または `exclusive_area > 1,000.0`（1,000㎡超）の異常値検出。

---

## 4. クローリング障害連携 ＆ Issue 自動再オープン仕様 (Issue #1536)

クローリング全タスク集約時および日次整合性スキャンにおいて、検知された障害を確実に修復キューへ投入するため、以下の連携・同期プロトコルを義務付ける。

### 4.1 全体クローリング集約時の機械的障害連携 (E2E Pipeline Integration)
- `run_all_crawlers.py` の集約完了時、失敗ジョブ（`failed_list`）が 1 件以上存在する場合：
  1. Slack へのアラート発信に加え、直ちに `auto_heal_parsers.py --failed-steps '<JSON配列>'` を直接サブプロセス実行して指示書（`Temp/auto_heal_instruction.json`）を生成する。
  2. 続いて `sync_auto_heal_issues.py --instruction-file Temp/auto_heal_instruction.json` を実行し、GitHub Issue へ確実に反映・同期する。
  3. これにより、人間による手動介入や Slack コマンド入力を待たずに、クローリング完了直後から GitHub Actions または Antigravity 自律エージェントによる自動修復が即座に起動可能となる。

### 4.2 既存 CLOSED Issue の自動再オープン規約 (Auto Re-Open Policy)
- `sync_auto_heal_issues.py` の同期処理において、同一キー（`company:property_type` または `pipeline:<step>`）を持つ過去の Issue が既に `CLOSED` 状態であっても：
  - 新たなスキャンやテレメトリで未解決異常が再検知された場合、単なる「コメント追記」で済ませず、**最新テレメトリコメントを追記した上で直ちに `gh issue reopen <number>` を実行して OPEN 状態へ復帰**させる。
  - 受入基準（チェックボックス）がすべて `[x]` になっていた場合は、未完了状態（`- [ ]`）へリセットする。
  - これにより、`sync_auto_heal_issues.py --list-actionable` で確実に抽出対象となり、過去に一度修復されたパーサーが再度のレイアウト変更等で再発した際の見落とし・未着手放置を完全に防止する。

---

## 5. 自動修復サーキットブレーカー適正運用仕様 (Issue #1561)

自動修復ループにおける誤ったサーキットブレーカー発動（`auto-heal:needs-human` への誤エスカレーション）を防止するため、以下の運用規約および CLI 挙動を義務付ける。

### 5.1 調査・事実確認先行原則（着手前インクリメントの完全禁止）
- **着手前インクリメントの禁止**: 調査やコード修正に着手する前の段階で形式的・機械的に `--record-attempt` を呼び出すことを禁止する。未調査のまま試行回数上限（2回）を消費してしまう誤エスカレーションを防止する。
- **実態調査の先行**: まず対象 Issue のパーサー実装、エラー生HTML/ログ、動的疎通状況を調査し、先行PRでの解決状況や真のエラー原因を特定する。

### 5.2 人手対応へのエスカレーション全面禁止と失敗記録 (`--reason`)
- **人手対応へのエスカレーション禁止**: `--escalate` や `auto-heal:needs-human` ラベルを付与して人手対応へ丸投げすることを全面禁止とする。404・接続タイムアウト・サイト側元データ未記載であっても、別サンプルURL取得・GCS生HTML解析・パーサー/バリデーション/クローラー側の根本修正を自律的に完遂すること。
- **自動エスカレーション機能の無効化 (Issue #1840)**: `sync_auto_heal_issues.py --record-attempt` は試行回数および失敗理由の記録のみを行い、試行回数が上限を超えても `auto-heal:needs-human` への自動エスカレーションを行わない（常に `escalated: false` を返し `auto-heal` ラベルを維持する）。
- `sync_auto_heal_issues.py --record-attempt <number> [--reason "<理由>"]`
  - 修正・再現テストを試みた結果、修復に失敗した場合の証跡記録としてのみ実行する。

---

## 6. 割安物件通知未配信・MLパイプライン異常の日次 Auto-Heal 統合仕様 (Issue #1849)

パーサー不整合だけでなく、日次の割安物件通知（`send_recommendations.py`）の未配信および ML パイプライン（`run_ml_pipeline.py`）の異常終了を確実に日次オートヒールの修復キュー（`auto-heal` GitHub Issue）へ自動投入する。

### 6.1 GCS 配信ハートビート監視と自動 Issue 起票・自動クローズ (`sync_auto_heal_issues.py`)
- `sync_auto_heal_issues.py --pull-from-gcs` 実行時、`auto_heal/latest_instruction.json` の同期に加え、GCS の以下 2 つのハートビートを検査する：
  1. `monitoring/recommendation_last_success.json`（当日 JST の割安物件通知完了・成否）
  2. `monitoring/ml_pipeline_last_status.json`（当日 JST の ML パイプライン実行ステータス・失敗ステップ）
- 当日 JST の割安物件通知が未完了（未存在・前日以前・`status != "ok"`）であり、かつ ML パイプラインが正常稼働中（`status == "running"` かつ開始から 3 時間以内）でない場合、固定キー `pipeline:bargain-recommendation-not-delivered` として `auto-heal` ラベル付き GitHub Issue を自動起票（既存クローズ済みがあれば自動再オープン）する。
- `ml_pipeline_last_status.json` に失敗ステップが記録されている場合も `failed_pipeline_steps` に合流させ、対応する `pipeline:<step>` Issue を起票・更新する。
- 翌日の配信成功（`completed_date_jst == today_jst` かつ `status == "ok"`）が確認された時点で `active_groups` から消滅し、`_close_resolved_issues()` により自動クローズされる。

### 6.2 GitHub Actions 同期スケジュール最適化 (`.github/workflows/sync-auto-heal-issues.yml`)
- `realestate-ml-pipeline-prod`（`20:10 UTC` / `05:10 JST` 起動、最大 3 時間）の完了後に確実に検査できるよう、cron を `15 22 * * *`（`07:15 JST`）および `20 23 * * *`（`08:20 JST`）の 2 回構成とする。



# 仕様書: Issue #1072 レコメンド配信および日次精度診断のクエリチャンク分割・タイムアウト防止 (SDD)

## 1. 背景と課題
- 本番環境の `property_evaluation` テーブルには 18 万件を超える評価レコードが存在する。
- `send_recommendations.py` では `candidates = _fetch_recommendation_candidates()` で未通知かつ有効なレコード（約 15 万件）を一括抽出した上で、ループ内で `get_property_record(eval_rec)`（物件 1 件あたり 1 回の SELECT クエリ）を同期的に繰り返し実行していた。
- 15 万件のループ処理によりクエリが数十分間にわたり継続し、ProxySQL または Cloud SQL のコネクションアイドル/通信切断（Code: 2013 `Lost connection to server during query`）が発生していた。
- 同様に `run_daily_prediction_diagnostics.py` においても大規模クエリセットに対するカウントやイテレーションがコネクションタイムアウトを誘発するリスクがある。

## 2. 要件定義 (Functional Requirements)
1. **`send_recommendations.py` の候補抽出・評価の効率化**:
   - `_fetch_recommendation_candidates()` において、直近 48 時間以内に解析された物件を優先し、さらに処理上限（例: 最大 1,000 件〜2,000 件）または最新解析日順（`order_by('-analyzed_at')`）のスライスを取得する。
   - 物件レコードの取得を 1 件ごとの単発クエリから、モデルごとに `pageUrl__in=[...]` でバルク取得（チャンク化辞書ルックアップ）できるように最適化する。
   - クエリセットを一度に全件メモリに展開する `len(candidates)` や `_result_cache` を避け、`iterator(chunk_size=500)` またはスライス処理とする。
2. **`run_daily_prediction_diagnostics.py` の安全性向上**:
   - 診断対象クエリセットの集計処理で接続切断が発生しないよう、チャンク分割またはタイムアウトハンドリングを実施。
3. **既存機能の完全互換性**:
   - 優先度算出ロジック・2シグマ外れ値フィルタ・Slack通知フォーマット等の仕様は完全に維持する。

## 3. テスト計画 (TDD)
- `tests/unit/test_issue_1072_recommendation_chunking.py`:
  - `_fetch_recommendation_candidates()` が上限付きまたはチャンク化されて取得されること。
  - バルクまたはチャンク化された物件取得で同一の推薦判定結果が得られること。

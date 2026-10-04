# 物件URL一意性制約および重複排除・アップサート仕様要件 (Issue #660)

## 1. 背景と課題
- 全不動産モデルが継承する `PropertyBaseModel` において、`pageUrl` カラムに一意性制約（`unique=True`）が未設定であった。
- クローリング実行時に同一URLの物件が別IDとして重複INSERTされるケースがあり、データベース内に同一URLの重複レコードが蓄積されていた。
- 後続のバルクML価格推定ジョブ (`run_bulk_ml_evaluation.py`) では、評価結果保存先である `property_evaluation` テーブルの `property_url` に一意性制約が設定されているため、クローリング元データに重複URLが存在すると `IntegrityError (Duplicate entry)` が発生しジョブがクラッシュ・タイムアウトしていた。

## 2. 要件定義
1. **既存データの重複クレンジング**:
   - 各物件モデルテーブルにおいて、同一 `pageUrl` を持つレコードが存在する場合、最新のレコード（`id` 最大値）を1件のみ残し、古い重複レコードを物理削除すること。
2. **モデル一意制約の強制**:
   - `PropertyBaseModel` の `pageUrl` フィールドに `unique=True` を定義し、DBスキーマレベルで重複混入を恒久的に遮断すること。
3. **アップサート（Update or Create）の徹底**:
   - クローラーの物件データ保存処理では、同一URLが存在する場合は新規INSERTではなく既存レコードのフィールド更新（UPSERT）とすること。
4. **バルクML評価の耐障害性**:
   - `run_bulk_ml_evaluation.py` において、`PropertyEvaluation.objects.bulk_create` に `ignore_conflicts=True` を指定し、並行実行時の競合や重複によるクラッシュを完全に防止すること。
   - メモリ内でのURL重複排除を事前に行い、同一バッチ内で同じURLを二重にINSERTしようとしないこと。

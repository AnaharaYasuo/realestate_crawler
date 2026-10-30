# 全サイト全モデル欠損データ（traffic等）包括的復旧 内部設計書 (Issue #913)

## 1. モジュール構成
- 対象ファイル: `src/crawler/scripts/maintenance/restore_missing_traffic_data.py`
- テストファイル: `src/crawler/tests/unit/test_restore_missing_traffic_data.py`

## 2. 関数詳細仕様

### 2.1 `get_all_target_property_models()`
```python
def get_all_target_property_models() -> list:
    """全アプリケーションから traffic フィールドおよび交通系フィールドを持つ物件モデルを動的抽出"""
```
- **処理ロジック**:
  1. `from django.apps import apps`
  2. `apps.get_models()` をイテレート。
  3. 各モデルの `_meta.fields` からフィールド名集合を取得。
  4. `'traffic'` が含まれ、かつ `station1`〜`5` または `railway1`〜`5` のいずれかが含まれるモデルを抽出。
  5. テーブル名順にソートしてリストとして返却。

### 2.2 `synthesize_traffic_str(item) -> str`
- **処理ロジック**:
  - Route 1〜5 のループ: `railway{i}`, `station{i}`, `railwayWalkMinute{i}`, `railwayWalkMinute{i}Str`
  - Bus 1〜5 のループ: `busStation{i}`, `busWalkMinute{i}`, `busWalkMinute{i}Str`
  - 重複排除の上、`" / ".join(parts)` を返却。

### 2.3 `restore_traffic_from_existing_fields(dry_run: bool = True) -> dict[str, int]`
- **処理ロジック**:
  - `dry_run=False` の場合、`assert_production_db_safety("restore_traffic")` を実行。
  - `get_all_target_property_models()` で全モデル取得。
  - 各モデルに対し、`traffic` が空で、交通情報（`station1`〜`5` または `railway1`〜`5`）が存在するレコードを `Q` オブジェクトで抽出。
  - イテレータでチャンク（500件）ごとに `bulk_update(batch, ["traffic"])`。

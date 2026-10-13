# 本番DBローカル保護機構・マイグレ完全整合化・欠損データ全件復旧 内部設計書 (Issue #909)

## 1. 内部モジュール実装詳細

### 1.1 `src/crawler/realestateSettings.py` / `manage.py`
- ハードガード関数 `assert_production_db_safety(command_name: str)` を追加。
- 実行中のサブコマンドが `migrate` 等のスキーマ変更系である場合、
  ```python
  def assert_production_db_safety():
      if os.getenv("IS_PRODUCTION_DEPLOYMENT") == "true":
          return
      # 本番DB接続判定
      db_host = os.getenv("DB_HOST", "")
      db_port = str(os.getenv("DB_PORT", ""))
      db_name = os.getenv("DB_NAME", "")
      is_prod_target = (
          ("host.docker.internal" in db_host or "34." in db_host or "35." in db_host)
          and db_port in ("3306", "3307")
          and db_name == "real_estate"
      )
      if is_prod_target:
          raise RuntimeError(
              "CRITICAL BLOCK: Direct schema migration against production DB from non-deployment environment is strictly forbidden!"
          )
  ```
- これを `manage.py` の先頭および `realestateSettings.py` の `configure()` 内で呼び出し、二重で防壁を張る。

### 1.2 `src/crawler/package/ml/evaluation/targets.py`
- `iter_unprocessed_chunks` 内のクエリ取得処理を、カーソル破棄の例外を発生させない安全な ID ベースページネーション方式に変更：
  ```python
  def iter_unprocessed_chunks(model_cls, chunk_size=1000):
      # ID範囲またはスライシングで安全にフェッチ
      # 各チャンク処理後にのみ安全に close_old_connections() を呼ぶ
  ```

### 1.3 `src/crawler/package/utils/data_validator.py`
- `_check_madori_and_age` で、対象オブジェクトが Django モデルインスタンスの場合、`_meta.get_field(...)` またはモデル定義をチェックし、フィールドが存在しない場合は検査をスキップする。

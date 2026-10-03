# 内部設計書: ProxySQL MIG クライアント引数整合性修復およびフォールバック内部設計

## 1. 変更対象ファイルと詳細ロジック

### 1.1 `src/crawler/scripts/ensure_resources_stopped.py`

#### `_get_mig_info(project_id: str, region: str, mig_name: str)`
- `client.get(...)` 呼び出しのキーワード引数を `region_instance_group_manager=mig_name` から `instance_group_manager=mig_name` に変更。
- `except Exception as e:` ブロックで直ちに `return -1, str(e), None` とせず、`logger.warning(f"Failed to get MIG info via compute_v1: {e}")` を出力して `compute_v1` ブロックを抜け、後続の `token = _get_gcp_access_token()` および REST API 呼び出しへ進む。

#### `_resize_mig_to_zero(project_id: str, region: str, mig_name: str)`
- `client.resize(...)` 呼び出しのキーワード引数を `region_instance_group_manager=mig_name` から `instance_group_manager=mig_name` に変更。
- `except Exception as e:` ブロックで直ちに `return str(e)` とせず、`logger.warning(f"Failed to resize MIG via compute_v1: {e}")` を出力して `compute_v1` ブロックを抜け、後続の `token = _get_gcp_access_token()` および REST API 呼び出しへ進む。

### 1.2 `src/crawler/package/utils/gcp_resources.py`

#### `resize_proxysql_mig(target_size: int, project_id: str | None = None, region: str | None = None, mig_name: str | None = None, ...)`
- `client.resize(...)` 呼び出しのキーワード引数を `region_instance_group_manager=mig` から `instance_group_manager=mig` に変更。

### 1.3 `src/crawler/tests/test_ensure_resources_stopped.py`
- `mock_instance.resize.assert_called_once_with(...)` の引数アサーションを `instance_group_manager="proxysql-mig-prod"` に更新。
- `mock_instance.get` において例外が発生した場合でも REST API フォールバックにより正常に MIG 情報を取得・停止できるテストケースを追加。

### 1.4 `src/crawler/tests/unit/test_gcp_resources.py`
- `mock_compute.RegionInstanceGroupManagersClient.return_value.resize.assert_called_once()` 周辺の引数アサーションを `instance_group_manager="proxysql-mig-prod"` に更新。

# 基本設計書: ProxySQL MIG クライアント引数整合性修復およびフォールバック設計

## 1. 概要
本設計書は、Google Cloud Compute API クライアント (`compute_v1.RegionInstanceGroupManagersClient`) による ProxySQL MIG 操作時の引数不整合を解消し、例外発生時の多重防御（フォールバック）を強化するための基本設計を規定する。

## 2. アーキテクチャと変更方針

### 2.1 API シグネチャ整合
Google Cloud Compute API Python クライアントライブラリ (`google-cloud-compute`) の `RegionInstanceGroupManagersClient` メソッド仕様:
- `get(project: str, region: str, instance_group_manager: str, timeout: float)`
- `resize(project: str, region: str, instance_group_manager: str, size: int, timeout: float)`

従来のコードでは `region_instance_group_manager` という誤ったキーワードが渡されていたため、これを公式 SDK 仕様に準拠した `instance_group_manager` に改修する。

### 2.2 多重防御フォールバック（Resilience）
従来:
`compute_v1` クライアント呼び出しで例外が発生した場合、`_get_mig_info` および `_resize_mig_to_zero` は即座に `(-1, str(e), None)` や `str(e)` を返し、直後の Slack アラート（緊急障害通知）を発報していた。

改善後:
`compute_v1` 呼び出しで例外（ライブラリ不整合、一時的ネットワーク不全等）を捕捉した場合、警告ログ (`logger.warning`) を記録した上で処理を中断せず、後続の GCP メタデータ / OAuth トークンを用いた REST API 直接呼び出し（HTTP GET / POST）へとフォールバックする。

```
[MIG 情報取得 / リサイズ要求]
         │
         ▼
[compute_v1 クライアント呼び出し] (引数: instance_group_manager)
         │
         ├── 成功 ──> 正常終了
         │
         └── 失敗 (例外発生)
                 │ (logger.warning 記録)
                 ▼
       [REST API フォールバック] (HTTP GET/POST)
                 │
                 ├── 成功 ──> 正常終了
                 │
                 └── 失敗 ──> エラー通知 / Slack アラート発報
```

## 3. 影響範囲
- `src/crawler/scripts/ensure_resources_stopped.py`
- `src/crawler/package/utils/gcp_resources.py`
- ユニットテスト (`test_ensure_resources_stopped.py`, `test_gcp_resources.py`)

# 要件定義書: ProxySQL MIG クライアント引数整合性修復およびフォールバック強化要件

## 1. 背景と目的
GCP 上で運用される ProxySQL Managed Instance Group (MIG) のゾンビ監視および自動縮退処理（`ensure_resources_stopped.py` および `gcp_resources.py`）において、Google Cloud Compute API クライアント (`google.cloud.compute_v1.RegionInstanceGroupManagersClient`) の `get` および `resize` メソッド呼び出し時に不正な引数名 `region_instance_group_manager` が渡され、以下の例外が発生していた：
`RegionInstanceGroupManagersClient.get() got an unexpected keyword argument 'region_instance_group_manager'`

これにより MIG のステータス取得が失敗し、誤って緊急 Slack アラート（`:rotating_light: *【緊急】ProxySQL MIG状態取得失敗*`）が発報される障害が発生した。
本要件は、API クライアント引数を正しいシグネチャ `instance_group_manager` に修正するとともに、SDK 呼び出しエラー発生時の REST API フォールバック耐性を向上させ、安定したリソース管理と誤報ゼロを実現することを目的とする。

## 2. 対象スコープ
1. `src/crawler/scripts/ensure_resources_stopped.py`:
   - `_get_mig_info()`: `client.get()` の引数修正および compute_v1 失敗時の REST API フォールバック継続。
   - `_resize_mig_to_zero()`: `client.resize()` の引数修正および compute_v1 失敗時の REST API フォールバック継続。
2. `src/crawler/package/utils/gcp_resources.py`:
   - `resize_proxysql_mig()`: `client.resize()` の引数修正。
3. テストコード:
   - `src/crawler/tests/test_ensure_resources_stopped.py`: モック引数の検証修正およびフォールバック動作テスト。
   - `src/crawler/tests/unit/test_gcp_resources.py`: モック引数の検証修正。

## 3. 機能要件
- **FR-001 (引数名の正常化)**:
  `google.cloud.compute_v1.RegionInstanceGroupManagersClient` の `get()` および `resize()` に渡すキーワード引数を `instance_group_manager` に統一する。
- **FR-002 (二重防御フォールバック機構)**:
  `ensure_resources_stopped.py` の `_get_mig_info` および `_resize_mig_to_zero` において、`compute_v1` の呼び出しで予期しない例外が発生した場合、即座にエラーリターンしてアラートを出すのではなく、警告ログを記録した上で後続の GCP REST API (HTTP) フォールバック処理を実行する。
- **FR-003 (gcp_resources.py との整合性)**:
  `src/crawler/package/utils/gcp_resources.py` の `resize_proxysql_mig` においても同様に `instance_group_manager` を使用し、ProxySQL スケール処理の共通整合性を保つ。

## 4. 非機能要件
- **NFR-001 (リグレッション防止)**: 既存の全テストが通過すること。
- **NFR-002 (迅速な回復)**: compute_v1 または REST API のいずれかが機能していれば、MIG 状態取得・停止が正常に完遂すること。

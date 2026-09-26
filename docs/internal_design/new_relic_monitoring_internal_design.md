# New Relic 統合監視 内部詳細設計書

## 1. モジュールおよびファイル構成
- `src/crawler/package/utils/newrelic_helper.py`: New Relic APM の安全な初期化ヘルパー関数、GenAI / LLM メトリクス記録、クローラー実行統計カスタムイベント記録。
- `src/crawler/main.py`: ヘルスチェックルート（`/`, `/health`）の実装および `init_new_relic()` の呼び出し。
- `docker-compose.newrelic.yml`: New Relic Infrastructure エージェントおよびコンテナ監視定義。
- `terraform/new_relic_gcp_integration.tf`: GCP Cloud Logging ➔ New Relic ログ転送 Pub/Sub トピック・ログシンク・Push サブスクリプション。
- `src/crawler/scripts/setup_new_relic_synthetics.py`: NerdGraph GraphQL API を利用した Synthetics 外形監視の登録・更新 CLI。
- `src/crawler/scripts/notify_new_relic_deployment.py`: NerdGraph Change Tracking API を利用したデプロイイベント通知スクリプト。
- `src/crawler/scripts/setup_new_relic_crawler_alerts.py`: クローラー特化の NRQL アラートポリシー＆条件プロビジョニングスクリプト。
- `src/crawler/tests/unit/test_new_relic_full_stack.py`: GenAI メトリクス、クローラーイベント、デプロイ通知、NRQL アラート設定の包括的単体テスト。
- `terraform/secrets.tf`: Secret Manager 定義。
- `terraform/cloud_run_api_service.tf`, `terraform/cloud_run_crawler_service.tf`: 環境変数注入設定。

## 2. 実装詳細

### 2.1 `newrelic_helper.py`
```python
import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def init_new_relic() -> bool:
    """Initialize New Relic APM agent if NEW_RELIC_LICENSE_KEY is configured."""
    license_key = os.getenv("NEW_RELIC_LICENSE_KEY")
    if not license_key:
        return False

    app_name = os.getenv("NEW_RELIC_APP_NAME", "realestate-crawler")
    try:
        import newrelic.agent
        newrelic.agent.initialize()
        logger.info(f"New Relic APM agent initialized for app: {app_name}")
        return True
    except Exception as e:
        logger.warning(f"Failed to initialize New Relic APM agent: {e}")
        return False

def record_llm_event(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: float,
    status: str = "success",
    error_msg: Optional[str] = None,
    cost_usd: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Record LLM/GenAI invocation telemetry to New Relic custom events (LlmEvent)."""
    # newrelic.agent.record_custom_event("LlmEvent", params)
    ...

def record_crawler_metrics(
    site_name: str,
    property_type: str,
    count: int,
    duration_sec: float,
    zero_count: bool = False,
    status: str = "success",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Record crawler run metrics to New Relic custom events (CrawlerExecution)."""
    ...

def notice_error(error: Exception, custom_params: Optional[Dict[str, Any]] = None) -> bool:
    """Safely report exception to New Relic APM with custom attributes."""
    ...
```

### 2.2 `main.py` ヘルスチェックルート追加
```python
@app.route('/health', methods=['GET'])
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "service": "realestate-api",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }), 200
```

### 2.3 Synthetics プロビジョニング NerdGraph クエリ
```graphql
mutation CreateSyntheticsMonitor($accountId: Int!, $monitor: SyntheticsCreateSimpleMonitorInput!) {
  syntheticsCreateSimpleMonitor(accountId: $accountId, monitor: $monitor) {
    errors {
      description
      type
    }
    monitor {
      id
      name
      status
      period
      uri
    }
  }
}
```

### 2.4 Change Tracking GraphQL Mutation
```graphql
mutation CreateDeployment($deployment: ChangeTrackingDeploymentInput!) {
  changeTrackingCreateDeployment(deployment: $deployment) {
    deploymentId
    entityGuid
  }
}
```

### 2.5 クローラー NRQL アラート条件
```sql
-- ゼロ件取得失敗アラート
SELECT count(*) FROM CrawlerExecution WHERE zero_count = true OR (count = 0 AND status != 'no_updates') FACET site_name

-- パース速度劣化（> 1.0秒/件）
SELECT average(duration_sec / count) FROM CrawlerExecution WHERE count > 0 FACET site_name

-- 対象サイト 403 / 429 拒絶急増
SELECT count(*) FROM CrawlerExecution WHERE status IN ('blocked_403', 'rate_limited_429') FACET site_name
```

### 2.6 パイプライン・バッチクローラー実行時の計装
```python
# run_pipeline.py / run_all_crawlers.py 冒頭
from package.utils.newrelic_helper import init_new_relic, record_crawler_metrics
init_new_relic()

# run_all_crawlers.py での各ジョブ終了時
record_crawler_metrics(
    site_name=company,
    property_type=ptype,
    count=scraped_cnt,
    duration_sec=float(elapsed),
    zero_count=(scraped_cnt == 0 and status == "success"),
    status=status,
    metadata={"exit_code": exit_code, "error_msg": error_msg or ""}
)
```

## 3. テスト計画
- `test_health_endpoint`: `/` および `/health` が 200 OK かつ JSON 形式で `status: ok` を返すことを検証。
- `test_new_relic_initialization_without_key`: `NEW_RELIC_LICENSE_KEY` 未設定時に `init_new_relic()` が `False` を返し、エラーを起こさないこと。
- `test_new_relic_initialization_with_key`: `NEW_RELIC_LICENSE_KEY` 設定時に正常に処理が呼び出されること（モックによる検証）。
- `test_record_llm_event`: 正常系・異常系・コスト計算・キー未設定時のフォールバックを検証。
- `test_record_crawler_metrics`: クローラー実行イベントのパラメータバリデーションとイベント記録を検証。
- `test_notice_error`: 例外レポートとカスタムパラメータ転送を検証。
- `test_notify_deployment_nerdgraph`: Change Tracking API の GraphQL ペイロード組み立てとレスポンスハンドリングを検証。
- `test_crawler_alerts_provisioning`: NRQL アラートルール登録ペイロードと有限タイムアウト処理を検証。
- `test_run_all_crawlers_records_crawler_metrics`: バッチクローラーが完了したジョブに対して `record_crawler_metrics` を呼び出すことを検証。


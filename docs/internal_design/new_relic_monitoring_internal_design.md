# New Relic 統合監視 内部詳細設計書

## 1. モジュールおよびファイル構成
- `src/crawler/package/utils/newrelic_helper.py`: New Relic APM の安全な初期化ヘルパー関数。
- `src/crawler/main.py`: ヘルスチェックルート（`/`, `/health`）の実装および `init_new_relic()` の呼び出し。
- `src/crawler/scripts/setup_new_relic_synthetics.py`: NerdGraph GraphQL API を利用した Synthetics 外形監視の登録・更新 CLI。
- `src/crawler/tests/test_new_relic_integration.py`: 初期化処理、ヘルスチェックレスポンス、環境変数ハンドリングの単体テスト。
- `terraform/secrets.tf`: Secret Manager 定義。
- `terraform/cloud_run_api_service.tf`, `terraform/cloud_run_crawler_service.tf`: 環境変数注入設定。

## 2. 実装詳細

### 2.1 `newrelic_helper.py`
```python
import os
import logging

logger = logging.getLogger(__name__)

def init_new_relic() -> bool:
    """Initialize New Relic APM agent if NEW_RELIC_LICENSE_KEY is configured."""
    license_key = os.getenv("NEW_RELIC_LICENSE_KEY")
    if not license_key:
        return False

    app_name = os.getenv("NEW_RELIC_APP_NAME", "realestate-crawler")
    distributed_tracing = os.getenv("NEW_RELIC_DISTRIBUTED_TRACING_ENABLED", "true")

    try:
        import newrelic.agent
        # 環境変数経由で設定を読み込み初期化
        newrelic.agent.initialize()
        logger.info(f"New Relic APM agent initialized for app: {app_name}")
        return True
    except Exception as e:
        logger.warning(f"Failed to initialize New Relic APM agent: {e}")
        return False
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
入力パラメータ:
```json
{
  "accountId": 8553111,
  "monitor": {
    "name": "RealEstate API Health Check",
    "status": "ENABLED",
    "period": "EVERY_5_MINUTES",
    "uri": "https://realestate-api-prod-62ys4zbasq-an.a.run.app/health",
    "locations": {
      "public": ["AP_NORTHEAST_1", "AP_EAST_1"]
    }
  }
}
```

## 3. テスト計画
- `test_health_endpoint`: `/` および `/health` が 200 OK かつ JSON 形式で `status: ok` を返すことを検証。
- `test_new_relic_initialization_without_key`: `NEW_RELIC_LICENSE_KEY` 未設定時に `init_new_relic()` が `False` を返し、エラーを起こさないこと。
- `test_new_relic_initialization_with_key`: `NEW_RELIC_LICENSE_KEY` 設定時に正常に処理が呼び出されること（モックによる検証）。
